# app/schemas/auth.py
#
# UserCreateRequest now documents which scope fields are required for each role:
#   sysadmin       → no com_id/cir_id/ba_id required
#   circle_admin   → cir_id required, no com_id
#   ba_admin       → cir_id + ba_id required, no com_id
#   cust_admin     → com_id required (cir_id/ba_id auto-inherited from customer)
#   viewer         → com_id required (cir_id/ba_id auto-inherited from customer)
#
# The enforcement is in UserService._assert_role_scope_invariants().

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    device_id: str | None = None  # For mobile clients


class UserInResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    com_id: int | None
    cir_id: int | None
    ba_id: int | None
    is_active: bool
    date_joined: datetime


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserInResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(default="")
    last_name: str = Field(default="")
    role: str = Field(pattern="^(sysadmin|circle_admin|ba_admin|cust_admin|viewer)$")
    # Scope fields — which ones are required depends on role; enforced in UserService.
    # cust_admin / viewer:  com_id required; cir_id + ba_id inherited from customer.
    # circle_admin:         cir_id required; com_id must be omitted.
    # ba_admin:             cir_id + ba_id required; com_id must be omitted.
    # sysadmin:             all optional.
    com_id: int | None = None
    cir_id: int | None = None
    ba_id: int | None = None


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = Field(
        default=None, pattern="^(sysadmin|circle_admin|ba_admin|cust_admin|viewer)$"
    )
    com_id: int | None = None
    cir_id: int | None = None
    ba_id: int | None = None
    is_active: bool | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class DeviceTokenRequest(BaseModel):
    token: str = Field(min_length=1)
    platform: str = Field(pattern="^(android|ios|web)$")
