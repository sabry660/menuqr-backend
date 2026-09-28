import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import PlanCode, QRCodeStatus, SubscriptionStatus


class QRCode(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "qr_codes"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    target_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[QRCodeStatus] = mapped_column(
        Enum(QRCodeStatus, name="qr_status_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=QRCodeStatus.ACTIVE,
        nullable=False,
    )
    scans_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="qr_codes")
    branch: Mapped["Branch | None"] = relationship(back_populates="qr_codes")


class Plan(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "plans"

    code: Mapped[PlanCode] = mapped_column(
        Enum(PlanCode, name="plan_code_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_branches: Mapped[int] = mapped_column(Integer, nullable=False)
    max_staff: Mapped[int] = mapped_column(Integer, nullable=False)
    max_menu_items: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents_monthly: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")


class Subscription(Base, UUIDPKMixin, TimestampMixin):
    """Billing-provider-agnostic subscription. `provider` + `provider_ref` let a
    real payment provider (Stripe etc.) be plugged in later without changing the
    domain model; see app/integrations/billing.py."""

    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=SubscriptionStatus.ACTIVE,
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(50), default="internal", nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="subscription")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")


class AuditLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
