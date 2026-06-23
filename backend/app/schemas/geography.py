"""
app/schemas/geography.py
Pydantic V2 schemas for circle_master and ba_master — the top-level
BSNL geographic hierarchy. Used to populate circle/BA dropdowns and
for sysadmin-only hierarchy management.
"""

from pydantic import BaseModel, ConfigDict, Field


class CircleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cir_name: str
    cir_code: str


class CircleCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    cir_name: str = Field(min_length=1, max_length=100)
    cir_code: str = Field(min_length=1, max_length=20)


class BAResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ba_name: str
    ba_code: str
    cir_id: int


class BACreateRequest(BaseModel):
    """cir_id is taken from the URL path, not the body — see POST /circles/{cir_id}/bas."""

    model_config = ConfigDict(str_strip_whitespace=True)

    ba_name: str = Field(min_length=1, max_length=100)
    ba_code: str = Field(min_length=1, max_length=20)
