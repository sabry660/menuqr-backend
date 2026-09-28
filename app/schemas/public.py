"""Schemas for the unauthenticated public menu endpoint.

These intentionally omit anything internal: no tenant_id, no membership data, no
settings.internal_notes, no audit/subscription info, no archived/unpublished
content. See app/services/public_service.py for the query-level filtering that
backs this.
"""
import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class PublicModifierOption(BaseModel):
    id: uuid.UUID
    name: str
    price_delta: Decimal


class PublicModifierGroup(BaseModel):
    id: uuid.UUID
    name: str
    is_required: bool
    min_selections: int
    max_selections: int
    options: list[PublicModifierOption] = Field(default_factory=list)


class PublicMenuItem(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool
    dietary_tags: list[str] = Field(default_factory=list)
    modifier_groups: list[PublicModifierGroup] = Field(default_factory=list)


class PublicCategory(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    items: list[PublicMenuItem] = Field(default_factory=list)


class PublicMenu(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    categories: list[PublicCategory] = Field(default_factory=list)


class PublicBranding(BaseModel):
    logo_url: str | None
    cover_url: str | None
    theme_color: str | None
    social_links: dict = Field(default_factory=dict)
    public_description: str | None


class PublicRestaurantMenu(BaseModel):
    restaurant_name: str
    restaurant_slug: str
    currency: str
    locale: str
    branding: PublicBranding
    menus: list[PublicMenu] = Field(default_factory=list)
