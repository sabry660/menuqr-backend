import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext
from app.core.database import get_db
from app.permissions.definitions import Perm
from app.permissions.dependencies import require_permission
from app.schemas.auth import TokenResponse
from app.schemas.common import Page, PaginationParams
from app.schemas.tenant import InvitationAccept, InvitationCreate, InvitationOut
from app.services import invitation_service

router = APIRouter(prefix="/invitations", tags=["Invitations"])
# Accepting an invitation is unauthenticated (the token itself is the credential),
# so it lives on its own router mounted without tenant/auth dependencies.
public_router = APIRouter(prefix="/invitations", tags=["Invitations"])


@router.post("", response_model=InvitationOut, status_code=status.HTTP_201_CREATED, summary="Invite a new member")
async def create_invitation(
    payload: InvitationCreate,
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_INVITE)),
    db: AsyncSession = Depends(get_db),
):
    return await invitation_service.create_invitation(
        db, tenant_id=ctx.tenant_id, actor_id=ctx.user.id, email=payload.email, role=payload.role
    )


@router.get("", response_model=Page[InvitationOut], summary="List invitations for the current tenant")
async def list_invitations(
    pagination: PaginationParams = Depends(),
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_READ)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await invitation_service.list_invitations(
        db, tenant_id=ctx.tenant_id, offset=pagination.offset, limit=pagination.page_size
    )
    return Page.create(items, total, pagination.page, pagination.page_size)


@router.post("/{invitation_id}/resend", response_model=InvitationOut, summary="Resend a pending invitation")
async def resend_invitation(
    invitation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_INVITE)),
    db: AsyncSession = Depends(get_db),
):
    return await invitation_service.resend_invitation(
        db, tenant_id=ctx.tenant_id, invitation_id=invitation_id, actor_id=ctx.user.id
    )


@router.post("/{invitation_id}/revoke", response_model=InvitationOut, summary="Revoke a pending invitation")
async def revoke_invitation(
    invitation_id: uuid.UUID,
    ctx: TenantContext = Depends(require_permission(Perm.MEMBER_INVITE)),
    db: AsyncSession = Depends(get_db),
):
    return await invitation_service.revoke_invitation(
        db, tenant_id=ctx.tenant_id, invitation_id=invitation_id, actor_id=ctx.user.id
    )


@public_router.post(
    "/accept",
    response_model=TokenResponse,
    summary="Accept an invitation (unauthenticated; the token is the credential)",
)
async def accept_invitation(payload: InvitationAccept, db: AsyncSession = Depends(get_db)):
    """Accepts an invitation and immediately issues a token pair, so the client can
    redirect the newly-joined (or newly-created) user straight into the app without
    a second login round-trip."""
    from app.core.config import settings as _settings
    from app.core.security import create_access_token, create_refresh_token, hash_secret_token
    from app.models.user import RefreshToken as RefreshTokenModel

    user, _membership, _tenant = await invitation_service.accept_invitation(
        db, token=payload.token, password=payload.password, full_name=payload.full_name
    )

    access_token, _, _ = create_access_token(user.id)
    raw_refresh, jti, expire = create_refresh_token(user.id)
    db.add(
        RefreshTokenModel(
            user_id=user.id,
            jti=jti,
            token_hash=hash_secret_token(raw_refresh),
            expires_at=expire,
        )
    )
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=_settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
