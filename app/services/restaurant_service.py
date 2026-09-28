import json
import uuid

from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.misc import AuditLog  # noqa: F401 (kept for type clarity in audit calls)
from app.models.restaurant import Restaurant, RestaurantSettings
from app.schemas.restaurant import RestaurantCreate, RestaurantSettingsUpdate, RestaurantUpdate
from app.services import audit_service


async def _unique_restaurant_slug(db: AsyncSession, base_name: str, preferred: str | None) -> str:
    raw_name = preferred or base_name
    raw_name = raw_name.replace("'", "").replace("’", "")
    base = slugify(raw_name) or "restaurant"
    candidate = base
    suffix = 1
    while True:
        result = await db.execute(select(Restaurant).where(Restaurant.slug == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def create_restaurant(
    db: AsyncSession, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, payload: RestaurantCreate
) -> Restaurant:
    slug = await _unique_restaurant_slug(db, payload.name, payload.slug)
    restaurant = Restaurant(
        tenant_id=tenant_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        currency=payload.currency.upper(),
        locale=payload.locale,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    db.add(restaurant)
    await db.flush()

    db.add(RestaurantSettings(restaurant_id=restaurant.id))

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="restaurant.created",
        resource_type="restaurant",
        resource_id=str(restaurant.id),
    )
    await db.commit()
    await db.refresh(restaurant)
    return restaurant


async def _get_owned_restaurant(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID) -> Restaurant:
    """The single choke point for tenant-ownership validation on restaurants.
    Every read/update/delete of a restaurant MUST go through this."""
    result = await db.execute(
        select(Restaurant).where(
            Restaurant.id == restaurant_id, Restaurant.tenant_id == tenant_id
        )
    )
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundError("Restaurant not found.")
    return restaurant


async def get_restaurant(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID) -> Restaurant:
    return await _get_owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)


async def list_restaurants(
    db: AsyncSession, *, tenant_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[Restaurant], int]:
    count_result = await db.execute(
        select(func.count()).select_from(Restaurant).where(Restaurant.tenant_id == tenant_id, Restaurant.is_archived.is_(False))
    )
    total = count_result.scalar_one()
    result = await db.execute(
        select(Restaurant)
        .where(Restaurant.tenant_id == tenant_id, Restaurant.is_archived.is_(False))
        .order_by(Restaurant.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def update_restaurant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: RestaurantUpdate,
) -> Restaurant:
    restaurant = await _get_owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    data = payload.model_dump(exclude_unset=True)
    if "currency" in data and data["currency"]:
        data["currency"] = data["currency"].upper()
    for field, value in data.items():
        setattr(restaurant, field, value)

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="restaurant.updated",
        resource_type="restaurant",
        resource_id=str(restaurant.id),
        metadata={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(restaurant)
    return restaurant


async def archive_restaurant(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    restaurant = await _get_owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    restaurant.is_archived = True
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="restaurant.archived",
        resource_type="restaurant",
        resource_id=str(restaurant.id),
    )
    await db.commit()


async def get_settings(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID) -> RestaurantSettings:
    await _get_owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    result = await db.execute(
        select(RestaurantSettings).where(RestaurantSettings.restaurant_id == restaurant_id)
    )
    settings_row = result.scalar_one_or_none()
    if settings_row is None:
        raise NotFoundError("Settings not found.")
    return settings_row


async def update_settings(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: RestaurantSettingsUpdate,
) -> RestaurantSettings:
    settings_row = await get_settings(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    data = payload.model_dump(exclude_unset=True)
    if "social_links" in data and data["social_links"] is not None:
        data["social_links"] = json.dumps(data["social_links"])
    for field, value in data.items():
        setattr(settings_row, field, value)

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="settings.updated",
        resource_type="restaurant_settings",
        resource_id=str(settings_row.id),
        metadata={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(settings_row)
    return settings_row


def settings_to_dict(settings_row: RestaurantSettings) -> dict:
    out = {
        "id": settings_row.id,
        "restaurant_id": settings_row.restaurant_id,
        "logo_url": settings_row.logo_url,
        "cover_url": settings_row.cover_url,
        "theme_color": settings_row.theme_color,
        "public_description": settings_row.public_description,
        "internal_notes": settings_row.internal_notes,
        "social_links": json.loads(settings_row.social_links) if settings_row.social_links else {},
    }
    return out
