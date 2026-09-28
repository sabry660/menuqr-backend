import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError, BusinessRuleError, ConflictError, NotFoundError, ValidationAppError
from app.core.security import generate_secure_token, hash_password, hash_secret_token
from app.models.enums import InvitationStatus, MembershipStatus, RoleName
from app.models.tenant import Invitation, Membership, Tenant
from app.models.user import User
from app.services import audit_service, email_service, subscription_service


async def create_invitation(
    db: AsyncSession, *, tenant_id: uuid.UUID, actor_id: uuid.UUID, email: str, role: RoleName
) -> Invitation:
    email = email.lower().strip()
    if role == RoleName.OWNER:
        raise AppError("Cannot invite someone directly as Owner.")

    await subscription_service.assert_can_add_staff(db, tenant_id=tenant_id)

    # Already an active member?
    existing_member = await db.execute(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == tenant_id, User.email == email, Membership.status == MembershipStatus.ACTIVE)
    )
    if existing_member.scalar_one_or_none() is not None:
        raise ConflictError("This user is already a member of the tenant.")

    # Duplicate pending invitation?
    existing_invite = await db.execute(
        select(Invitation).where(
            Invitation.tenant_id == tenant_id,
            Invitation.email == email,
            Invitation.status == InvitationStatus.PENDING,
        )
    )
    if existing_invite.scalar_one_or_none() is not None:
        raise ConflictError("A pending invitation already exists for this email.")

    tenant = await db.get(Tenant, tenant_id)
    raw_token = generate_secure_token()
    invitation = Invitation(
        tenant_id=tenant_id,
        email=email,
        role=role,
        token_hash=hash_secret_token(raw_token),
        status=InvitationStatus.PENDING,
        invited_by_user_id=actor_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.INVITATION_TOKEN_EXPIRE_DAYS),
    )
    db.add(invitation)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("A pending invitation already exists for this email.")

    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="member.invited",
        resource_type="invitation", resource_id=str(invitation.id), metadata={"email": email, "role": role.value},
    )
    await db.commit()
    await db.refresh(invitation)

    await email_service.send_invitation_email(email, raw_token, tenant.name if tenant else "MenuQR")
    return invitation


