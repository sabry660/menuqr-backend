from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.common import Page, PaginationParams
from app.schemas.tenant import AuditLogOut
from app.services import audit_service

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("", response_model=Page[AuditLogOut], summary="List audit logs for the current tenant")
async def list_audit_logs(
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.AUDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await audit_service.list_for_tenant(
        db, tenant_id=ctx.tenant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)
