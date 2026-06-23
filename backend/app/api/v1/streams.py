"""
app/api/v1/streams.py
API endpoints for stream token generation.
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.schemas.camera import StreamTokenResponse
from app.services.stream_service import StreamService

logger = structlog.get_logger(__name__)

# Note: We mount this on /cameras to match the pattern /api/v1/cameras/{cam_id}/stream-token
router = APIRouter(prefix="/cameras", tags=["streams"])


def get_stream_service(db: AsyncSession = Depends(get_db)) -> StreamService:
    return StreamService(db=db)


@router.get("/{cam_id}/stream-token", response_model=StreamTokenResponse)
async def get_stream_token(
    cam_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: StreamService = Depends(get_stream_service),
) -> StreamTokenResponse:
    """
    Get a short-lived JWT token and HLS URL for camera streaming.
    Requires authentication and verifies the user has access to the camera's company.
    """
    return await service.generate_stream_token(
        cam_id=cam_id,
        user_id=current_user.id,
        user_com_id=current_user.com_id,
        user_role=current_user.role,
    )
