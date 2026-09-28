import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import InvitationStatus, MembershipStatus, RoleName


class Tenant(Base, UUIDPKMixin, TimestampMixin):
    """A billing/organizational boundary. One Tenant may eventually own several
    Restaurants (e.g. a restaurant group)."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    restaurants: Mapped[list["Restaurant"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="tenant", uselist=False, cascade="all, delete-orphan"
    )


class Membership(Base, UUIDPKMixin, TimestampMixin):
    """A User's membership (with a role) inside a Tenant. This is the row every
    authorization check is ultimately anchored to."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]), nullable=False
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="membership_status_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=MembershipStatus.ACTIVE,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="memberships")
    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")


class Invitation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "email", "status", name="uq_invitation_tenant_email_status"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(InvitationStatus, name="invitation_status_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=InvitationStatus.PENDING,
        nullable=False,
        index=True,
    )
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="invitations")
