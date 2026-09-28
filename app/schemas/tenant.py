import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    InvitationStatus,
    MembershipStatus,
    QRCodeStatus,
    RoleName,
    SubscriptionStatus,
)
from app.schemas.common import ORMModel


class MemberOut(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    role: RoleName
    status: MembershipStatus
    joined_at: datetime


class MemberRoleUpdate(BaseModel):
    role: RoleName


class InvitationCreate(BaseModel):
    email: EmailStr
    role: RoleName


class InvitationOut(ORMModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    role: RoleName
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime


class InvitationAccept(BaseModel):
    token: str
    # Required only if the invited email has no existing account yet.
    password: str | None = Field(default=None, min_length=10, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class QRCodeCreate(BaseModel):
    label: str = Field(min_length=1, max_length=255)
    branch_id: uuid.UUID | None = None


class QRCodeUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    status: QRCodeStatus | None = None


class QRCodeOut(ORMModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID
    branch_id: uuid.UUID | None
    label: str
    target_url: str
    status: QRCodeStatus
    scans_count: int
    created_at: datetime


class SubscriptionOut(BaseModel):
    tenant_id: uuid.UUID
    plan_code: str
    plan_name: str
    status: SubscriptionStatus
    max_branches: int
    max_staff: int
    max_menu_items: int
    current_period_end: datetime | None


class SubscriptionChange(BaseModel):
    plan_code: str


class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None = None
    action: str
    resource_type: str
    resource_id: str | None
    metadata: dict = Field(default_factory=dict)
    ip_address: str | None
    created_at: datetime
