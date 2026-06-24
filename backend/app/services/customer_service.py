"""
app/services/customer_service.py
Business logic for customer_master (tenant/company) CRUD.

Role scoping:
  sysadmin     → full access, any circle/BA
  circle_admin → customers within their own circle
  ba_admin     → customers within their own circle + BA
  cust_admin   → read-only, their own company only
  viewer       → read-only, their own company only

Key fixes vs. previous version:
  1. list_for_user: guard against com_id being None for cust_admin/viewer —
     previously would produce "WHERE id = NULL" returning nothing silently.
  2. get_by_id / list now join circle, BA, plan, and count cameras to populate
     the enriched CustomerResponse / CustomerListItem fields the frontend needs.
  3. create() validates that the com_id FK target actually exists when creating
     users scoped to a customer (enforced in user_service, surfaced here for
     reuse via assert_customer_exists()).
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, CustomerNotFoundError, ForbiddenError, NotFoundError
from app.models.auth import SvUser
from app.models.camera import camera_master
from app.models.customer import customer_master, plan_master
from app.models.geography import ba_master, circle_master
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerListItem,
    CustomerResponse,
    CustomerUpdateRequest,
)

logger = structlog.get_logger(__name__)


class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_by_id(self, customer_id: int) -> customer_master:
        """Return a plain customer_master ORM object (for permission checks etc.)."""
        result = await self._db.execute(
            select(customer_master).where(customer_master.id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def get_response(self, customer_id: int) -> CustomerResponse:
        """
        Return a fully-enriched CustomerResponse: joins circle/BA/plan names
        and aggregates the camera count for the customer.
        """
        customer = await self.get_by_id(customer_id)
        return await self._enrich_single(customer)

    async def assert_customer_exists(self, customer_id: int) -> None:
        """Raise NotFoundError if the customer does not exist. Used by user_service."""
        result = await self._db.execute(
            select(customer_master.id).where(customer_master.id == customer_id)
        )
        if result.scalar_one_or_none() is None:
            raise NotFoundError(f"Customer {customer_id} not found")

    async def list_for_user(
        self,
        current_user: SvUser,
        ba_id: int | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[CustomerListItem], int]:
        """Role-scoped customer list, optionally narrowed to a single BA."""
        q = select(customer_master)

        if current_user.role == "sysadmin":
            pass
        elif current_user.role == "circle_admin":
            q = q.where(customer_master.cir_id == current_user.cir_id)
        elif current_user.role == "ba_admin":
            q = q.where(
                customer_master.cir_id == current_user.cir_id,
                customer_master.ba_id == current_user.ba_id,
            )
        else:
            # cust_admin / viewer — scoped to their own company only.
            # Guard: if com_id is somehow None, return empty list rather than
            # silently running "WHERE id = NULL" which returns nothing.
            if not current_user.com_id:
                return [], 0
            q = q.where(customer_master.id == current_user.com_id)

        if ba_id is not None:
            q = q.where(customer_master.ba_id == ba_id)

        count_result = await self._db.execute(select(func.count()).select_from(q.subquery()))
        total = count_result.scalar_one()

        result = await self._db.execute(
            q.order_by(customer_master.com_name).offset(offset).limit(limit)
        )
        customers = list(result.scalars().all())
        items = [await self._enrich_list_item(c) for c in customers]
        return items, total

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create(self, data: CustomerCreateRequest, created_by: SvUser) -> CustomerResponse:
        self._validate_creation_permission(created_by, data)
        await self._assert_circle_ba_plan_exist(data.cir_id, data.ba_id, data.plan_id)

        customer = customer_master(
            com_name=data.com_name,
            com_adr=data.com_adr,
            gstn=data.gstn,
            cir_id=data.cir_id,
            ba_id=data.ba_id,
            plan_id=data.plan_id,
        )
        self._db.add(customer)
        await self._db.flush()
        logger.info("customer.created", com_id=customer.id, created_by=created_by.id)
        return await self._enrich_single(customer)

    async def update(
        self, customer_id: int, data: CustomerUpdateRequest, updated_by: SvUser
    ) -> CustomerResponse:
        """Partial update — cir_id/ba_id are immutable."""
        customer = await self.get_by_id(customer_id)
        self._validate_update_permission(updated_by, customer)

        if data.plan_id is not None:
            await self._assert_plan_exists(data.plan_id)

        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        await self._db.flush()
        logger.info(
            "customer.updated",
            com_id=customer_id,
            by=updated_by.id,
            fields=list(update_data.keys()),
        )
        return await self._enrich_single(customer)

    # ── Enrichment helpers ────────────────────────────────────────────────────

    async def _enrich_single(self, customer: customer_master) -> CustomerResponse:
        """Build a CustomerResponse with joined names and camera count."""
        cir_name, ba_name, plan_name, cam_limit = await self._fetch_joined_names(
            customer.cir_id, customer.ba_id, customer.plan_id
        )
        camera_count = await self._count_cameras(customer.id)
        return CustomerResponse(
            id=customer.id,
            com_name=customer.com_name,
            com_adr=customer.com_adr,
            gstn=customer.gstn,
            cir_id=customer.cir_id,
            ba_id=customer.ba_id,
            plan_id=customer.plan_id,
            cir_name=cir_name,
            ba_name=ba_name,
            plan_name=plan_name,
            camera_count=camera_count,
            camera_limit=cam_limit,
        )

    async def _enrich_list_item(self, customer: customer_master) -> CustomerListItem:
        """Build a CustomerListItem with joined names and camera count."""
        cir_name, ba_name, plan_name, cam_limit = await self._fetch_joined_names(
            customer.cir_id, customer.ba_id, customer.plan_id
        )
        camera_count = await self._count_cameras(customer.id)
        return CustomerListItem(
            id=customer.id,
            com_name=customer.com_name,
            com_adr=customer.com_adr,
            gstn=customer.gstn,
            cir_id=customer.cir_id,
            ba_id=customer.ba_id,
            plan_id=customer.plan_id,
            cir_name=cir_name,
            ba_name=ba_name,
            plan_name=plan_name,
            camera_count=camera_count,
            camera_limit=cam_limit,
        )

    async def _fetch_joined_names(
        self, cir_id: int, ba_id: int, plan_id: int
    ) -> tuple[str, str, str, int]:
        """Return (cir_name, ba_name, plan_name, cam_limit)."""
        cir_res = await self._db.execute(
            select(circle_master.cir_name).where(circle_master.id == cir_id)
        )
        cir_name = cir_res.scalar_one_or_none() or ""

        ba_res = await self._db.execute(select(ba_master.ba_name).where(ba_master.id == ba_id))
        ba_name = ba_res.scalar_one_or_none() or ""

        plan_res = await self._db.execute(
            select(plan_master.plan_name, plan_master.cam_limit).where(plan_master.id == plan_id)
        )
        plan_row = plan_res.one_or_none()
        plan_name = plan_row[0] if plan_row else ""
        cam_limit = plan_row[1] if plan_row else 0

        return cir_name, ba_name, plan_name, cam_limit

    async def _count_cameras(self, com_id: int) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(camera_master)
            .where(
                camera_master.com_id == com_id,
                camera_master.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one() or 0

    # ── Permission helpers ────────────────────────────────────────────────────

    def _validate_creation_permission(self, creator: SvUser, data: CustomerCreateRequest) -> None:
        if creator.role == "sysadmin":
            return
        if creator.role == "circle_admin":
            if data.cir_id != creator.cir_id:
                raise ForbiddenError("circle_admin can only create customers in their own circle")
            return
        if creator.role == "ba_admin":
            if data.cir_id != creator.cir_id or data.ba_id != creator.ba_id:
                raise ForbiddenError(
                    "ba_admin can only create customers in their own circle and BA"
                )
            return
        raise ForbiddenError("Role not permitted to create customers")

    def _validate_update_permission(self, updater: SvUser, customer: customer_master) -> None:
        if updater.role == "sysadmin":
            return
        if updater.role == "circle_admin":
            if customer.cir_id != updater.cir_id:
                raise ForbiddenError("circle_admin can only update customers in their own circle")
            return
        if updater.role == "ba_admin":
            if customer.cir_id != updater.cir_id or customer.ba_id != updater.ba_id:
                raise ForbiddenError(
                    "ba_admin can only update customers in their own circle and BA"
                )
            return
        raise ForbiddenError("Role not permitted to update customers")

    def assert_view_permission(self, viewer: SvUser, customer: customer_master) -> None:
        """Raise ForbiddenError if `viewer` cannot see `customer`."""
        if viewer.role == "sysadmin":
            return
        if viewer.role == "circle_admin":
            if customer.cir_id != viewer.cir_id:
                raise ForbiddenError("Access to this company is not permitted for your account")
            return
        if viewer.role == "ba_admin":
            if customer.cir_id != viewer.cir_id or customer.ba_id != viewer.ba_id:
                raise ForbiddenError("Access to this company is not permitted for your account")
            return
        # cust_admin / viewer
        if customer.id != viewer.com_id:
            raise ForbiddenError("Access to this company is not permitted for your account")

    # ── Existence / referential checks ───────────────────────────────────────

    async def _assert_circle_ba_plan_exist(self, cir_id: int, ba_id: int, plan_id: int) -> None:
        cir_result = await self._db.execute(select(circle_master).where(circle_master.id == cir_id))
        if cir_result.scalar_one_or_none() is None:
            raise NotFoundError(f"Circle {cir_id} not found")

        ba_result = await self._db.execute(select(ba_master).where(ba_master.id == ba_id))
        ba = ba_result.scalar_one_or_none()
        if ba is None:
            raise NotFoundError(f"BA {ba_id} not found")
        if ba.cir_id != cir_id:
            raise ConflictError(f"BA {ba_id} does not belong to circle {cir_id}")

        await self._assert_plan_exists(plan_id)

    async def _assert_plan_exists(self, plan_id: int) -> None:
        plan_result = await self._db.execute(select(plan_master).where(plan_master.id == plan_id))
        if plan_result.scalar_one_or_none() is None:
            raise NotFoundError(f"Plan {plan_id} not found")
