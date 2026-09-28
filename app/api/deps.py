import uuid

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.core.security import TokenType, decode_token
from app.models.tenant import Membership
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise AuthenticationError("Invalid or expired token.")

    if payload.get("type") != TokenType.ACCESS.value:
        raise AuthenticationError("An access token is required.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise AuthenticationError("Malformed token subject.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")
    return user


class TenantContext:
    """Resolved (user, tenant_id, membership, permissions) for the current request.

    Every tenant-scoped router depends on this instead of trusting a client-supplied
    tenant_id: the tenant is always taken from the authenticated user's membership,
    never from a path/query/body parameter the client controls.
    """

    def __init__(self, user: User, membership: Membership):
        self.user = user
        self.membership = membership
        self.tenant_id = membership.tenant_id
        self.role = membership.role


async def get_tenant_context(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID", description="Active tenant/organization ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Resolves the tenant the current request operates on.

    The client tells us *which* of the user's tenants it wants to act as via the
    X-Tenant-ID header, but we NEVER trust that alone: we look up the Membership row
    joining that exact user_id + tenant_id, and reject if none exists (or if it's not
    active). This is the server-side ownership check IDOR protection depends on.
    """
    try:
        tenant_uuid = uuid.UUID(x_tenant_id)
    except ValueError:
        raise AuthenticationError("Invalid X-Tenant-ID header.")

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.tenant_id == tenant_uuid,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        # Deliberately the same error as "doesn't exist" to avoid confirming tenant existence.
        raise AuthorizationError("You do not have access to this tenant.")
    if membership.status.value != "active":
        raise AuthorizationError("Your membership in this tenant is not active.")

    return TenantContext(user=current_user, membership=membership)
