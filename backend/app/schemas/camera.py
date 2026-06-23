"""
app/schemas/camera.py
Pydantic V2 schemas for camera_master CRUD.

FIX (see customer/geography delivery notes): CameraResponse / CameraListItem
previously used Django-style `_id`-suffixed field names (com_id_id, cir_id_id,
ba_id_id, device_id_id, strm_type_id_id) that don't exist as attributes on
the SQLAlchemy camera_master model — only `com_id`, `cir_id`, etc. do. With
`from_attributes=True`, that mismatch made every CameraResponse.model_validate()
call raise a validation error, breaking GET/POST/PATCH /cameras. Field names
below now match the model exactly.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CameraCreateRequest(BaseModel):
    """Request body for POST /cameras."""

    model_config = ConfigDict(str_strip_whitespace=True)

    cam_name: str = Field(min_length=1, max_length=100)
    cam_loc: str = Field(min_length=1, max_length=300)
    cam_make: str = Field(min_length=1, max_length=100)
    cam_usrname: str = Field(min_length=1, max_length=100)
    cam_pass: str = Field(min_length=1, max_length=100)
    cam_strm1: str = Field(
        min_length=1, max_length=100, description="Primary stream URL (RTSP/RTMP)"
    )
    cam_strm2: str | None = Field(default=None, max_length=100)
    cam_strm3: str | None = Field(default=None, max_length=100)
    cam_onvif: int | None = Field(default=None, description="ONVIF port (e.g. 80 or 8080)")
    motion_active: bool = Field(default=False)
    com_id: int = Field(description="Customer/company ID")
    device_id: int = Field(description="Edge device DB ID")
    strm_type_id: int | None = Field(default=None, description="Stream type FK")

    @field_validator("cam_strm1")
    @classmethod
    def validate_stream_url(cls, v: str) -> str:
        lower = v.lower()
        if not (
            lower.startswith("rtsp://")
            or lower.startswith("rtmp://")
            or lower.startswith("publisher")
        ):
            raise ValueError("Stream URL must start with rtsp://, rtmp://, or be 'publisher'")
        return v


class CameraUpdateRequest(BaseModel):
    """Request body for PATCH /cameras/{cam_id}."""

    model_config = ConfigDict(str_strip_whitespace=True)

    cam_name: str | None = Field(default=None, max_length=100)
    cam_loc: str | None = Field(default=None, max_length=300)
    cam_make: str | None = Field(default=None, max_length=100)
    cam_usrname: str | None = Field(default=None, max_length=100)
    cam_pass: str | None = Field(default=None, max_length=100)
    cam_strm1: str | None = Field(default=None, max_length=100)
    cam_strm2: str | None = None
    cam_strm3: str | None = None
    cam_onvif: int | None = None
    motion_active: bool | None = None
    is_active: bool | None = None


class CameraResponse(BaseModel):
    """Full camera record response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cam_id: str | None
    cam_name: str
    cam_loc: str
    cam_make: str
    cam_usrname: str
    # cam_pass intentionally excluded — never expose credentials in API responses
    cam_strm1: str
    cam_strm2: str | None
    cam_strm3: str | None
    cam_onvif: int | None
    is_active: bool
    motion_active: bool
    upd_time: datetime
    com_id: int
    cir_id: int
    ba_id: int
    device_id: int
    strm_type_id: int | None


class CameraListItem(BaseModel):
    """Compact camera item for list views."""

    model_config = ConfigDict(from_attributes=True)

    cam_id: str | None
    cam_name: str
    cam_loc: str
    is_active: bool
    motion_active: bool
    com_id: int


class StreamTokenResponse(BaseModel):
    """Short-lived JWT for HLS stream access."""

    cam_id: str
    stream_url: str
    token: str
    expires_in: int  # seconds