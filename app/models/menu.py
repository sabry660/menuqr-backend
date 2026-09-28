import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import MenuStatus


class Menu(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "menus"

    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MenuStatus] = mapped_column(
        Enum(MenuStatus, name="menu_status_enum", native_enum=True, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=MenuStatus.DRAFT,
        nullable=False,
        index=True,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    restaurant: Mapped["Restaurant"] = relationship(back_populates="menus")
    categories: Mapped[list["MenuCategory"]] = relationship(
        back_populates="menu", cascade="all, delete-orphan", order_by="MenuCategory.position"
    )


class MenuCategory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "menu_categories"

    menu_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("menus.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    menu: Mapped["Menu"] = relationship(back_populates="categories")
    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="MenuItem.position"
    )


class MenuItem(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "menu_items"

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("menu_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Money is ALWAYS Numeric/Decimal, never float.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dietary_tags: Mapped[str | None] = mapped_column(String(500), nullable=True)  # csv
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category: Mapped["MenuCategory"] = relationship(back_populates="items")
    modifier_groups: Mapped[list["ModifierGroup"]] = relationship(
        back_populates="menu_item", cascade="all, delete-orphan", order_by="ModifierGroup.position"
    )


class ModifierGroup(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "modifier_groups"

    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_selections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_selections: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    menu_item: Mapped["MenuItem"] = relationship(back_populates="modifier_groups")
    options: Mapped[list["ModifierOption"]] = relationship(
        back_populates="modifier_group",
        cascade="all, delete-orphan",
        order_by="ModifierOption.position",
    )


class ModifierOption(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "modifier_options"

    modifier_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("modifier_groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    modifier_group: Mapped["ModifierGroup"] = relationship(back_populates="options")
