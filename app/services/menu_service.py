import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError, NotFoundError, ValidationAppError
from app.models.enums import MenuStatus
from app.models.menu import Menu, MenuCategory, MenuItem, ModifierGroup, ModifierOption
from app.models.restaurant import Restaurant
from app.schemas.menu import (
    CategoryCreate,
    CategoryUpdate,
    MenuCreate,
    MenuItemCreate,
    MenuItemUpdate,
    MenuUpdate,
    ModifierGroupCreate,
)
from app.services import audit_service, subscription_service

# ---------------------------------------------------------------------------
# Ownership resolution helpers. Every one of these joins all the way up to
# Restaurant.tenant_id so a client can never touch another tenant's resource
# by guessing/forging an ID, regardless of which level of the hierarchy the
# ID belongs to (menu, category, item, modifier group/option).
# ---------------------------------------------------------------------------


async def _owned_restaurant(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID) -> Restaurant:
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.tenant_id == tenant_id)
    )
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundError("Restaurant not found.")
    return restaurant


async def _owned_menu(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID) -> Menu:
    result = await db.execute(
        select(Menu)
        .join(Restaurant, Restaurant.id == Menu.restaurant_id)
        .where(Menu.id == menu_id, Menu.restaurant_id == restaurant_id, Restaurant.tenant_id == tenant_id)
    )
    menu = result.scalar_one_or_none()
    if menu is None:
        raise NotFoundError("Menu not found.")
    return menu


async def _owned_category(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID
) -> MenuCategory:
    result = await db.execute(
        select(MenuCategory)
        .join(Menu, Menu.id == MenuCategory.menu_id)
        .join(Restaurant, Restaurant.id == Menu.restaurant_id)
        .where(
            MenuCategory.id == category_id,
            MenuCategory.menu_id == menu_id,
            Menu.restaurant_id == restaurant_id,
            Restaurant.tenant_id == tenant_id,
        )
    )
    category = result.scalar_one_or_none()
    if category is None:
        raise NotFoundError("Category not found.")
    return category


async def _owned_item(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    menu_id: uuid.UUID,
    category_id: uuid.UUID,
    item_id: uuid.UUID,
) -> MenuItem:
    result = await db.execute(
        select(MenuItem)
        .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
        .join(Menu, Menu.id == MenuCategory.menu_id)
        .join(Restaurant, Restaurant.id == Menu.restaurant_id)
        .where(
            MenuItem.id == item_id,
            MenuItem.category_id == category_id,
            MenuCategory.menu_id == menu_id,
            Menu.restaurant_id == restaurant_id,
            Restaurant.tenant_id == tenant_id,
        )
        .options(selectinload(MenuItem.modifier_groups).selectinload(ModifierGroup.options))
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise NotFoundError("Menu item not found.")
    return item


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------


async def create_menu(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, actor_id: uuid.UUID, payload: MenuCreate
) -> Menu:
    await _owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    menu = Menu(restaurant_id=restaurant_id, name=payload.name, description=payload.description)
    db.add(menu)
    await db.flush()
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="menu.created",
        resource_type="menu", resource_id=str(menu.id),
    )
    await db.commit()
    await db.refresh(menu)
    return menu


async def list_menus(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, offset: int, limit: int):
    await _owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    total = (
        await db.execute(select(func.count()).select_from(Menu).where(Menu.restaurant_id == restaurant_id, Menu.is_archived.is_(False)))
    ).scalar_one()
    result = await db.execute(
        select(Menu)
        .where(Menu.restaurant_id == restaurant_id, Menu.is_archived.is_(False))
        .order_by(Menu.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def get_menu(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID) -> Menu:
    return await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)


async def update_menu(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, actor_id: uuid.UUID, payload: MenuUpdate
) -> Menu:
    menu = await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(menu, field, value)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="menu.updated",
        resource_type="menu", resource_id=str(menu.id), metadata={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(menu)
    return menu


async def set_menu_status(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, actor_id: uuid.UUID, publish: bool
) -> Menu:
    menu = await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    menu.status = MenuStatus.PUBLISHED if publish else MenuStatus.DRAFT
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id,
        action="menu.published" if publish else "menu.unpublished",
        resource_type="menu", resource_id=str(menu.id),
    )
    await db.commit()
    await db.refresh(menu)
    return menu


async def delete_menu(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    menu = await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    menu.is_archived = True
    menu.status = MenuStatus.ARCHIVED
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="menu.deleted",
        resource_type="menu", resource_id=str(menu.id),
    )
    await db.commit()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def create_category(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, actor_id: uuid.UUID, payload: CategoryCreate
) -> MenuCategory:
    await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    category = MenuCategory(menu_id=menu_id, name=payload.name, description=payload.description, position=payload.position)
    db.add(category)
    await db.flush()
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="category.created",
        resource_type="menu_category", resource_id=str(category.id),
    )
    await db.commit()
    await db.refresh(category)
    return category


