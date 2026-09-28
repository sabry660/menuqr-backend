from fastapi import APIRouter

from app.api.v1 import (
    ai,
    audit_logs,
    auth,
    branches,
    invitations,
    members,
    menu_items,
    menus,
    public,
    qr_codes,
    restaurants,
    subscriptions,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(restaurants.router)
api_router.include_router(branches.router)
api_router.include_router(members.router)
api_router.include_router(invitations.router)
api_router.include_router(invitations.public_router)
api_router.include_router(menus.router)
api_router.include_router(menus.categories_router)
api_router.include_router(menu_items.router)
api_router.include_router(qr_codes.router)
api_router.include_router(subscriptions.router)
api_router.include_router(audit_logs.router)
api_router.include_router(public.router)
api_router.include_router(ai.router)
