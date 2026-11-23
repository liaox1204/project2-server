"""API 路由聚合。"""
from fastapi import APIRouter

from routers import auth, users, family, health, services, orders, reminders, emergency, ai, notify, admin, vip

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(family.router)
api_router.include_router(health.router)
api_router.include_router(services.router)
api_router.include_router(orders.router)
api_router.include_router(reminders.router)
api_router.include_router(emergency.router)
api_router.include_router(ai.router)
api_router.include_router(notify.router)
api_router.include_router(admin.router)
api_router.include_router(vip.router)
