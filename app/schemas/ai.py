"""AI Service schemas for menu generation and import."""
import re
from typing import List, Optional, Literal
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


CUR = r"^[A-Z]{3}$"
LANG = r"^([a-z]{2,3}|mixed)$"

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize_number(v):
    """Deterministic parser. '٩٥' -> 95.0, '12,50' -> 12.5, '1,200' -> 1200.0.
    Ambiguous formats (e.g. '1,25,30') are rejected, not guessed."""
    if not isinstance(v, str):
        return v
    s = re.sub(r"[^\d.,]", "", v.translate(ARABIC_DIGITS).replace("٫", "."))
    if not s:
        return v
    if s.count(".") > 1:
        return v
    if s.count(",") > 1:
        return v
    if "," in s:
        if re.fullmatch(r"\d+,\d{1,2}", s):
            s = s.replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):
            s = s.replace(",", "")
        else:
            return v
    try:
        return float(s)
    except ValueError:
        return v


class Modifier(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(0, ge=0)
    
    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v):
        return normalize_number(v)


class ModifierGroup(BaseModel):
    name: str = Field(min_length=1)
    min_selection: int = Field(0, ge=0)
    max_selection: int = Field(1, ge=0)
    modifiers: List[Modifier] = []

    @model_validator(mode="after")
    def validate_minmax(self):
        if self.max_selection < self.min_selection:
            raise ValueError("max_selection must be >= min_selection")
        return self


class Variant(BaseModel):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)
    sku: Optional[str] = None
    
    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, v):
        return normalize_number(v)


class Item(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    price: float = Field(ge=0)
    compare_at_price: Optional[float] = Field(None, ge=0)
    calories: Optional[int] = Field(None, ge=0)
    variants: List[Variant] = []
    modifier_groups: List[ModifierGroup] = []
    
    @field_validator("price", "compare_at_price", mode="before")
    @classmethod
    def normalize_prices(cls, v):
        return normalize_number(v)

    @model_validator(mode="after")
    def validate_compare(self):
        if self.compare_at_price is not None and self.compare_at_price < self.price:
            raise ValueError("compare_at_price must be >= price")
        return self


class Category(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    items: List[Item] = []


class Menu(BaseModel):
    name: str = Field(min_length=1)
    description: Optional[str] = None
    currency: str = Field(pattern=CUR)
    language: str = Field(pattern=LANG)
    categories: List[Category] = []


class ReviewFlag(BaseModel):
    item: str
    field: Literal["name", "price", "category", "description", "other"]
    reason: str
    confidence: Literal["high", "medium", "low"] = "medium"


class Meta(BaseModel):
    price_source: Literal["extracted", "estimated"] = "extracted"
    warnings: List[str] = []
    review: List[ReviewFlag] = []


class MenuResponse(BaseModel):
    schema_version: str = "1.0"
    menu: Menu
    meta: Meta = Field(default_factory=Meta)


class MenuResponseOut(MenuResponse):
    """API response shape only — never used for the LLM structured-output schema."""
    request_id: Optional[str] = None


class GenerateRequest(BaseModel):
    restaurant_id: str
    branch_id: Optional[str] = None
    prompt: str = Field(min_length=3, max_length=2000)
    cuisine_type: Optional[str] = Field(None, max_length=100)
    currency: str = Field(pattern=CUR)
    language: str = Field("en", pattern=LANG)
    pricing_tier: Optional[str] = Field(None, max_length=50)
    target_categories_count: Optional[int] = Field(None, ge=1, le=20)


class ImportRequest(BaseModel):
    restaurant_id: str
    branch_id: Optional[str] = None
    target_menu_id: Optional[str] = None
    raw_text: Optional[str] = Field(None, max_length=50_000)
    document_base64: Optional[str] = Field(None, max_length=14_500_000)
    document_url: Optional[str] = None
    currency: str = Field(pattern=CUR)
    language: str = Field("en", pattern=LANG)
    auto_publish: bool = False