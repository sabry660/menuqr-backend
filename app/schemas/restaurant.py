import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from slugify import slugify

from app.models.enums import BranchStatus
from app.schemas.common import ORMModel


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    locale: str = Field(default="en", max_length=10)
    contact_email: str | None = None
    contact_phone: str | None = None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, v: str | None) -> str | None:
        return slugify(v) if v else v


class RestaurantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    locale: str | None = Field(default=None, max_length=10)
    contact_email: str | None = None
    contact_phone: str | None = None


class RestaurantOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    currency: str
    locale: str
    contact_email: str | None
    contact_phone: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class BranchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    address: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: dict | None = None

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, v: str | None) -> str | None:
        return slugify(v) if v else v


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_hours: dict | None = None
    status: BranchStatus | None = None


class BranchOut(ORMModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    slug: str
    address: str | None
    phone: str | None
    latitude: float | None
    longitude: float | None
    status: BranchStatus
    created_at: datetime
    updated_at: datetime


class RestaurantSettingsUpdate(BaseModel):
    logo_url: str | None = None
    cover_url: str | None = None
    theme_color: str | None = None
    social_links: dict | None = None
    public_description: str | None = None
    internal_notes: str | None = None


class RestaurantSettingsOut(ORMModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    logo_url: str | None
    cover_url: str | None
    theme_color: str | None
    social_links: dict | None = None
    public_description: str | None
    internal_notes: str | None
