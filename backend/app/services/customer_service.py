"""
app/services/customer_service.py
Business logic for customer_master (tenant/company) CRUD.

Role scoping mirrors UserService:
  sysadmin     → full access, any circle/BA
  circle_admin → customers within their own circle
  ba_admin     → customers within their own circle + BA
  cust_admin   → read-only, their own company only
  viewer       → read-only, their own company only
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, CustomerNotFoundError, ForbiddenError, NotFoundError
from app.models.auth import SvUser
from app.models.customer import customer_master, plan_master
from app.models.geography import ba_master, circle_master
from app.schemas.customer import CustomerCreateRequest, CustomerUpdateRequest

logger = structlog.get_logger(__name__)


class CustomerService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_by_id(self, customer_id: int) -> customer_master:
        result = await self._db.execute(
            select(customer_master).where(customer_master.id == customer_id)
        )
        customer = result.scalar_one_or_none()
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    async def list_for_user(
        self,
        current_user: SvUser,
        ba_id: int | None = None,
        offset: int = 0,
        limit: int = 25,
    ) -> tuple[list[customer_master], int]:
        """Role-scoped customer list, optionally narrowed to a single BA."""
        q = select(customer_master)

        if current_user.role == "sysadmin":
            pass
        elif current_user.role == "circle_admin":
            q = q.where(customer_master.cir_id == current_user.cir_id)
        elif current_user.role == "ba_admin":
            q = q.where(
                customer_master.cir_id == current_user.cir_id,
                customer_master.ba_id == current_user.ba_id,
            )
        else:
            # cust_admin / viewer — scoped to their own company only
            q = q.where(customer_master.id == current_user.com_id)

        if ba_id is not None:
            q = q.where(customer_master.ba_id == ba_id)

        count_result = await self._db.execute(select(func.count()).select_from(q.subquery()))
        total = count_result.scalar_one()

        result = await self._db.execute(
            q.order_by(customer_master.com_name).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def create(self, data: CustomerCreateRequest, created_by: SvUser) -> customer_master:
        self._validate_creation_permission(created_by, data)
        await self._assert_circle_ba_plan_exist(data.cir_id, data.ba_id, data.plan_id)

        customer = customer_master(
            com_name=data.com_name,
            com_adr=data.com_adr,
            gstn=data.gstn,
            cir_id=data.cir_id,
            ba_id=data.ba_id,
            plan_id=data.plan_id,
        )
        self._db.add(customer)
        await self._db.flush()  # Get PK without committing transaction
        logger.info("customer.created", com_id=customer.id, created_by=created_by.id)
        return customer

    async def update(
        self, customer_id: int, data: CustomerUpdateRequest, updated_by: SvUser
    ) -> customer_master:
        """Partial update — cir_id/ba_id are immutable here; moving a company
        between circles/BAs is a deliberate sysadmin-only operation, not exposed yet."""
        customer = await self.get_by_id(customer_id)
        self._validate_update_permission(updated_by, customer)

        if data.plan_id is not None:
            await self._assert_plan_exists(data.plan_id)

        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(customer, field, value)

        await self._db.flush()
        logger.info(
            "customer.updated",
            com_id=customer_id,
            by=updated_by.id,
            fields=list(update_data.keys()),
        )
        return customer

    # ── Permission helpers ────────────────────────────────────────────────────

    def _validate_creation_permission(self, creator: SvUser, data: CustomerCreateRequest) -> None:
        if creator.role == "sysadmin":
            return
        if creator.role == "circle_admin":
            if data.cir_id != creator.cir_id:
                raise ForbiddenError("circle_admin can only create customers in their own circle")
            return
        if creator.role == "ba_admin":
            if data.cir_id != creator.cir_id or data.ba_id != creator.ba_id:
                raise ForbiddenError(
                    "ba_admin can only create customers in their own circle and BA"
                )
            return
        raise ForbiddenError("Role not permitted to create customers")

    def _validate_update_permission(self, updater: SvUser, customer: customer_master) -> None:
        if updater.role == "sysadmin":
            return
        if updater.role == "circle_admin":
            if customer.cir_id != updater.cir_id:
                raise ForbiddenError("circle_admin can only update customers in their own circle")
            return
        if updater.role == "ba_admin":
            if customer.cir_id != updater.cir_id or customer.ba_id != updater.ba_id:
                raise ForbiddenError(
                    "ba_admin can only update customers in their own circle and BA"
                )
            return
        raise ForbiddenError("Role not permitted to update customers")

    def assert_view_permission(self, viewer: SvUser, customer: customer_master) -> None:
        """Raise ForbiddenError if `viewer` cannot see `customer`."""
        if viewer.role == "sysadmin":
            return
        if viewer.role == "circle_admin":
            if customer.cir_id != viewer.cir_id:
                raise ForbiddenError("Access to this company is not permitted for your account")
            return
        if viewer.role == "ba_admin":
            if customer.cir_id != viewer.cir_id or customer.ba_id != viewer.ba_id:
                raise ForbiddenError("Access to this company is not permitted for your account")
            return
        # cust_admin / viewer
        if customer.id != viewer.com_id:
            raise ForbiddenError("Access to this company is not permitted for your account")

    # ── Existence / referential checks ───────────────────────────────────────

    async def _assert_circle_ba_plan_exist(self, cir_id: int, ba_id: int, plan_id: int) -> None:
        cir_result = await self._db.execute(select(circle_master).where(circle_master.id == cir_id))
        if cir_result.scalar_one_or_none() is None:
            raise NotFoundError(f"Circle {cir_id} not found")

        ba_result = await self._db.execute(select(ba_master).where(ba_master.id == ba_id))
        ba = ba_result.scalar_one_or_none()
        if ba is None:
            raise NotFoundError(f"BA {ba_id} not found")
        if ba.cir_id != cir_id:
            raise ConflictError(f"BA {ba_id} does not belong to circle {cir_id}")

        await self._assert_plan_exists(plan_id)

    async def _assert_plan_exists(self, plan_id: int) -> None:
        plan_result = await self._db.execute(select(plan_master).where(plan_master.id == plan_id))
        if plan_result.scalar_one_or_none() is None:
            raise NotFoundError(f"Plan {plan_id} not found")