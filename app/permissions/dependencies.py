from fastapi import Depends

from app.api.deps import TenantContext, get_tenant_context
from app.core.exceptions import AuthorizationError
from app.permissions.definitions import permissions_for_role


def require_permission(permission: str):
    """FastAPI dependency factory enforcing a single centralized permission check.

    Usage: `ctx: TenantContext = Depends(require_permission(Perm.MENU_UPDATE))`
    All protected endpoints use this rather than ad-hoc `if ctx.role == ...` checks,
    so the full authorization matrix lives in app/permissions/definitions.py.
    """

    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        granted = permissions_for_role(ctx.role)
        if permission not in granted:
            raise AuthorizationError(
                f"Your role ({ctx.role.value}) does not have permission '{permission}'."
            )
        return ctx

    return _dependency


def require_any_membership():
    """Just requires a valid, active membership in the tenant (no specific permission)."""

    async def _dependency(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        return ctx

    return _dependency
