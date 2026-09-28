import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.models.user import User
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.common import Page, PaginationParams
from app.schemas.tenant import MemberOut, MemberRoleUpdate
from app.services import member_service

router = APIRouter(prefix="/members", tags=["Members"])


@router.get("", response_model=Page[MemberOut], summary="List members of the current tenant")
async def list_members(
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await member_service.list_members(
        db, tenant_id=ctx.tenant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)


@router.patch("/{membership_id}", response_model=MemberOut, summary="Change a member's role")
async def update_role(
    membership_id: uuid.UUID,
    payload: MemberRoleUpdate,
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_UPDATE)),
    db: AsyncSession = Depends(get_db),
):
    membership = await member_service.update_role(
        db, tenant_id=ctx.tenant_id, membership_id=membership_id, new_role=payload.role, actor_membership=ctx.membership
    )
    user = await db.get(User, membership.user_id)
    return {
        "membership_id": membership.id,
        "user_id": membership.user_id,
        "email": user.email if user else "",
        "full_name": user.full_name if user else "",
        "role": membership.role,
        "status": membership.status,
        "joined_at": membership.created_at,
    }


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a member")
async def remove_member(
    membership_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_REMOVE)),
    db: AsyncSession = Depends(get_db),
):
    await member_service.remove_member(db, tenant_id=ctx.tenant_id, membership_id=membership_id, actor_membership=ctx.membership)
