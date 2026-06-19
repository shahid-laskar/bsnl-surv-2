"""
app/api/v1/cameras.py
Camera CRUD endpoints.

All write operations require sysadmin or circle_admin.
Read operations allow any authenticated user, scoped to their company.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_role
from app.core.exceptions import ForbiddenError
from app.core.security import create_stream_token
from app.models.auth import SvUser
from app.schemas.camera import (
    CameraCreateRequest,
    CameraListItem,
    CameraResponse,
    CameraUpdateRequest,
    StreamTokenResponse,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services.camera_service import CameraService
from app.core.config import settings

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=PaginatedResponse[CameraListItem], summary="List cameras")
async def list_cameras(
    com_id: int = Query(..., description="Filter by customer/company ID"),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CameraListItem]:
    """
    List cameras for a company.
    Users can only see cameras belonging to their own company (or all, for sysadmin).
    """
    _assert_customer_access(current_user, com_id)

    params = PaginationParams(page=page, page_size=page_size)
    service = CameraService(db)
    cameras, total = await service.list_for_customer(
        com_id=com_id,
        is_active=is_active,
        offset=params.offset,
        limit=params.page_size,
    )
    items = [CameraListItem.model_validate(c) for c in cameras]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "",
    response_model=CameraResponse,
    status_code=201,
    dependencies=[Depends(require_role("sysadmin", "circle_admin"))],
    summary="Create camera",
)
async def create_camera(
    body: CameraCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    """
    Register a new camera.
    Automatically generates cam_id using a race-condition-safe SELECT FOR UPDATE.
    Registers the stream path with MediaMTX after creation.
    """
    service = CameraService(db)
    cam = await service.create(body, added_by_id=current_user.id)
    return CameraResponse.model_validate(cam)


@router.get("/{cam_id}", response_model=CameraResponse, summary="Get camera")
async def get_camera(
    cam_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    service = CameraService(db)
    cam = await service.get_by_cam_id(cam_id)
    _assert_customer_access(current_user, cam.com_id)
    return CameraResponse.model_validate(cam)


@router.patch(
    "/{cam_id}",
    response_model=CameraResponse,
    dependencies=[Depends(require_role("sysadmin", "circle_admin"))],
    summary="Update camera",
)
async def update_camera(
    cam_id: str,
    body: CameraUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> CameraResponse:
    service = CameraService(db)
    cam = await service.update(cam_id, body)
    return CameraResponse.model_validate(cam)


@router.post(
    "/{cam_id}/deactivate",
    response_model=MessageResponse,
    dependencies=[Depends(require_role("sysadmin", "circle_admin"))],
    summary="Deactivate camera (soft delete)",
)
async def deactivate_camera(
    cam_id: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = CameraService(db)
    await service.deactivate(cam_id)
    return MessageResponse(message=f"Camera {cam_id} deactivated")


@router.post(
    "/{cam_id}/reactivate",
    response_model=MessageResponse,
    dependencies=[Depends(require_role("sysadmin", "circle_admin"))],
    summary="Reactivate camera",
)
async def reactivate_camera(
    cam_id: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    service = CameraService(db)
    await service.reactivate(cam_id)
    return MessageResponse(message=f"Camera {cam_id} reactivated")


@router.get(
    "/{cam_id}/stream-token",
    response_model=StreamTokenResponse,
    summary="Get a short-lived HLS stream token",
)
async def get_stream_token(
    cam_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamTokenResponse:
    """
    Generate a short-lived JWT (15 min) for HLS stream access.
    The stream URL embeds the token as a query parameter, which Nginx
    validates via auth_request before proxying segments from MediaMTX.
    """
    service = CameraService(db)
    cam = await service.get_by_cam_id(cam_id)
    _assert_customer_access(current_user, cam.com_id)

    token = create_stream_token(cam_id=cam_id, user_id=current_user.id)
    stream_url = f"http://{settings.domain_name}/stream/hls/{cam_id}/index.m3u8?token={token}"

    return StreamTokenResponse(
        cam_id=cam_id,
        stream_url=stream_url,
        token=token,
        expires_in=settings.jwt_stream_token_expire_minutes * 60,
    )


@router.get(
    "/{cam_id}/status",
    summary="Get live stream status from MediaMTX",
)
async def get_camera_status(
    cam_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Query MediaMTX for real-time stream readiness and reader count."""
    service = CameraService(db)
    cam = await service.get_by_cam_id(cam_id)
    _assert_customer_access(current_user, cam.com_id)

    from app.services.mediamtx_service import MediaMTXService

    mtx = MediaMTXService()
    path_info = await mtx.get_path(cam_id)

    if path_info is None:
        return {"cam_id": cam_id, "ready": False, "readers": 0}

    return {
        "cam_id": cam_id,
        "ready": path_info.get("ready", False),
        "readers": len(path_info.get("readers", [])),
        "source": path_info.get("source"),
    }


# ── Scope enforcement helper ──────────────────────────────────────────────────


def _assert_customer_access(user: SvUser, com_id: int) -> None:
    """
    Raise ForbiddenError if a non-sysadmin tries to access another company's cameras.
    sysadmin and circle_admin see all companies (circle_admin enforced at query level).
    """
    if user.role == "sysadmin":
        return
    if user.role in ("circle_admin", "ba_admin"):
        return  # further scoping handled at query level
    # cust_admin and viewer can only see their own company
    if user.com_id != com_id:
        raise ForbiddenError(f"Access to company {com_id} is not permitted for your account")
