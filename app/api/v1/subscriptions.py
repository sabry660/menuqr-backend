from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.tenant import SubscriptionChange, SubscriptionOut
from app.services import subscription_service

router = APIRouter(prefix="/subscription", tags=["Subscriptions"])


@router.get("", response_model=SubscriptionOut, summary="Get the current tenant's subscription and entitlements")
async def get_subscription(
    ctx: TenantContext = Depends(require_permission(Perm.SUBSCRIPTION_READ)),
    db: AsyncSession = Depends(get_db),
):
    return await subscription_service.get_subscription_view(db, tenant_id=ctx.tenant_id)


@router.post("/change-plan", response_model=SubscriptionOut, summary="Change the tenant's plan")
async def change_plan(
    payload: SubscriptionChange,
    ctx: TenantContext = Depends(require_permission(Perm.SUBSCRIPTION_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    return await subscription_service.change_plan(
        db, tenant_id=ctx.tenant_id, actor_id=ctx.user.id, plan_code=payload.plan_code
    )
