import json
import uuid

from slugify import slugify
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.restaurant import Branch, Restaurant
from app.schemas.restaurant import BranchCreate, BranchUpdate
from app.services import audit_service, subscription_service


async def _get_owned_restaurant(db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID) -> Restaurant:
    result = await db.execute(
        select(Restaurant).where(Restaurant.id == restaurant_id, Restaurant.tenant_id == tenant_id)
    )
    restaurant = result.scalar_one_or_none()
    if restaurant is None:
        raise NotFoundError("Restaurant not found.")
    return restaurant


async def _get_owned_branch(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, branch_id: uuid.UUID
) -> Branch:
    """Ownership is verified by joining through Restaurant.tenant_id — never by
    trusting the branch_id/restaurant_id path params alone."""
    result = await db.execute(
        select(Branch)
        .join(Restaurant, Restaurant.id == Branch.restaurant_id)
        .where(
            Branch.id == branch_id,
            Branch.restaurant_id == restaurant_id,
            Restaurant.tenant_id == tenant_id,
        )
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise NotFoundError("Branch not found.")
    return branch


async def create_branch(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: BranchCreate,
) -> Branch:
    await _get_owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    await subscription_service.assert_can_add_branch(db, tenant_id=tenant_id)

    base_slug = slugify(payload.slug or payload.name) or "branch"
    candidate = base_slug
    suffix = 1
    while True:
        existing = await db.execute(
            select(Branch).where(Branch.restaurant_id == restaurant_id, Branch.slug == candidate)
        )
        if existing.scalar_one_or_none() is None:
            break
        suffix += 1
        candidate = f"{base_slug}-{suffix}"

    branch = Branch(
        restaurant_id=restaurant_id,
        name=payload.name,
        slug=candidate,
        address=payload.address,
        phone=payload.phone,
        latitude=payload.latitude,
        longitude=payload.longitude,
        opening_hours=json.dumps(payload.opening_hours) if payload.opening_hours else None,
    )
    db.add(branch)
    await db.flush()

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="branch.created",
        resource_type="branch",
        resource_id=str(branch.id),
    )
    await db.commit()
    await db.refresh(branch)
    return branch


async def list_branches(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[Branch], int]:
    await _get_owned_restaurant(db, tenant_id=tenant_id, restaurant_id=restaurant_id)
    count = (
        await db.execute(
            select(func.count()).select_from(Branch).where(Branch.restaurant_id == restaurant_id)
        )
    ).scalar_one()
    result = await db.execute(
        select(Branch)
        .where(Branch.restaurant_id == restaurant_id)
        .order_by(Branch.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), count


async def get_branch(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, branch_id: uuid.UUID
) -> Branch:
    return await _get_owned_branch(db, tenant_id=tenant_id, restaurant_id=restaurant_id, branch_id=branch_id)


async def update_branch(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    restaurant_id: uuid.UUID,
    branch_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: BranchUpdate,
) -> Branch:
    branch = await _get_owned_branch(db, tenant_id=tenant_id, restaurant_id=restaurant_id, branch_id=branch_id)
    data = payload.model_dump(exclude_unset=True)
    if "opening_hours" in data and data["opening_hours"] is not None:
        data["opening_hours"] = json.dumps(data["opening_hours"])
    for field, value in data.items():
        setattr(branch, field, value)

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="branch.updated",
        resource_type="branch",
        resource_id=str(branch.id),
        metadata={"fields": list(data.keys())},
    )
    await db.commit()
    await db.refresh(branch)
    return branch


async def delete_branch(
    db: AsyncSession, *, tenant_id: uuid.UUID, restaurant_id: uuid.UUID, branch_id: uuid.UUID, actor_id: uuid.UUID
) -> None:
    branch = await _get_owned_branch(db, tenant_id=tenant_id, restaurant_id=restaurant_id, branch_id=branch_id)
    branch.status = "archived"
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="branch.deleted",
        resource_type="branch",
        resource_id=str(branch.id),
    )
    await db.commit()
