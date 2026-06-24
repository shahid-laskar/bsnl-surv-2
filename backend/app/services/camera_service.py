"""
app/services/camera_service.py
Business logic for camera_master CRUD.

cam_id generation:
  Uses SELECT FOR UPDATE to prevent the race condition present in the
  original Django save() override. The lock is held only for the duration
  of the ID selection + insert — milliseconds.

MediaMTX integration:
  After creating/deleting a camera the service calls MediaMTX's REST API
  to register/deregister the stream path. Failures are logged but do not
  roll back the DB change (the operator can re-sync manually).
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    CamIDGenerationError,
    CameraConflictError,
    CameraNotFoundError,
    CustomerNotFoundError,
)
from app.models.camera import camera_master
from app.models.customer import customer_master
from app.models.geography import ba_master, circle_master
from app.schemas.camera import CameraCreateRequest, CameraUpdateRequest
from app.services.mediamtx_service import MediaMTXService

logger = structlog.get_logger(__name__)


class CameraService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._mtx = MediaMTXService()

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_by_cam_id(self, cam_id: str) -> camera_master:
        result = await self._db.execute(select(camera_master).where(camera_master.cam_id == cam_id))
        cam = result.scalar_one_or_none()
        if cam is None:
            raise CameraNotFoundError(cam_id)
        return cam

    async def list_for_customer(
        self,
        com_id: int | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[camera_master], int]:
        """Return (cameras, total_count) for a customer (or all customers if com_id is None), with optional active filter."""
        q = select(camera_master)
        if com_id is not None:
            q = q.where(camera_master.com_id == com_id)
        if is_active is not None:
            q = q.where(camera_master.is_active == is_active)

        count_result = await self._db.execute(select(func.count()).select_from(q.subquery()))
        total = count_result.scalar_one()

        result = await self._db.execute(
            q.order_by(camera_master.cam_id).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create(
        self,
        data: CameraCreateRequest,
        added_by_id: int,
    ) -> camera_master:
        """
        Create a new camera with a race-condition-safe cam_id.
        Registers the stream path with MediaMTX after DB commit.
        """
        # Verify customer exists and load hierarchy
        cust_result = await self._db.execute(
            select(customer_master).where(customer_master.id == data.com_id)
        )
        customer = cust_result.scalar_one_or_none()
        if customer is None:
            raise CustomerNotFoundError(data.com_id)

        # Generate cam_id under SELECT FOR UPDATE
        cam_id = await self._generate_cam_id(customer.cir_id, customer.ba_id)

        cam = camera_master(
            cam_id=cam_id,
            cam_name=data.cam_name,
            cam_loc=data.cam_loc,
            cam_make=data.cam_make,
            cam_usrname=data.cam_usrname,
            cam_pass=data.cam_pass,
            cam_strm1=data.cam_strm1,
            cam_strm2=data.cam_strm2,
            cam_strm3=data.cam_strm3,
            cam_onvif=data.cam_onvif,
            motion_active=data.motion_active,
            is_active=True,
            com_id=data.com_id,
            cir_id=customer.cir_id,
            ba_id=customer.ba_id,
            device_id=data.device_id,
            added_by=added_by_id,
            strm_type_id=data.strm_type_id,
        )

        if data.strm_type_id:
            from app.models.device import stream_master
            strm_result = await self._db.execute(select(stream_master).where(stream_master.id == data.strm_type_id))
            cam.stream_type = strm_result.scalar_one_or_none()

        self._db.add(cam)
        await self._db.flush()  # Get PK without committing transaction

        logger.info("camera.created", cam_id=cam_id, com_id=data.com_id)

        # Register with MediaMTX (best-effort, non-transactional)
        await self._mtx.add_path(cam)

        return cam

    async def update(self, cam_id: str, data: CameraUpdateRequest) -> camera_master:
        """Partial update — only fields present in the request body are changed."""
        cam = await self.get_by_cam_id(cam_id)

        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(cam, field, value)

        await self._db.flush()
        logger.info("camera.updated", cam_id=cam_id, fields=list(update_data.keys()))

        # If stream URL changed, re-register with MediaMTX
        if "cam_strm1" in update_data or "is_active" in update_data:
            if cam.is_active:
                await self._mtx.add_path(cam)
            else:
                await self._mtx.delete_path(cam_id)

        return cam

    async def deactivate(self, cam_id: str) -> camera_master:
        """
        Soft-delete: set is_active=False and remove from MediaMTX.
        Does not delete the DB record — recordings and motion events are preserved.
        """
        cam = await self.get_by_cam_id(cam_id)
        cam.is_active = False
        await self._db.flush()

        await self._mtx.delete_path(cam_id)
        logger.info("camera.deactivated", cam_id=cam_id)
        return cam

    async def reactivate(self, cam_id: str) -> camera_master:
        """Re-enable a deactivated camera and restore the MediaMTX path."""
        cam = await self.get_by_cam_id(cam_id)
        cam.is_active = True
        await self._db.flush()

        await self._mtx.add_path(cam)
        logger.info("camera.reactivated", cam_id=cam_id)
        return cam

    # ── cam_id generation ─────────────────────────────────────────────────────

    async def _generate_cam_id(self, cir_id: int, ba_id: int) -> str:
        """
        Generate the next sequential cam_id for a circle+BA pair.

        Algorithm:
          1. SELECT FOR UPDATE on camera_master WHERE cir_id AND ba_id
             to serialize concurrent inserts.
          2. Find the highest existing sequence number.
          3. Increment and return the new cam_id.

        The lock is row-level (not table-level) so cameras in different
        circle+BA combinations are not blocked.
        """
        # Fetch circle and BA codes for prefix construction
        cir_result = await self._db.execute(select(circle_master).where(circle_master.id == cir_id))
        circle = cir_result.scalar_one_or_none()

        ba_result = await self._db.execute(select(ba_master).where(ba_master.id == ba_id))
        ba = ba_result.scalar_one_or_none()

        if circle is None or ba is None:
            raise CamIDGenerationError(f"Circle {cir_id} or BA {ba_id} not found")

        prefix = f"CAM{circle.cir_code}{ba.ba_code}"

        # SELECT FOR UPDATE — serialises concurrent cam_id generation
        result = await self._db.execute(
            select(camera_master)
            .where(
                camera_master.cir_id == cir_id,
                camera_master.ba_id == ba_id,
                camera_master.cam_id.like(f"{prefix}%"),
            )
            .order_by(camera_master.cam_id.desc())
            .limit(1)
            .with_for_update()
        )
        latest = result.scalar_one_or_none()

        if latest and latest.cam_id:
            try:
                last_num = int(latest.cam_id[-5:])
                next_num = last_num + 1
            except (ValueError, IndexError):
                raise CamIDGenerationError(f"Cannot parse sequence from cam_id '{latest.cam_id}'")
        else:
            next_num = 1

        if next_num > 99999:
            raise CamIDGenerationError(f"cam_id sequence exhausted for prefix '{prefix}'")

        return f"{prefix}{next_num:05d}"
