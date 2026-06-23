"""
app/api/v1/dashboard.py
Dashboard stats endpoint: active cameras, live streams, counts.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.services.dashboard_service import DashboardService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_service(db: AsyncSession = Depends(get_db)) -> DashboardService:
    return DashboardService(db=db)


@router.get("/stats", summary="Get dashboard statistics (role-scoped)")
async def dashboard_stats(
    current_user: CurrentUser = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> dict:
    return await service.get_stats(current_user)


@router.get("/camera-status", summary="Get per-camera online/offline status (role-scoped)")
async def camera_status(
    current_user: CurrentUser = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> list:
    return await service.get_camera_status(current_user)
