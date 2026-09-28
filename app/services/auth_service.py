import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationAppError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    hash_password,
    hash_secret_token,
    verify_password,
)
from app.models.enums import RoleName
from app.models.tenant import Membership, Tenant
from app.models.user import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from app.services import audit_service, email_service


async def _unique_tenant_slug(db: AsyncSession, base_name: str) -> str:
    base = slugify(base_name) or "tenant"
    candidate = base
    suffix = 1
    while True:
        result = await db.execute(select(Tenant).where(Tenant.slug == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def register_user(
    db: AsyncSession, *, email: str, password: str, full_name: str, tenant_name: str
) -> tuple[User, Tenant]:
    email = email.lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        # Generic message: do not reveal whether the account exists via a different message.
        raise ConflictError("A user with this email already exists.")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name.strip(),
        is_active=True,
        is_email_verified=False,
    )
    db.add(user)
    await db.flush()

    tenant_slug = await _unique_tenant_slug(db, tenant_name)
    tenant = Tenant(name=tenant_name.strip(), slug=tenant_slug, is_active=True)
    db.add(tenant)
    await db.flush()

    membership = Membership(user_id=user.id, tenant_id=tenant.id, role=RoleName.OWNER)
    db.add(membership)

    verification_raw = generate_secure_token()
    verification = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_secret_token(verification_raw),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )
    db.add(verification)

    await audit_service.record(
        db,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="tenant.created",
        resource_type="tenant",
        resource_id=str(tenant.id),
    )

    await db.commit()
    await db.refresh(user)
    await db.refresh(tenant)

    await email_service.send_verification_email(user.email, verification_raw)
    return user, tenant


async def _persist_refresh_token(
    db: AsyncSession, *, user_id: uuid.UUID, ip_address: str | None, user_agent: str | None
) -> str:
    raw_token, jti, expire = create_refresh_token(user_id)
    row = RefreshToken(
        user_id=user_id,
        jti=jti,
        token_hash=hash_secret_token(raw_token),
        expires_at=expire,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(row)
    await db.flush()
    return raw_token


async def authenticate(
    db: AsyncSession, *, email: str, password: str, ip_address: str | None, user_agent: str | None
) -> tuple[User, str, str, int]:
    email = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Constant-shape response whether the user exists or not, to avoid user enumeration.
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise AuthenticationError("This account has been deactivated.")

    access_token, _, _ = create_access_token(user.id)
    refresh_token = await _persist_refresh_token(
        db, user_id=user.id, ip_address=ip_address, user_agent=user_agent
    )
    await db.commit()
    return user, access_token, refresh_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def refresh_tokens(
    db: AsyncSession, *, refresh_token: str, ip_address: str | None, user_agent: str | None
) -> tuple[str, str, int]:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise AuthenticationError("Invalid or expired refresh token.")

    if payload.get("type") != TokenType.REFRESH.value:
        raise AuthenticationError("A refresh token is required.")

    jti = payload.get("jti")
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    stored = result.scalar_one_or_none()

    if stored is None:
        raise AuthenticationError("Refresh token not recognized.")

    if not stored.is_active:
        # REUSE DETECTION: a revoked/rotated token being presented again indicates the
        # token was stolen. Defensively revoke the entire session family for this user.
        all_tokens = (
            await db.execute(select(RefreshToken).where(RefreshToken.user_id == stored.user_id))
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for t in all_tokens:
            if t.is_active:
                t.revoked_at = now
        await db.commit()
        raise AuthenticationError("Refresh token has already been used. All sessions revoked.")

    if stored.expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token has expired.")

    user = await db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive.")

    # Rotate: revoke old, issue new.
    new_raw_token, new_jti, expire = create_refresh_token(user.id)
    stored.revoked_at = datetime.now(timezone.utc)
    stored.replaced_by_jti = new_jti
    new_row = RefreshToken(
        user_id=user.id,
        jti=new_jti,
        token_hash=hash_secret_token(new_raw_token),
        expires_at=expire,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(new_row)

    access_token, _, _ = create_access_token(user.id)
    await db.commit()
    return access_token, new_raw_token, settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


async def logout(db: AsyncSession, *, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        return  # Logout is idempotent; an already-invalid token is fine.

    jti = payload.get("jti")
    result = await db.execute(select(RefreshToken).where(RefreshToken.jti == jti))
    stored = result.scalar_one_or_none()
    if stored and stored.is_active:
        stored.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def request_password_reset(db: AsyncSession, *, email: str) -> None:
    email = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        # Do not reveal whether the account exists.
        return
    raw_token = generate_secure_token()
    row = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_secret_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(row)
    await db.commit()
    await email_service.send_password_reset_email(user.email, raw_token)


async def reset_password(db: AsyncSession, *, token: str, new_password: str) -> None:
    token_hash = hash_secret_token(token)
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is None or row.used_at is not None:
        raise ValidationAppError("Invalid or already-used reset token.")
    if row.expires_at < datetime.now(timezone.utc):
        raise ValidationAppError("Reset token has expired.")

    user = await db.get(User, row.user_id)
    if user is None:
        raise NotFoundError("User not found.")

    user.hashed_password = hash_password(new_password)
    row.used_at = datetime.now(timezone.utc)

    # Revoke all existing sessions on password change.
    active_tokens = (
        await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
            )
        )
    ).scalars().all()
    for t in active_tokens:
        t.revoked_at = datetime.now(timezone.utc)

    await db.commit()


async def verify_email(db: AsyncSession, *, token: str) -> None:
    token_hash = hash_secret_token(token)
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is None or row.used_at is not None:
        raise ValidationAppError("Invalid or already-used verification token.")
    if row.expires_at < datetime.now(timezone.utc):
        raise ValidationAppError("Verification token has expired.")

    user = await db.get(User, row.user_id)
    if user is None:
        raise NotFoundError("User not found.")

    user.is_email_verified = True
    row.used_at = datetime.now(timezone.utc)
    await db.commit()


async def resend_verification(db: AsyncSession, *, email: str) -> None:
    email = email.lower().strip()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or user.is_email_verified:
        return  # Do not leak account existence or verification state.

    raw_token = generate_secure_token()
    row = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_secret_token(raw_token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS),
    )
    db.add(row)
    await db.commit()
    await email_service.send_verification_email(user.email, raw_token)


async def get_memberships(db: AsyncSession, *, user_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Membership, Tenant)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == user_id, Membership.status == "active")
    )
    return [
        {
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "tenant_slug": tenant.slug,
            "role": membership.role.value,
        }
        for membership, tenant in result.all()
    ]
