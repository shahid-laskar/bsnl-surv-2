"""
app/schemas/device.py
Pydantic schemas for edge devices.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: str = Field(min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=100)
    dev_name: str = Field(min_length=1, max_length=100)
    dev_loc: str = Field(min_length=1, max_length=300)


class DeviceUpdateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    staging_status: str | None = None
    status_log: str | None = None
    mqtt_status: str | None = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    username: str
    dev_name: str
    dev_loc: str
    is_active: bool
    staging_status: str | None
    status_log: str | None
    mqtt_status: str | None
    mqtt_update: datetime | None
    upd_time: datetime
    com_id: int
    cir_id: int
    ba_id: int


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    total: int