async def list_categories(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID):
    await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    result = await db.execute(
        select(MenuCategory)
        .where(MenuCategory.menu_id == menu_id, MenuCategory.is_archived.is_(False))
        .order_by(MenuCategory.position.asc())
    )
    return list(result.scalars().all())


async def update_category(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID,
    actor_id: uuid.UUID, payload: CategoryUpdate,
) -> MenuCategory:
    category = await _owned_category(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(category, field, value)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="category.updated",
        resource_type="menu_category", resource_id=str(category.id), metadata={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    category = await _owned_category(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id)
    category.is_archived = True
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="category.deleted",
        resource_type="menu_category", resource_id=str(category.id),
    )
    await db.commit()


async def reorder_categories(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, ordered_ids: list[uuid.UUID], actor_id: uuid.UUID
) -> list[MenuCategory]:
    await _owned_menu(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    categories = await list_categories(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)
    by_id = {c.id: c for c in categories}
    if set(ordered_ids) != set(by_id.keys()):
        raise ValidationAppError("ordered_ids must contain exactly the current category IDs.")
    for position, cid in enumerate(ordered_ids):
        by_id[cid].position = position
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="category.updated",
        resource_type="menu_category", resource_id=str(menu_id), metadata={"reordered": True},
    )
    await db.commit()
    return await list_categories(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id)


# ---------------------------------------------------------------------------
# Menu items
# ---------------------------------------------------------------------------


async def create_item(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID,
    actor_id: uuid.UUID, payload: MenuItemCreate,
) -> MenuItem:
    await _owned_category(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id)
    await subscription_service.assert_can_add_menu_item(db, tenant_id=tenant_id)

    item = MenuItem(
        category_id=category_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        image_url=payload.image_url,
        is_available=payload.is_available,
        is_visible=payload.is_visible,
        position=payload.position,
        dietary_tags=",".join(payload.dietary_tags) if payload.dietary_tags else None,
    )
    db.add(item)
    await db.flush()
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="item.created",
        resource_type="menu_item", resource_id=str(item.id),
    )
    await db.commit()

    result = await db.execute(
        select(MenuItem)
        .where(MenuItem.id == item.id)
        .options(
            selectinload(MenuItem.modifier_groups)
            .selectinload(ModifierGroup.options)
        )
    )
    return result.scalar_one()


async def list_items(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID):
    await _owned_category(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id)
    result = await db.execute(
        select(MenuItem)
        .where(MenuItem.category_id == category_id, MenuItem.is_archived.is_(False))
        .order_by(MenuItem.position.asc())
        .options(selectinload(MenuItem.modifier_groups).selectinload(ModifierGroup.options))
    )
    return list(result.scalars().all())


async def get_item(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID, item_id: uuid.UUID) -> MenuItem:
    return await _owned_item(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, item_id=item_id)


async def update_item(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID,
    item_id: uuid.UUID, actor_id: uuid.UUID, payload: MenuItemUpdate,
) -> MenuItem:
    item = await _owned_item(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, item_id=item_id)
    data = payload.model_dump(exclude_unset=True)
    if "dietary_tags" in data:
        tags = data.pop("dietary_tags")
        item.dietary_tags = ",".join(tags) if tags else None
    for field, value in data.items():
        setattr(item, field, value)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="item.updated",
        resource_type="menu_item", resource_id=str(item.id), metadata={"fields": list(data.keys())},
    )
    await db.commit()

    result = await db.execute(
        select(MenuItem)
        .where(MenuItem.id == item.id)
        .options(
            selectinload(MenuItem.modifier_groups)
            .selectinload(ModifierGroup.options)
        )
    )
    return result.scalar_one()


