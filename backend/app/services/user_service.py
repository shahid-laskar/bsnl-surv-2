# app/services/user_service.py
#
# Key fixes vs. previous version:
#   1. create(): cust_admin and viewer MUST have com_id set — validated here.
#   2. create(): com_id is verified to actually exist in customer_master via
#      CustomerService.assert_customer_exists() before the row is inserted.
#   3. create(): cir_id / ba_id are auto-inherited from the customer when the
#      new user is a cust_admin or viewer (matching BSNL hierarchy).
#   4. update(): same com_id existence check when com_id is being changed.

from datetime import datetime, UTC
import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, ConflictError, NotFoundError, BadRequestError
from app.core.security import hash_password
from app.models.auth import SvUser, SvKongConsumer, SvRefreshToken
from app.models.customer import customer_master
from app.schemas.auth import UserCreateRequest, UserUpdateRequest
from app.services.kong_service import KongService

logger = structlog.get_logger(__name__)

# Roles that MUST be attached to a specific customer company.
CUSTOMER_ROLES = {"cust_admin", "viewer"}
# Roles that belong to BSNL (admin hierarchy), must NOT have com_id.
BSNL_ADMIN_ROLES = {"sysadmin", "circle_admin", "ba_admin"}


class UserService:
    def __init__(self, db: AsyncSession, kong: KongService) -> None:
        self._db = db
        self._kong = kong

    async def get_by_id(self, user_id: int) -> SvUser | None:
        result = await self._db.execute(select(SvUser).where(SvUser.id == user_id))
        return result.scalar_one_or_none()

    async def _get_or_raise(self, user_id: int) -> SvUser:
        user = await self.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        return user

    async def _username_exists(self, username: str, exclude_id: int | None = None) -> bool:
        query = select(SvUser).where(SvUser.username == username)
        if exclude_id is not None:
            query = query.where(SvUser.id != exclude_id)
        result = await self._db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _email_exists(self, email: str, exclude_id: int | None = None) -> bool:
        query = select(SvUser).where(SvUser.email == email)
        if exclude_id is not None:
            query = query.where(SvUser.id != exclude_id)
        result = await self._db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _get_customer(self, com_id: int) -> customer_master | None:
        result = await self._db.execute(select(customer_master).where(customer_master.id == com_id))
        return result.scalar_one_or_none()

    async def _assert_customer_exists(self, com_id: int) -> customer_master:
        """Raise NotFoundError if the customer does not exist."""
        customer = await self._get_customer(com_id)
        if customer is None:
            raise NotFoundError(f"Customer (company) ID {com_id} not found")
        return customer

    # ── Role-specific invariants ──────────────────────────────────────────────

    def _assert_role_scope_invariants(
        self,
        role: str,
        com_id: int | None,
        cir_id: int | None,
        ba_id: int | None,
    ) -> None:
        """
        Enforce BSNL hierarchy rules on user creation:
        - cust_admin / viewer  → com_id REQUIRED, cir_id/ba_id optional
          (they'll be inherited from the customer if not set explicitly)
        - circle_admin         → cir_id REQUIRED, com_id must be None
        - ba_admin             → cir_id + ba_id REQUIRED, com_id must be None
        - sysadmin             → no scope restrictions
        """
        if role in CUSTOMER_ROLES:
            if not com_id:
                raise BadRequestError(
                    f"Role '{role}' requires a customer company (com_id) to be specified"
                )
            if com_id and (cir_id or ba_id):
                # Caller may pass cir_id/ba_id explicitly; we'll validate they match
                # the customer's circle/BA in create().  Allowing it here is fine.
                pass
        elif role == "circle_admin":
            if not cir_id:
                raise BadRequestError("circle_admin role requires cir_id to be specified")
            if com_id:
                raise BadRequestError("circle_admin must not be associated with a customer company")
        elif role == "ba_admin":
            if not cir_id or not ba_id:
                raise BadRequestError(
                    "ba_admin role requires both cir_id and ba_id to be specified"
                )
            if com_id:
                raise BadRequestError("ba_admin must not be associated with a customer company")
        # sysadmin: no constraints

    def _validate_creation_permission(self, creator: SvUser, request: UserCreateRequest) -> None:
        if creator.role == "sysadmin":
            return  # sysadmin can create any user

        if creator.role == "circle_admin":
            if request.role not in ("ba_admin", "cust_admin", "viewer"):
                raise ForbiddenError(
                    "circle_admin cannot create users with sysadmin or circle_admin role"
                )
            if request.cir_id != creator.cir_id:
                raise ForbiddenError("circle_admin can only create users in their own circle")
            return

        if creator.role == "ba_admin":
            if request.role not in ("cust_admin", "viewer"):
                raise ForbiddenError(
                    "ba_admin cannot create users with roles other than cust_admin or viewer"
                )
            if request.cir_id != creator.cir_id or request.ba_id != creator.ba_id:
                raise ForbiddenError("ba_admin can only create users in their own circle and BA")
            return

        if creator.role == "cust_admin":
            if request.role != "viewer":
                raise ForbiddenError("cust_admin can only create users with viewer role")
            # The new viewer must belong to the same customer as the cust_admin
            if request.com_id != creator.com_id:
                raise ForbiddenError(
                    "cust_admin can only create users belonging to their own company"
                )
            return

        raise ForbiddenError("Role not permitted to create users")

    def _validate_update_permission(
        self, updater: SvUser, target: SvUser, request: UserUpdateRequest
    ) -> None:
        # Self updates
        if updater.id == target.id:
            if request.role is not None and request.role != target.role:
                raise ForbiddenError("Cannot change your own role")
            if request.is_active is not None and request.is_active != target.is_active:
                raise ForbiddenError("Cannot deactivate your own account")
            if (
                (request.cir_id is not None and request.cir_id != target.cir_id)
                or (request.ba_id is not None and request.ba_id != target.ba_id)
                or (request.com_id is not None and request.com_id != target.com_id)
            ):
                raise ForbiddenError("Cannot change your own scope")
            return

        if updater.role == "sysadmin":
            return

        if updater.role == "circle_admin":
            if target.role in ("sysadmin", "circle_admin") or target.is_superuser:
                raise ForbiddenError("circle_admin cannot update sysadmin or circle_admin users")
            if target.cir_id != updater.cir_id:
                raise ForbiddenError("circle_admin can only update users in their own circle")
            if request.role is not None and request.role not in (
                "ba_admin",
                "cust_admin",
                "viewer",
            ):
                raise ForbiddenError("Invalid target role for circle_admin")
            if request.cir_id is not None and request.cir_id != updater.cir_id:
                raise ForbiddenError("Cannot assign user outside of your circle")
            return

        if updater.role == "ba_admin":
            if target.role in ("sysadmin", "circle_admin", "ba_admin") or target.is_superuser:
                raise ForbiddenError("ba_admin cannot update users with higher or equal roles")
            if target.cir_id != updater.cir_id or target.ba_id != updater.ba_id:
                raise ForbiddenError("ba_admin can only update users in their own circle and BA")
            if request.role is not None and request.role not in ("cust_admin", "viewer"):
                raise ForbiddenError("Invalid target role for ba_admin")
            if (request.cir_id is not None and request.cir_id != updater.cir_id) or (
                request.ba_id is not None and request.ba_id != updater.ba_id
            ):
                raise ForbiddenError("Cannot assign user outside of your circle/BA")
            return

        if updater.role == "cust_admin":
            if target.role != "viewer" or target.is_superuser:
                raise ForbiddenError("cust_admin can only update viewer users")
            if target.com_id != updater.com_id:
                raise ForbiddenError("cust_admin can only update users in their own company")
            if request.role is not None and request.role != "viewer":
                raise ForbiddenError("Invalid target role for cust_admin")
            if (
                (request.cir_id is not None and request.cir_id != updater.cir_id)
                or (request.ba_id is not None and request.ba_id != updater.ba_id)
                or (request.com_id is not None and request.com_id != updater.com_id)
            ):
                raise ForbiddenError("Cannot assign user outside of your company/BA/circle")
            return

        raise ForbiddenError("Role not permitted to update users")

    def _validate_deactivation_permission(self, deactivated_by: SvUser, target: SvUser) -> None:
        if deactivated_by.role == "sysadmin":
            return

        if deactivated_by.role == "circle_admin":
            if target.role in ("sysadmin", "circle_admin") or target.is_superuser:
                raise ForbiddenError(
                    "circle_admin cannot deactivate sysadmin or circle_admin users"
                )
            if target.cir_id != deactivated_by.cir_id:
                raise ForbiddenError("circle_admin can only deactivate users in their own circle")
            return

        if deactivated_by.role == "ba_admin":
            if target.role in ("sysadmin", "circle_admin", "ba_admin") or target.is_superuser:
                raise ForbiddenError("ba_admin cannot deactivate users with higher or equal roles")
            if target.cir_id != deactivated_by.cir_id or target.ba_id != deactivated_by.ba_id:
                raise ForbiddenError("ba_admin can only deactivate users in their own BA")
            return

        if deactivated_by.role == "cust_admin":
            if target.role != "viewer" or target.is_superuser:
                raise ForbiddenError("cust_admin can only deactivate viewer users")
            if target.com_id != deactivated_by.com_id:
                raise ForbiddenError("cust_admin can only deactivate users in their own company")
            return

        raise ForbiddenError("Role not permitted to deactivate users")

    # ── CRUD ─────────────────────────────────────────────────────────────────

    async def create(self, request: UserCreateRequest, created_by: SvUser) -> SvUser:
        """Create a new user and provision a Kong consumer."""
        # 1. Role/scope invariant check
        self._assert_role_scope_invariants(
            request.role, request.com_id, request.cir_id, request.ba_id
        )

        # 2. Caller permission check
        self._validate_creation_permission(created_by, request)

        # 3. Uniqueness checks
        if await self._username_exists(request.username):
            raise ConflictError(f"Username '{request.username}' already taken")
        if await self._email_exists(request.email):
            raise ConflictError(f"Email '{request.email}' already registered")

        # 4. For customer-level roles, verify the customer exists and inherit
        #    cir_id/ba_id from the customer record so we never have a mismatch.
        effective_cir_id = request.cir_id
        effective_ba_id = request.ba_id
        effective_com_id = request.com_id

        if request.role in CUSTOMER_ROLES:
            customer = await self._assert_customer_exists(request.com_id)  # type: ignore[arg-type]
            # Inherit circle/BA from customer to guarantee hierarchy consistency
            effective_cir_id = customer.cir_id
            effective_ba_id = customer.ba_id
            effective_com_id = customer.id
            # If caller explicitly supplied cir_id/ba_id, they must match
            if request.cir_id and request.cir_id != customer.cir_id:
                raise BadRequestError(
                    f"cir_id {request.cir_id} does not match the customer's circle "
                    f"{customer.cir_id}"
                )
            if request.ba_id and request.ba_id != customer.ba_id:
                raise BadRequestError(
                    f"ba_id {request.ba_id} does not match the customer's BA {customer.ba_id}"
                )

        password_hash = hash_password(request.password)

        user = SvUser(
            username=request.username,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            password_hash=password_hash,
            role=request.role,
            com_id=effective_com_id,
            cir_id=effective_cir_id,
            ba_id=effective_ba_id,
            is_active=True,
        )
        self._db.add(user)
        await self._db.flush()  # Get user.id before calling Kong service

        # Provision Kong consumer
        consumer_username, jwt_key = await self._kong.create_consumer_and_credential(user.id)

        self._db.add(
            SvKongConsumer(
                user_id=user.id,
                kong_consumer_username=consumer_username,
                jwt_key=jwt_key,
                is_active=True,
            )
        )

        await self._db.commit()
        logger.info("user.created", user_id=user.id, role=user.role, created_by=created_by.id)
        return user

    async def update(self, user_id: int, request: UserUpdateRequest, updated_by: SvUser) -> SvUser:
        """Update user properties."""
        user = await self._get_or_raise(user_id)
        self._validate_update_permission(updated_by, user, request)

        if request.email is not None and request.email != user.email:
            if await self._email_exists(request.email, exclude_id=user_id):
                raise ConflictError(f"Email '{request.email}' already registered")
            user.email = request.email

        # If changing com_id, verify the new customer exists and re-sync circle/BA
        if request.com_id is not None and request.com_id != user.com_id:
            customer = await self._assert_customer_exists(request.com_id)
            user.com_id = customer.id
            user.cir_id = customer.cir_id
            user.ba_id = customer.ba_id
        else:
            if request.first_name is not None:
                user.first_name = request.first_name
            if request.last_name is not None:
                user.last_name = request.last_name
            if request.role is not None:
                user.role = request.role
            if request.cir_id is not None:
                user.cir_id = request.cir_id
            if request.ba_id is not None:
                user.ba_id = request.ba_id

        if request.first_name is not None:
            user.first_name = request.first_name
        if request.last_name is not None:
            user.last_name = request.last_name
        if request.role is not None:
            user.role = request.role

        if request.is_active is not None:
            if not request.is_active and user.is_active:
                await self.deactivate(user_id, updated_by)
                return user
            else:
                user.is_active = request.is_active

        await self._db.commit()
        logger.info("user.updated", user_id=user_id, by=updated_by.id)
        return user

    async def deactivate(self, user_id: int, deactivated_by: SvUser) -> None:
        """Soft-delete a user, delete Kong consumer, and revoke refresh tokens."""
        user = await self._get_or_raise(user_id)

        if user.id == deactivated_by.id:
            raise ForbiddenError("Cannot deactivate your own account")

        self._validate_deactivation_permission(deactivated_by, user)

        user.is_active = False

        # Delete Kong consumer
        result = await self._db.execute(
            select(SvKongConsumer)
            .where(SvKongConsumer.user_id == user_id)
            .where(SvKongConsumer.is_active == True)  # noqa: E712
        )
        consumer = result.scalar_one_or_none()
        if consumer:
            await self._kong.delete_consumer(consumer.kong_consumer_username)
            consumer.is_active = False

        # Revoke all refresh tokens
        await self._db.execute(
            update(SvRefreshToken)
            .where(SvRefreshToken.user_id == user_id)
            .values(revoked=True, revoked_at=datetime.now(UTC))
        )

        await self._db.commit()
        logger.info("user.deactivated", user_id=user_id, by=deactivated_by.id)

    async def list_users(self, current_user: SvUser) -> list[SvUser]:
        """List users matching the current user's role scope."""
        query = select(SvUser)
        if current_user.role == "sysadmin":
            pass
        elif current_user.role == "circle_admin":
            query = query.where(SvUser.cir_id == current_user.cir_id)
        elif current_user.role == "ba_admin":
            query = query.where(
                SvUser.cir_id == current_user.cir_id, SvUser.ba_id == current_user.ba_id
            )
        elif current_user.role == "cust_admin":
            query = query.where(SvUser.com_id == current_user.com_id)
        else:
            # viewer can only see themselves
            query = query.where(SvUser.id == current_user.id)

        result = await self._db.execute(query)
        return list(result.scalars().all())
