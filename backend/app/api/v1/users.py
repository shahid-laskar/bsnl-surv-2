# app/api/v1/users.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, CurrentUser, require_any_role
from app.schemas.auth import UserCreateRequest, UserUpdateRequest, UserInResponse
from app.services.user_service import UserService
from app.services.kong_service import KongService

router = APIRouter(prefix="/users", tags=["users"])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db=db, kong=KongService())


@router.post("/", response_model=UserInResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    current_user: CurrentUser = Depends(
        require_any_role("sysadmin", "circle_admin", "ba_admin", "cust_admin")
    ),
    service: UserService = Depends(get_user_service),
) -> UserInResponse:
    """Create a new user."""
    user = await service.create(body, current_user)
    return UserInResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserInResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserInResponse:
    """Update user properties."""
    user = await service.update(user_id, body, current_user)
    return UserInResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: int,
    current_user: CurrentUser = Depends(
        require_any_role("sysadmin", "circle_admin", "ba_admin", "cust_admin")
    ),
    service: UserService = Depends(get_user_service),
) -> None:
    """Deactivate a user account."""
    await service.deactivate(user_id, current_user)


@router.get("/", response_model=list[UserInResponse])
async def list_users(
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> list[UserInResponse]:
    """List users within the requester's scope."""
    users = await service.list_users(current_user)
    return [UserInResponse.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserInResponse)
async def get_user(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
) -> UserInResponse:
    """Get details of a single user."""
    user = await service.get_by_id(user_id)
    if not user:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("User not found")

    # Check permission to view this user
    if current_user.role != "sysadmin":
        if current_user.role == "circle_admin" and user.cir_id != current_user.cir_id:
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Permission denied to view user")
        elif current_user.role == "ba_admin" and (
            user.cir_id != current_user.cir_id or user.ba_id != current_user.ba_id
        ):
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Permission denied to view user")
        elif current_user.role == "cust_admin" and user.com_id != current_user.com_id:
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Permission denied to view user")
        elif current_user.role == "viewer" and user.id != current_user.id:
            from app.core.exceptions import ForbiddenError

            raise ForbiddenError("Permission denied to view user")

    return UserInResponse.model_validate(user)
