"""
tests/unit/test_stream_service.py
"""

from unittest.mock import AsyncMock

import pytest
from app.models.camera import camera_master
from app.services.stream_service import StreamService

@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()

@pytest.mark.asyncio
async def test_generate_stream_token(mock_db: AsyncMock, mocker: AsyncMock) -> None:
    # Mock _get_active_camera
    mock_cam = camera_master(cam_id="CAMKLTVM00001", com_id=1, is_active=True)
    mocker.patch.object(StreamService, "_get_active_camera", return_value=mock_cam)
    
    service = StreamService(mock_db)
    
    resp = await service.generate_stream_token(
        cam_id="CAMKLTVM00001",
        user_id=1,
        user_com_id=1,
        user_role="cust_admin"
    )
    
    assert resp.cam_id == "CAMKLTVM00001"
    assert resp.token is not None
    assert "token=" in resp.stream_url
