"""
app/schemas/customer.py
Pydantic V2 schemas for customer_master (tenant/company) and plan_master.

Field names match the SQLAlchemy model attributes exactly.
CustomerResponse and CustomerListItem now include the joined fields
(cir_name, ba_name, plan_name, camera_count, camera_limit) that the
frontend CustomersPage.tsx and geography dropdowns need.
"""

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreateRequest(BaseModel):
    """Request body for POST /customers."""

    model_config = ConfigDict(str_strip_whitespace=True)

    com_name: str = Field(min_length=1, max_length=255)
    com_adr: str = Field(min_length=1, max_length=500)
    gstn: str | None = Field(default=None, max_length=15)
    cir_id: int = Field(description="Circle ID")
    ba_id: int = Field(description="BA ID — must belong to cir_id")
    plan_id: int = Field(description="Subscription plan ID")


class CustomerUpdateRequest(BaseModel):
    """Request body for PATCH /customers/{id}. cir_id/ba_id are immutable."""

    model_config = ConfigDict(str_strip_whitespace=True)

    com_name: str | None = Field(default=None, max_length=255)
    com_adr: str | None = Field(default=None, max_length=500)
    gstn: str | None = Field(default=None, max_length=15)
    plan_id: int | None = None


class PlanResponse(BaseModel):
    """Subscription plan — defines camera limits."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_name: str
    cam_limit: int


class CustomerResponse(BaseModel):
    """
    Full customer record response — includes circle/BA/plan names and camera stats.
    These are populated by CustomerService.get_by_id_with_details().
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    com_name: str
    com_adr: str
    gstn: str | None
    cir_id: int
    ba_id: int
    plan_id: int
    # Joined / computed — always populated by the service layer
    cir_name: str = ""
    ba_name: str = ""
    plan_name: str = ""
    camera_count: int = 0
    camera_limit: int = 0


class CustomerListItem(BaseModel):
    """
    Compact customer item for list views — includes the joined name columns
    and camera usage so the table can render without extra API calls.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    com_name: str
    com_adr: str
    gstn: str | None = None
    cir_id: int
    ba_id: int
    plan_id: int
    cir_name: str = ""
    ba_name: str = ""
    plan_name: str = ""
    camera_count: int = 0
    camera_limit: int = 0