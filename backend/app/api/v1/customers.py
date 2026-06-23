"""
app/api/v1/customers.py
Customer (tenant/company) CRUD endpoints, plus a read-only plans lookup.

Write operations require sysadmin, circle_admin, or ba_admin — scoped to
their own circle/BA (enforced in CustomerService). Read operations are
scoped per role in the service layer, same pattern as UserService.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_any_role
from app.models.customer import plan_master
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.customer import (
    CustomerCreateRequest,
    CustomerListItem,
    CustomerResponse,
    CustomerUpdateRequest,
    PlanResponse,
)
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])

# Separate, unprefixed router for plan lookups — plans aren't a sub-resource
# of a single customer, they're shared reference data used when creating one.
plans_router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=PaginatedResponse[CustomerListItem], summary="List customers")
async def list_customers(
    ba_id: int | None = Query(default=None, description="Filter by BA ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[CustomerListItem]:
    """List customers, scoped to the caller's role (circle/BA/own company)."""
    params = PaginationParams(page=page, page_size=page_size)
    service = CustomerService(db)
    customers, total = await service.list_for_user(
        current_user, ba_id=ba_id, offset=params.offset, limit=params.page_size
    )
    items = [CustomerListItem.model_validate(c) for c in customers]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=201,
    dependencies=[Depends(require_any_role("sysadmin", "circle_admin", "ba_admin"))],
    summary="Create customer",
)
async def create_customer(
    body: CustomerCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    """
    Register a new customer/company under a circle + BA + subscription plan.
    circle_admin/ba_admin are restricted to their own circle/BA by the service layer.
    """
    service = CustomerService(db)
    customer = await service.create(body, created_by=current_user)
    return CustomerResponse.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerResponse, summary="Get customer")
async def get_customer(
    customer_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    service = CustomerService(db)
    customer = await service.get_by_id(customer_id)
    service.assert_view_permission(current_user, customer)
    return CustomerResponse.model_validate(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(require_any_role("sysadmin", "circle_admin", "ba_admin"))],
    summary="Update customer",
)
async def update_customer(
    customer_id: int,
    body: CustomerUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CustomerResponse:
    """Partial update. cir_id/ba_id are immutable via this endpoint."""
    service = CustomerService(db)
    customer = await service.update(customer_id, body, updated_by=current_user)
    return CustomerResponse.model_validate(customer)


# ── Plans lookup ───────────────────────────────────────────────────────────────


@plans_router.get("", response_model=list[PlanResponse], summary="List subscription plans")
async def list_plans(
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlanResponse]:
    """Reference data — any authenticated user can list plans (used when creating a customer)."""
    result = await db.execute(select(plan_master).order_by(plan_master.cam_limit))
    return [PlanResponse.model_validate(p) for p in result.scalars().all()]
