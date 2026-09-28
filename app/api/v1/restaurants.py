import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.common import Page, PaginationParams
from app.schemas.restaurant import (
    RestaurantCreate,
    RestaurantOut,
    RestaurantSettingsOut,
    RestaurantSettingsUpdate,
    RestaurantUpdate,
)
from app.services import restaurant_service

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.post("", response_model=RestaurantOut, status_code=status.HTTP_201_CREATED, summary="Create a restaurant")
async def create_restaurant(
    payload: RestaurantCreate,
    ctx: TenantContext = Depends(require_permission(Perm.RESTAURANT_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await restaurant_service.create_restaurant(db, tenant_id=ctx.tenant_id, actor_id=ctx.user.id, payload=payload)


@router.get("", response_model=Page[RestaurantOut], summary="List restaurants for the current tenant")
async def list_restaurants(
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.RESTAURANT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await restaurant_service.list_restaurants(
        db, tenant_id=ctx.tenant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)


@router.get("/{restaurant_id}", response_model=RestaurantOut, summary="Get a restaurant")
async def get_restaurant(
    restaurant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.RESTAURANT_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await restaurant_service.get_restaurant(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id)


@router.patch("/{restaurant_id}", response_model=RestaurantOut, summary="Update a restaurant")
async def update_restaurant(
    restaurant_id: uuid.UUID,
    payload: RestaurantUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.RESTAURANT_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await restaurant_service.update_restaurant(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, actor_id=ctx.user.id, payload=payload
    )


@router.delete("/{restaurant_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive a restaurant")
async def archive_restaurant(
    restaurant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.RESTAURANT_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    await restaurant_service.archive_restaurant(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, actor_id=ctx.user.id)


@router.get("/{restaurant_id}/settings", response_model=RestaurantSettingsOut, summary="Get restaurant settings")
async def get_settings(
    restaurant_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.SETTINGS_READ)),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_service.get_settings(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id)
    return restaurant_service.settings_to_dict(row)


@router.patch("/{restaurant_id}/settings", response_model=RestaurantSettingsOut, summary="Update restaurant settings")
async def update_settings(
    restaurant_id: uuid.UUID,
    payload: RestaurantSettingsUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.SETTINGS_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_service.update_settings(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, actor_id=ctx.user.id, payload=payload
    )
    return restaurant_service.settings_to_dict(row)
