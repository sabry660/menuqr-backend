"""Development seed script. Creates a demo tenant with a full staff roster,
restaurant, branches, menus, categories, items, modifiers, and QR codes.

DEVELOPMENT ONLY. Credentials printed below are not secrets worth protecting —
never reuse them anywhere real.

Usage:
    python scripts/seed.py
"""
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import MenuStatus, PlanCode, RoleName  # noqa: E402
from app.models.menu import Menu, MenuCategory, MenuItem, ModifierGroup, ModifierOption  # noqa: E402
from app.models.misc import Plan, QRCode, Subscription  # noqa: E402
from app.models.restaurant import Branch, Restaurant, RestaurantSettings  # noqa: E402
from app.models.tenant import Membership, Tenant  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.subscription_service import DEFAULT_PLANS  # noqa: E402

DEV_PASSWORD = "DevPassword123!"  # DEVELOPMENT ONLY - never used in production seed data

DEMO_USERS = [
    ("owner@menuqr.dev", "Olivia Owner", RoleName.OWNER),
    ("admin@menuqr.dev", "Aiden Admin", RoleName.ADMIN),
    ("manager@menuqr.dev", "Mia Manager", RoleName.MANAGER),
    ("editor@menuqr.dev", "Eli Editor", RoleName.EDITOR),
    ("staff@menuqr.dev", "Sam Staff", RoleName.STAFF),
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # Plans
        for code, attrs in DEFAULT_PLANS.items():
            existing = (await db.execute(select(Plan).where(Plan.code == code))).scalar_one_or_none()
            if existing is None:
                db.add(Plan(code=code, **attrs))
        await db.commit()

        # Tenant
        tenant = (await db.execute(select(Tenant).where(Tenant.slug == "demo-bistro-group"))).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(name="Demo Bistro Group", slug="demo-bistro-group")
            db.add(tenant)
            await db.flush()

        # Subscription -> Pro plan for the demo tenant
        pro_plan = (await db.execute(select(Plan).where(Plan.code == PlanCode.PRO))).scalar_one()
        sub = (await db.execute(select(Subscription).where(Subscription.tenant_id == tenant.id))).scalar_one_or_none()
        if sub is None:
            db.add(Subscription(tenant_id=tenant.id, plan_id=pro_plan.id))

        # Users + memberships
        for email, full_name, role in DEMO_USERS:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                user = User(
                    email=email,
                    hashed_password=hash_password(DEV_PASSWORD),
                    full_name=full_name,
                    is_active=True,
                    is_email_verified=True,
                )
                db.add(user)
                await db.flush()

            membership = (
                await db.execute(
                    select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == tenant.id)
                )
            ).scalar_one_or_none()
            if membership is None:
                db.add(Membership(user_id=user.id, tenant_id=tenant.id, role=role))

        await db.commit()

        # Restaurant
        restaurant = (
            await db.execute(select(Restaurant).where(Restaurant.slug == "demo-bistro"))
        ).scalar_one_or_none()
        if restaurant is None:
            restaurant = Restaurant(
                tenant_id=tenant.id,
                name="Demo Bistro",
                slug="demo-bistro",
                description="A cozy neighborhood bistro serving modern comfort food.",
                currency="USD",
                locale="en",
                contact_email="hello@demobistro.dev",
                contact_phone="+1-555-0100",
            )
            db.add(restaurant)
            await db.flush()
            db.add(
                RestaurantSettings(
                    restaurant_id=restaurant.id,
                    theme_color="#8B4513",
                    public_description="Modern comfort food in the heart of downtown.",
                )
            )

        await db.commit()

        # Branches
        existing_branches = (
            await db.execute(select(Branch).where(Branch.restaurant_id == restaurant.id))
        ).scalars().all()
        if not existing_branches:
            downtown = Branch(
                restaurant_id=restaurant.id,
                name="Downtown",
                slug="downtown",
                address="123 Main St, Springfield",
                phone="+1-555-0101",
                latitude=39.7817,
                longitude=-89.6501,
            )
            uptown = Branch(
                restaurant_id=restaurant.id,
                name="Uptown",
                slug="uptown",
                address="456 Elm St, Springfield",
                phone="+1-555-0102",
                latitude=39.8,
                longitude=-89.64,
            )
            db.add_all([downtown, uptown])
            await db.flush()
            db.add(QRCode(restaurant_id=restaurant.id, branch_id=downtown.id, label="Downtown - Table QR", target_url=f"https://menuqr.dev/menu/{restaurant.slug}"))
            db.add(QRCode(restaurant_id=restaurant.id, branch_id=uptown.id, label="Uptown - Table QR", target_url=f"https://menuqr.dev/menu/{restaurant.slug}"))

        await db.commit()

        # Menu
        menu = (await db.execute(select(Menu).where(Menu.restaurant_id == restaurant.id))).scalar_one_or_none()
        if menu is None:
            menu = Menu(restaurant_id=restaurant.id, name="Main Menu", description="Our full lineup, available all day.", status=MenuStatus.PUBLISHED)
            db.add(menu)
            await db.flush()

            starters = MenuCategory(menu_id=menu.id, name="Starters", position=0)
            mains = MenuCategory(menu_id=menu.id, name="Mains", position=1)
            desserts = MenuCategory(menu_id=menu.id, name="Desserts", position=2)
            db.add_all([starters, mains, desserts])
            await db.flush()

            bruschetta = MenuItem(
                category_id=starters.id, name="Tomato Bruschetta", description="Grilled bread, heirloom tomato, basil.",
                price=Decimal("8.50"), position=0, dietary_tags="vegetarian",
            )
            soup = MenuItem(
                category_id=starters.id, name="Soup of the Day", description="Ask your server.",
                price=Decimal("6.00"), position=1,
            )
            burger = MenuItem(
                category_id=mains.id, name="Bistro Burger", description="Grass-fed beef, aged cheddar, brioche bun.",
                price=Decimal("15.00"), position=0,
            )
            salmon = MenuItem(
                category_id=mains.id, name="Grilled Salmon", description="Lemon-butter sauce, seasonal vegetables.",
                price=Decimal("21.00"), position=1, dietary_tags="gluten-free",
            )
            tart = MenuItem(
                category_id=desserts.id, name="Chocolate Tart", description="Dark chocolate ganache, sea salt.",
                price=Decimal("7.50"), position=0, dietary_tags="vegetarian",
            )
            db.add_all([bruschetta, soup, burger, salmon, tart])
            await db.flush()

            burger_temp = ModifierGroup(menu_item_id=burger.id, name="Temperature", is_required=True, min_selections=1, max_selections=1, position=0)
            db.add(burger_temp)
            await db.flush()
            db.add_all(
                [
                    ModifierOption(modifier_group_id=burger_temp.id, name="Medium Rare", position=0),
                    ModifierOption(modifier_group_id=burger_temp.id, name="Medium", position=1),
                    ModifierOption(modifier_group_id=burger_temp.id, name="Well Done", position=2),
                ]
            )

            burger_extras = ModifierGroup(menu_item_id=burger.id, name="Extras", is_required=False, min_selections=0, max_selections=3, position=1)
            db.add(burger_extras)
            await db.flush()
            db.add_all(
                [
                    ModifierOption(modifier_group_id=burger_extras.id, name="Extra Cheese", price_delta=Decimal("1.50"), position=0),
                    ModifierOption(modifier_group_id=burger_extras.id, name="Bacon", price_delta=Decimal("2.00"), position=1),
                    ModifierOption(modifier_group_id=burger_extras.id, name="Avocado", price_delta=Decimal("2.00"), position=2),
                ]
            )

        await db.commit()

    print("\n=== MenuQR demo data seeded (DEVELOPMENT ONLY credentials) ===")
    print(f"Password for all demo users: {DEV_PASSWORD}")
    for email, full_name, role in DEMO_USERS:
        print(f"  - {email:<22} role={role.value:<8} ({full_name})")
    print("\nDemo tenant slug: demo-bistro-group")
    print("Demo restaurant slug: demo-bistro")
    print("Public menu: GET /api/v1/public/demo-bistro/menu")
    print("===============================================================\n")


if __name__ == "__main__":
    asyncio.run(seed())
