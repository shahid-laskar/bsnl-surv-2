"""
app/api/v1/geography.py
Read-only BSNL hierarchy lookups (circles, BAs) used to populate
circle/BA/customer dropdowns, plus sysadmin-only hierarchy management.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user, require_role
from app.core.exceptions import ConflictError, NotFoundError
from app.models.geography import ba_master, circle_master
from app.schemas.customer import CustomerListItem
from app.schemas.geography import BACreateRequest, BAResponse, CircleCreateRequest, CircleResponse
from app.services.customer_service import CustomerService

router = APIRouter(tags=["geography"])


@router.get("/circles", response_model=list[CircleResponse], summary="List circles")
async def list_circles(
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CircleResponse]:
    """Reference data — any authenticated user can list circles (used for dropdowns)."""
    result = await db.execute(select(circle_master).order_by(circle_master.cir_name))
    return [CircleResponse.model_validate(c) for c in result.scalars().all()]


@router.post(
    "/circles",
    response_model=CircleResponse,
    status_code=201,
    dependencies=[Depends(require_role("sysadmin"))],
    summary="Create circle (sysadmin only)",
)
async def create_circle(
    body: CircleCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> CircleResponse:
    existing = await db.execute(select(circle_master).where(circle_master.cir_code == body.cir_code))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"Circle code '{body.cir_code}' already exists")

    circle = circle_master(cir_name=body.cir_name, cir_code=body.cir_code)
    db.add(circle)
    await db.flush()
    return CircleResponse.model_validate(circle)


@router.get(
    "/circles/{cir_id}/bas", response_model=list[BAResponse], summary="List BAs for a circle"
)
async def list_bas_for_circle(
    cir_id: int,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BAResponse]:
    circle_result = await db.execute(select(circle_master).where(circle_master.id == cir_id))
    if circle_result.scalar_one_or_none() is None:
        raise NotFoundError(f"Circle {cir_id} not found")

    result = await db.execute(
        select(ba_master).where(ba_master.cir_id == cir_id).order_by(ba_master.ba_name)
    )
    return [BAResponse.model_validate(b) for b in result.scalars().all()]


@router.post(
    "/circles/{cir_id}/bas",
    response_model=BAResponse,
    status_code=201,
    dependencies=[Depends(require_role("sysadmin"))],
    summary="Create BA under a circle (sysadmin only)",
)
async def create_ba(
    cir_id: int,
    body: BACreateRequest,
    db: AsyncSession = Depends(get_db),
) -> BAResponse:
    circle_result = await db.execute(select(circle_master).where(circle_master.id == cir_id))
    if circle_result.scalar_one_or_none() is None:
        raise NotFoundError(f"Circle {cir_id} not found")

    existing = await db.execute(
        select(ba_master).where(ba_master.cir_id == cir_id, ba_master.ba_code == body.ba_code)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError(f"BA code '{body.ba_code}' already exists in this circle")

    ba = ba_master(ba_name=body.ba_name, ba_code=body.ba_code, cir_id=cir_id)
    db.add(ba)
    await db.flush()
    return BAResponse.model_validate(ba)


@router.get(
    "/bas/{ba_id}/customers",
    response_model=list[CustomerListItem],
    summary="List customers for a BA",
)
async def list_customers_for_ba(
    ba_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CustomerListItem]:
    """
    Role scoping is delegated to CustomerService.list_for_user — a circle_admin
    or ba_admin outside this BA's circle simply gets an empty list, not a 403,
    since the BA itself is shared reference data.
    """
    ba_result = await db.execute(select(ba_master).where(ba_master.id == ba_id))
    if ba_result.scalar_one_or_none() is None:
        raise NotFoundError(f"BA {ba_id} not found")

    service = CustomerService(db)
    customers, _ = await service.list_for_user(current_user, ba_id=ba_id, offset=0, limit=200)
    return [CustomerListItem.model_validate(c) for c in customers]