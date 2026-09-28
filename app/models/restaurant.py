import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import BranchStatus


class Restaurant(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "restaurants"
    __table_args__ = (UniqueConstraint("slug", name="uq_restaurants_slug"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="restaurants")
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    menus: Mapped[list["Menu"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    settings: Mapped["RestaurantSettings | None"] = relationship(
        back_populates="restaurant", uselist=False, cascade="all, delete-orphan"
    )
    qr_codes: Mapped[list["QRCode"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )


class Branch(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "slug", name="uq_branch_restaurant_slug"),
    )

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    opening_hours: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    status: Mapped[BranchStatus] = mapped_column(
        Enum(BranchStatus, name="branch_status_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=BranchStatus.ACTIVE,
        nullable=False,
    )

    restaurant: Mapped["Restaurant"] = relationship(back_populates="branches")
    qr_codes: Mapped[list["QRCode"]] = relationship(
        back_populates="branch", cascade="all, delete-orphan"
    )


class RestaurantSettings(Base, UUIDPKMixin, TimestampMixin):
    """Branding + configuration. Split from Restaurant so we can clearly mark
    which fields are public-safe (see schemas.public) vs. private."""

    __tablename__ = "restaurant_settings"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cover_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    theme_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    social_links: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded
    public_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Private / internal-only configuration:
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="settings")
