"""
app/api/v1/__init__.py
Aggregates all v1 routers into a single router mounted at /api/v1.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.cameras import router as cameras_router
from app.api.v1.customers import plans_router as plans_router
from app.api.v1.customers import router as customers_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.devices import router as devices_router
from app.api.v1.geography import router as geography_router
from app.api.v1.health import router as health_router
from app.api.v1.motion import router as motion_router
from app.api.v1.recordings import router as recordings_router
from app.api.v1.users import router as users_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(users_router)
v1_router.include_router(cameras_router)
v1_router.include_router(customers_router)
v1_router.include_router(plans_router)
v1_router.include_router(geography_router)
v1_router.include_router(recordings_router)
v1_router.include_router(motion_router)
v1_router.include_router(devices_router)
v1_router.include_router(dashboard_router)
