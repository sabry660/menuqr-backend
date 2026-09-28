import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.common import Page, PaginationParams
from app.schemas.menu import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    MenuCreate,
    MenuOut,
    MenuUpdate,
    ReorderRequest,
)
from app.services import menu_service

router = APIRouter(prefix="/restaurants/{restaurant_id}/menus", tags=["Menus"])
categories_router = APIRouter(
    prefix="/restaurants/{restaurant_id}/menus/{menu_id}/categories", tags=["Categories"]
)


@router.post("", response_model=MenuOut, status_code=status.HTTP_201_CREATED, summary="Create a menu")
async def create_menu(
    restaurant_id: uuid.UUID,
    payload: MenuCreate,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.create_menu(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, actor_id=ctx.user.id, payload=payload)


@router.get("", response_model=Page[MenuOut], summary="List menus")
async def list_menus(
    restaurant_id: uuid.UUID,
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.MENU_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await menu_service.list_menus(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)


@router.get("/{menu_id}", response_model=MenuOut, summary="Get a menu")
async def get_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.get_menu(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)


@router.patch("/{menu_id}", response_model=MenuOut, summary="Update a menu")
async def update_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    payload: MenuUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.update_menu(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, actor_id=ctx.user.id, payload=payload
    )


@router.post("/{menu_id}/publish", response_model=MenuOut, summary="Publish a menu")
async def publish_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.set_menu_status(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, actor_id=ctx.user.id, publish=True
    )


@router.post("/{menu_id}/unpublish", response_model=MenuOut, summary="Unpublish a menu")
async def unpublish_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_PUBLISH)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.set_menu_status(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, actor_id=ctx.user.id, publish=False
    )


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive a menu")
async def delete_menu(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    await menu_service.delete_menu(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, actor_id=ctx.user.id)


# --- Categories (nested under a menu) ---------------------------------------


@categories_router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED, summary="Create a category")
async def create_category(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    payload: CategoryCreate,
    ctx: TenantContext = Depends(require_permission(Perm.CATEGORY_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.create_category(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, actor_id=ctx.user.id, payload=payload
    )


@categories_router.get("", response_model=list[CategoryOut], summary="List categories for a menu")
async def list_categories(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.list_categories(db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)


@categories_router.patch("/{category_id}", response_model=CategoryOut, summary="Update a category")
async def update_category(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    payload: CategoryUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.CATEGORY_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.update_category(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        actor_id=ctx.user.id, payload=payload,
    )


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive a category")
async def delete_category(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.CATEGORY_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    await menu_service.delete_category(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, actor_id=ctx.user.id
    )


@categories_router.post("/reorder", response_model=list[CategoryOut], summary="Reorder categories within a menu")
async def reorder_categories(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    payload: ReorderRequest,
    ctx: TenantContext = Depends(require_permission(Perm.CATEGORY_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.reorder_categories(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id,
        ordered_ids=payload.ordered_ids, actor_id=ctx.user.id,
    )
