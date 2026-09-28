import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, AuthorizationError, BusinessRuleError, NotFoundError
from app.models.enums import MembershipStatus, RoleName
from app.models.tenant import Membership
from app.models.user import User
from app.permissions.definitions import ROLE_RANK
from app.services import audit_service


async def list_members(db: AsyncSession, *, tenant_id: uuid.UUID, offset: int, limit: int) -> tuple[list[dict], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(Membership).where(Membership.tenant_id == tenant_id)
        )
    ).scalar_one()
    result = await db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(Membership.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    rows = [
        {
            "membership_id": m.id,
            "user_id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": m.role,
            "status": m.status,
            "joined_at": m.created_at,
        }
        for m, u in result.all()
    ]
    return rows, total


async def _get_membership(db: AsyncSession, *, tenant_id: uuid.UUID, membership_id: uuid.UUID) -> Membership:
    result = await db.execute(
        select(Membership).where(Membership.id == membership_id, Membership.tenant_id == tenant_id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise NotFoundError("Member not found.")
    return membership


async def update_role(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    membership_id: uuid.UUID,
    new_role: RoleName,
    actor_membership: Membership,
) -> Membership:
    target = await _get_membership(db, tenant_id=tenant_id, membership_id=membership_id)

    if target.user_id == actor_membership.user_id:
        raise AppError("You cannot change your own role.")

    if target.role == RoleName.OWNER:
        raise BusinessRuleError("The Owner role is protected and cannot be changed here.")

    if new_role == RoleName.OWNER:
        raise BusinessRuleError("Ownership transfer is not supported via this endpoint.")

    # A non-owner actor can never assign a role at or above their own rank
    # (prevents privilege escalation: an Admin cannot promote someone to Admin/Owner
    # unless the actor is itself Owner).
    if actor_membership.role != RoleName.OWNER and ROLE_RANK[new_role] >= ROLE_RANK[actor_membership.role]:
        raise AuthorizationError("You cannot assign a role equal to or higher than your own.")

    old_role = target.role
    target.role = new_role

    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_membership.user_id,
        action="member.role_updated",
        resource_type="membership",
        resource_id=str(target.id),
        metadata={"old_role": old_role.value, "new_role": new_role.value},
    )
    await db.commit()
    await db.refresh(target)
    return target


async def remove_member(
    db: AsyncSession, *, tenant_id: uuid.UUID, membership_id: uuid.UUID, actor_membership: Membership
) -> None:
    target = await _get_membership(db, tenant_id=tenant_id, membership_id=membership_id)

    if target.user_id == actor_membership.user_id:
        raise BusinessRuleError("You cannot remove yourself.")
    if target.role == RoleName.OWNER:
        raise AppError("The Owner cannot be removed.")

    target.status = MembershipStatus.REMOVED
    await audit_service.record(
        db,
        tenant_id=tenant_id,
        actor_user_id=actor_membership.user_id,
        action="member.removed",
        resource_type="membership",
        resource_id=str(target.id),
    )
    await db.commit()
