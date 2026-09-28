import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.misc import AuditLog
from app.models.user import User


async def record(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Writes one audit log row. Caller controls the transaction (commit happens in
    the calling service alongside the business change, so they succeed/fail together).
    Never pass secrets (tokens, passwords) in `metadata`.
    """
    entry = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_json=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    await db.flush()
    return entry


async def list_for_tenant(
    db: AsyncSession, *, tenant_id: uuid.UUID, offset: int, limit: int
) -> tuple[list[dict], int]:
    count_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.tenant_id == tenant_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.actor_user_id)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = []
    for log, actor_email in result.all():
        rows.append(
            {
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "actor_email": actor_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata": log.metadata_json or {},
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "created_at": log.created_at,
            }
        )
    return rows, total
