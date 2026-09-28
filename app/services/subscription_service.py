import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PlanLimitError, ValidationAppError
from app.models.enums import PlanCode
from app.models.misc import Plan, Subscription
from app.models.restaurant import Branch, Restaurant
from app.models.menu import MenuItem, MenuCategory, Menu
from app.models.tenant import Membership
from app.services import audit_service

DEFAULT_PLANS = {
    PlanCode.FREE: {"name": "Free", "max_branches": 1, "max_staff": 3, "max_menu_items": 30, "price_cents_monthly": 0},
    PlanCode.PRO: {"name": "Pro", "max_branches": 5, "max_staff": 15, "max_menu_items": 300, "price_cents_monthly": 2900},
    PlanCode.BUSINESS: {"name": "Business", "max_branches": 50, "max_staff": 100, "max_menu_items": 5000, "price_cents_monthly": 9900},
}


async def ensure_plans_seeded(db: AsyncSession) -> None:
    for code, attrs in DEFAULT_PLANS.items():
        existing = (await db.execute(select(Plan).where(Plan.code == code))).scalar_one_or_none()
        if existing is None:
            db.add(Plan(code=code, **attrs))
    await db.commit()


async def get_or_create_subscription(db: AsyncSession, *, tenant_id: uuid.UUID) -> Subscription:
    result = await db.execute(select(Subscription).where(Subscription.tenant_id == tenant_id))
    sub = result.scalar_one_or_none()
    if sub is not None:
        return sub

    free_plan = (await db.execute(select(Plan).where(Plan.code == PlanCode.FREE))).scalar_one_or_none()
    if free_plan is None:
        await ensure_plans_seeded(db)
        free_plan = (await db.execute(select(Plan).where(Plan.code == PlanCode.FREE))).scalar_one()

    sub = Subscription(tenant_id=tenant_id, plan_id=free_plan.id)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub


async def get_subscription_view(db: AsyncSession, *, tenant_id: uuid.UUID) -> dict:
    sub = await get_or_create_subscription(db, tenant_id=tenant_id)
    plan = await db.get(Plan, sub.plan_id)
    return {
        "tenant_id": tenant_id,
        "plan_code": plan.code.value,
        "plan_name": plan.name,
        "status": sub.status,
        "max_branches": plan.max_branches,
        "max_staff": plan.max_staff,
        "max_menu_items": plan.max_menu_items,
        "current_period_end": sub.current_period_end,
    }


async def change_plan(
    db: AsyncSession, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, plan_code: str
) -> dict:
    try:
        code = PlanCode(plan_code)
    except ValueError:
        raise ValidationAppError(f"Unknown plan code '{plan_code}'.")

    plan = (await db.execute(select(Plan).where(Plan.code == code))).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan not found.")

    sub = await get_or_create_subscription(db, tenant_id=tenant_id)
    old_plan_id = sub.plan_id
    sub.plan_id = plan.id
    sub.status = "active"

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_id,
        action="subscription.changed",
        resource_type="subscription",
        resource_id=str(sub.id),
        metadata={"old_plan_id": str(old_plan_id), "new_plan_id": str(plan.id)},
    )
    await db.commit()
    return await get_subscription_view(db, tenant_id=tenant_id)


async def assert_can_add_branch(db: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    view = await get_subscription_view(db, tenant_id=tenant_id)
    count = (
        await db.execute(
            select(func.count())
            .select_from(Branch)
            .join(Restaurant, Restaurant.id == Branch.restaurant_id)
            .where(Restaurant.tenant_id == tenant_id, Branch.status != "archived")
        )
    ).scalar_one()
    if count >= view["max_branches"]:
        raise PlanLimitError(
            f"Plan '{view['plan_code']}' allows at most {view['max_branches']} branches."
        )


async def assert_can_add_staff(db: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    view = await get_subscription_view(db, tenant_id=tenant_id)
    count = (
        await db.execute(
            select(func.count())
            .select_from(Membership)
            .where(Membership.tenant_id == tenant_id, Membership.status == "active")
        )
    ).scalar_one()
    if count >= view["max_staff"]:
        raise PlanLimitError(f"Plan '{view['plan_code']}' allows at most {view['max_staff']} staff members.")


async def assert_can_add_menu_item(db: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    view = await get_subscription_view(db, tenant_id=tenant_id)
    count = (
        await db.execute(
            select(func.count())
            .select_from(MenuItem)
            .join(MenuCategory, MenuCategory.id == MenuItem.category_id)
            .join(Menu, Menu.id == MenuCategory.menu_id)
            .join(Restaurant, Restaurant.id == Menu.restaurant_id)
            .where(Restaurant.tenant_id == tenant_id, MenuItem.is_archived.is_(False))
        )
    ).scalar_one()
    if count >= view["max_menu_items"]:
        raise PlanLimitError(
            f"Plan '{view['plan_code']}' allows at most {view['max_menu_items']} menu items."
        )
