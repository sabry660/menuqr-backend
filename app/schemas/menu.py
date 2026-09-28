import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import MenuStatus
from app.schemas.common import ORMModel


class MenuCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class MenuUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None


class MenuOut(ORMModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    name: str
    description: str | None
    status: MenuStatus
    created_at: datetime
    updated_at: datetime


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    position: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    position: int | None = None


class CategoryOut(ORMModel):
    id: uuid.UUID
    menu_id: uuid.UUID
    name: str
    description: str | None
    position: int


class ReorderRequest(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(min_length=1)


class ModifierOptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    price_delta: Decimal = Decimal("0.00")
    position: int = 0


class ModifierOptionOut(ORMModel):
    id: uuid.UUID
    name: str
    price_delta: Decimal
    position: int
    is_active: bool


class ModifierGroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_required: bool = False
    min_selections: int = 0
    max_selections: int = 1
    position: int = 0
    options: list[ModifierOptionCreate] = Field(default_factory=list)


class ModifierGroupOut(ORMModel):
    id: uuid.UUID
    menu_item_id: uuid.UUID
    name: str
    is_required: bool
    min_selections: int
    max_selections: int
    position: int
    is_active: bool
    options: list[ModifierOptionOut] = Field(default_factory=list)


class MenuItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(gt=Decimal("0"))
    image_url: str | None = None
    is_available: bool = True
    is_visible: bool = True
    position: int = 0
    dietary_tags: list[str] = Field(default_factory=list)


class MenuItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=Decimal("0"))
    image_url: str | None = None
    is_available: bool | None = None
    is_visible: bool | None = None
    dietary_tags: list[str] | None = None


class MenuItemOut(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_available: bool
    is_visible: bool
    position: int
    dietary_tags: list[str] = Field(default_factory=list)
    modifier_groups: list[ModifierGroupOut] = Field(default_factory=list)