async def delete_item(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID, item_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    item = await _owned_item(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, item_id=item_id)
    item.is_archived = True
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="item.deleted",
        resource_type="menu_item", resource_id=str(item.id),
    )
    await db.commit()


async def reorder_items(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID,
    ordered_ids: list[uuid.UUID], actor_id: uuid.UUID,
) -> list[MenuItem]:
    items = await list_items(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id)
    by_id = {i.id: i for i in items}
    if set(ordered_ids) != set(by_id.keys()):
        raise ValidationAppError("ordered_ids must contain exactly the current item IDs.")
    for position, iid in enumerate(ordered_ids):
        by_id[iid].position = position
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="item.updated",
        resource_type="menu_item", resource_id=str(category_id), metadata={"reordered": True},
    )
    await db.commit()
    return await list_items(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id)


# ---------------------------------------------------------------------------
# Modifier groups / options
# ---------------------------------------------------------------------------


async def create_modifier_group(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID,
    item_id: uuid.UUID, actor_id: uuid.UUID, payload: ModifierGroupCreate,
) -> ModifierGroup:
    await _owned_item(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, item_id=item_id)
    if payload.min_selections > payload.max_selections:
        raise AppError("min_selections cannot exceed max_selections.")

    group = ModifierGroup(
        menu_item_id=item_id,
        name=payload.name,
        is_required=payload.is_required,
        min_selections=payload.min_selections,
        max_selections=payload.max_selections,
        position=payload.position,
    )
    db.add(group)
    await db.flush()
    for opt in payload.options:
        db.add(ModifierOption(modifier_group_id=group.id, name=opt.name, price_delta=opt.price_delta, position=opt.position))

    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="item.updated",
        resource_type="modifier_group", resource_id=str(group.id),
    )
    await db.commit()
    result = await db.execute(
        select(ModifierGroup).where(ModifierGroup.id == group.id).options(selectinload(ModifierGroup.options))
    )
    return result.scalar_one()


def item_to_dict(item: MenuItem) -> dict:
    """Converts the ORM item (CSV dietary_tags) into the shape MenuItemOut expects."""
    return {
        "id": item.id,
        "category_id": item.category_id,
        "name": item.name,
        "description": item.description,
        "price": item.price,
        "image_url": item.image_url,
        "is_available": item.is_available,
        "is_visible": item.is_visible,
        "position": item.position,
        "dietary_tags": item.dietary_tags.split(",") if item.dietary_tags else [],
        "modifier_groups": [
            {
                "id": g.id,
                "menu_item_id": g.menu_item_id,
                "name": g.name,
                "is_required": g.is_required,
                "min_selections": g.min_selections,
                "max_selections": g.max_selections,
                "position": g.position,
                "is_active": g.is_active,
                "options": [
                    {
                        "id": o.id,
                        "name": o.name,
                        "price_delta": o.price_delta,
                        "position": o.position,
                        "is_active": o.is_active,
                    }
                    for o in sorted(g.options, key=lambda x: x.position)
                ],
            }
            for g in sorted(item.modifier_groups, key=lambda x: x.position)
        ],
    }


async def delete_modifier_group(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, menu_id: uuid.UUID, category_id: uuid.UUID,
    item_id: uuid.UUID, group_id: uuid.UUID, actor_id: uuid.UUID,
) -> None:
    await _owned_item(db, tenant_id=tenant_id, restaurant_id=restaurant_id, menu_id=menu_id, category_id=category_id, item_id=item_id)
    result = await db.execute(
        select(ModifierGroup).where(ModifierGroup.id == group_id, ModifierGroup.menu_item_id == item_id)
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise NotFoundError("Modifier group not found.")
    await db.delete(group)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="item.updated",
        resource_type="modifier_group", resource_id=str(group_id), metadata={"deleted": True},
    )
    await db.commit()
