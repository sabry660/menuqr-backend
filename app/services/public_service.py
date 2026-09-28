import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models.enums import MenuStatus
from app.models.menu import Menu, MenuCategory, MenuItem, ModifierGroup, ModifierOption
from app.models.restaurant import Restaurant, RestaurantSettings


async def get_public_menu(db: AsyncSession, *, restaurant_slug: str) -> dict:
    """Returns only public-safe data for a published menu.

    Explicit allow-list approach: we hand-build the response dict field by field
    rather than serializing ORM objects directly, so a new private column added to
    a model later cannot accidentally leak through this endpoint.
    """
    restaurant_result = await db.execute(
        select(Restaurant).where(Restaurant.slug == restaurant_slug, Restaurant.is_archived.is_(False))
    )
    restaurant = restaurant_result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundError("Restaurant not found.")

    settings_result = await db.execute(
        select(RestaurantSettings).where(RestaurantSettings.restaurant_id == restaurant.id)
    )
    settings_row = settings_result.scalar_one_or_none()

    menus_result = await db.execute(
        select(Menu)
        .where(
            Menu.restaurant_id == restaurant.id,
            Menu.status == MenuStatus.PUBLISHED,
            Menu.is_archived.is_(False),
        )
        .options(
            selectinload(Menu.categories)
            .selectinload(MenuCategory.items)
            .selectinload(MenuItem.modifier_groups)
            .selectinload(ModifierGroup.options)
        )
        .order_by(Menu.created_at.asc())
    )
    menus = menus_result.scalars().unique().all()

    def build_menu(menu: Menu) -> dict:
        categories = [c for c in menu.categories if not c.is_archived]
        categories.sort(key=lambda c: c.position)
        return {
            "id": menu.id,
            "name": menu.name,
            "description": menu.description,
            "categories": [build_category(c) for c in categories],
        }

    def build_category(category: MenuCategory) -> dict:
        items = [i for i in category.items if not i.is_archived and i.is_visible]
        items.sort(key=lambda i: i.position)
        return {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "items": [build_item(i) for i in items],
        }

    def build_item(item: MenuItem) -> dict:
        groups = [g for g in item.modifier_groups if g.is_active]
        groups.sort(key=lambda g: g.position)
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "price": item.price,
            "image_url": item.image_url,
            "is_available": item.is_available,
            "dietary_tags": item.dietary_tags.split(",") if item.dietary_tags else [],
            "modifier_groups": [build_group(g) for g in groups],
        }

    def build_group(group: ModifierGroup) -> dict:
        options = [o for o in group.options if o.is_active]
        options.sort(key=lambda o: o.position)
        return {
            "id": group.id,
            "name": group.name,
            "is_required": group.is_required,
            "min_selections": group.min_selections,
            "max_selections": group.max_selections,
            "options": [
                {"id": o.id, "name": o.name, "price_delta": o.price_delta} for o in options
            ],
        }

    branding = {
        "logo_url": settings_row.logo_url if settings_row else None,
        "cover_url": settings_row.cover_url if settings_row else None,
        "theme_color": settings_row.theme_color if settings_row else None,
        "social_links": json.loads(settings_row.social_links)
        if settings_row and settings_row.social_links
        else {},
        "public_description": settings_row.public_description if settings_row else None,
        # NOTE: settings_row.internal_notes is deliberately NEVER included here.
    }

    return {
        "restaurant_name": restaurant.name,
        "restaurant_slug": restaurant.slug,
        "currency": restaurant.currency,
        "locale": restaurant.locale,
        "branding": branding,
        "menus": [build_menu(m) for m in menus],
    }