async def list_invitations(db: AsyncSession, *, tenant_id: uuid.UUID, offset: int, limit: int) -> tuple[list[Invitation], int]:
    total = (
        await db.execute(select(func.count()).select_from(Invitation).where(Invitation.tenant_id == tenant_id))
    ).scalar_one()
    result = await db.execute(
        select(Invitation)
        .where(Invitation.tenant_id == tenant_id)
        .order_by(Invitation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def _get_owned_invitation(db: AsyncSession, *, tenant_id: uuid.UUID, invitation_id: uuid.UUID) -> Invitation:
    result = await db.execute(
        select(Invitation).where(Invitation.id == invitation_id, Invitation.tenant_id == tenant_id)
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise NotFoundError("Invitation not found.")
    return invitation


async def resend_invitation(db: AsyncSession, *, tenant_id: uuid.UUID, invitation_id: uuid.UUID, actor_id: uuid.UUID) -> Invitation:
    invitation = await _get_owned_invitation(db, tenant_id=tenant_id, invitation_id=invitation_id)
    if invitation.status != InvitationStatus.PENDING:
        raise BusinessRuleError("Only pending invitations can be resent.")

    raw_token = generate_secure_token()
    invitation.token_hash = hash_secret_token(raw_token)
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.INVITATION_TOKEN_EXPIRE_DAYS)

    tenant = await db.get(Tenant, tenant_id)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="invitation.resent",
        resource_type="invitation", resource_id=str(invitation.id),
    )
    await db.commit()
    await db.refresh(invitation)
    await email_service.send_invitation_email(invitation.email, raw_token, tenant.name if tenant else "MenuQR")
    return invitation


async def revoke_invitation(db: AsyncSession, *, tenant_id: uuid.UUID, invitation_id: uuid.UUID, actor_id: uuid.UUID) -> Invitation:
    invitation = await _get_owned_invitation(db, tenant_id=tenant_id, invitation_id=invitation_id)
    if invitation.status != InvitationStatus.PENDING:
        raise AppError("Only pending invitations can be revoked.")
    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = datetime.now(timezone.utc)
    await audit_service.record(
        db, tenant_id=tenant_id, actor_user_id=actor_id, action="invitation.revoked",
        resource_type="invitation", resource_id=str(invitation.id),
    )
    await db.commit()
    await db.refresh(invitation)
    return invitation


async def accept_invitation(
    db: AsyncSession, *, token: str, password: str | None, full_name: str | None
) -> tuple[User, Membership, Tenant]:
    """Transactional + race-safe acceptance.

    Concurrency strategy: the UPDATE ... WHERE status = 'pending' below only
    succeeds for the first concurrent request; a second simultaneous accept on the
    same token will find `status` no longer PENDING and fail cleanly, instead of
    creating two memberships. The unique (user_id, tenant_id) constraint on
    Membership is a second independent guard against a duplicate membership row.
    """
    token_hash = hash_secret_token(token)

    result = await db.execute(select(Invitation).where(Invitation.token_hash == token_hash))
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise ValidationAppError("Invalid invitation token.")

    if invitation.status == InvitationStatus.ACCEPTED:
        raise ValidationAppError("This invitation has already been used.")
    if invitation.status == InvitationStatus.REVOKED:
        raise ValidationAppError("This invitation has been revoked.")
    if invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = InvitationStatus.EXPIRED
        await db.commit()
        raise ValidationAppError("This invitation has expired.")
    if invitation.status != InvitationStatus.PENDING:
        raise ValidationAppError("This invitation is no longer valid.")

    # Find or create the user.
    user_result = await db.execute(select(User).where(User.email == invitation.email))
    user = user_result.scalar_one_or_none()

    if user is None:
        if not password or not full_name:
            raise ValidationAppError(
                "No account exists for this email yet; password and full_name are required."
            )
        user = User(
            email=invitation.email,
            hashed_password=hash_password(password),
            full_name=full_name.strip(),
            is_active=True,
            is_email_verified=True,  # accepting via a mailed invitation link verifies ownership
        )
        db.add(user)
        await db.flush()

    # Race-condition guard: atomically flip PENDING -> ACCEPTED; if another request
    # already did this, `rowcount` will be 0 and we abort instead of double-processing.
    from sqlalchemy import update as sa_update

    result = await db.execute(
        sa_update(Invitation)
        .where(Invitation.id == invitation.id, Invitation.status == InvitationStatus.PENDING)
        .values(status=InvitationStatus.ACCEPTED, accepted_at=datetime.now(timezone.utc))
    )
    if result.rowcount == 0:
        await db.rollback()
        raise ConflictError("This invitation was already processed.")

    existing_membership = await db.execute(
        select(Membership).where(Membership.user_id == user.id, Membership.tenant_id == invitation.tenant_id)
    )
    membership = existing_membership.scalar_one_or_none()
    if membership is not None:
        membership.status = MembershipStatus.ACTIVE
        membership.role = invitation.role
    else:
        membership = Membership(user_id=user.id, tenant_id=invitation.tenant_id, role=invitation.role)
        db.add(membership)

    tenant = await db.get(Tenant, invitation.tenant_id)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise ConflictError("This invitation was already processed.")

    await audit_service.record(
        db, tenant_id=invitation.tenant_id, actor_user_id=user.id, action="invitation.accepted",
        resource_type="invitation", resource_id=str(invitation.id),
    )
    await db.commit()
    await db.refresh(user)
    await db.refresh(membership)

    await email_service.send_invitation_accepted_email(user.email, tenant.name if tenant else "MenuQR")
    return user, membership, tenant
