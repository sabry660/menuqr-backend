import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.menu import (
    MenuItemCreate,
    MenuItemOut,
    MenuItemUpdate,
    ModifierGroupCreate,
    ModifierGroupOut,
    ReorderRequest,
)
from app.services import menu_service

router = APIRouter(
    prefix="/restaurants/{restaurant_id}/menus/{menu_id}/categories/{category_id}/items",
    tags=["Menu Items"],
)


@router.post("", response_model=MenuItemOut, status_code=status.HTTP_201_CREATED, summary="Create a menu item")
async def create_item(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    payload: MenuItemCreate,
    ctx: TenantContext = Depends(require_permission(Perm.ITEM_CREATE)),
    db: AsyncSession = Depends(get_db),
):
    item = await menu_service.create_item(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        actor_id=ctx.user.id, payload=payload,
    )
    return menu_service.item_to_dict(item)


@router.get("", response_model=list[MenuItemOut], summary="List menu items for a category")
async def list_items(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_READ)),
    db: AsyncSession = Depends(get_db),
):
    items = await menu_service.list_items(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id
    )
    return [menu_service.item_to_dict(i) for i in items]


@router.get("/{item_id}", response_model=MenuItemOut, summary="Get a menu item")
async def get_item(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    item_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MENU_READ)),
    db: AsyncSession = Depends(get_db),
):
    item = await menu_service.get_item(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, item_id=item_id
    )
    return menu_service.item_to_dict(item)


@router.patch("/{item_id}", response_model=MenuItemOut, summary="Update a menu item")
async def update_item(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: MenuItemUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.ITEM_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    item = await menu_service.update_item(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        item_id=item_id, actor_id=ctx.user.id, payload=payload,
    )
    return menu_service.item_to_dict(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive a menu item")
async def delete_item(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    item_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.ITEM_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    await menu_service.delete_item(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        item_id=item_id, actor_id=ctx.user.id,
    )


@router.post("/reorder", response_model=list[MenuItemOut], summary="Reorder items within a category")
async def reorder_items(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    payload: ReorderRequest,
    ctx: TenantContext = Depends(require_permission(Perm.ITEM_REORDER)),
    db: AsyncSession = Depends(get_db),
):
    items = await menu_service.reorder_items(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        ordered_ids=payload.ordered_ids, actor_id=ctx.user.id,
    )
    return [menu_service.item_to_dict(i) for i in items]


@router.post(
    "/{item_id}/modifier-groups",
    response_model=ModifierGroupOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a modifier group for an item",
)
async def create_modifier_group(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ModifierGroupCreate,
    ctx: TenantContext = Depends(require_permission(Perm.MODIFIER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    return await menu_service.create_modifier_group(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        item_id=item_id, actor_id=ctx.user.id, payload=payload,
    )


@router.delete(
    "/{item_id}/modifier-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a modifier group",
)
async def delete_modifier_group(
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    item_id: uuid.UUID,
    group_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MODIFIER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    await menu_service.delete_modifier_group(
        db, tenant_id=ctx.tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id,
        item_id=item_id, group_id=group_id, actor_id=ctx.user.id,
    )
