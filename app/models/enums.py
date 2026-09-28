import enum


class RoleName(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    EDITOR = "editor"
    STAFF = "staff"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REMOVED = "removed"


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class MenuStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class BranchStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class QRCodeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PlanCode(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class AuditAction(str, enum.Enum):
    MEMBER_INVITED = "member.invited"
    MEMBER_ROLE_UPDATED = "member.role_updated"
    MEMBER_REMOVED = "member.removed"
    INVITATION_CREATED = "invitation.created"
    INVITATION_RESENT = "invitation.resent"
    INVITATION_REVOKED = "invitation.revoked"
    INVITATION_ACCEPTED = "invitation.accepted"
    MENU_CREATED = "menu.created"
    MENU_UPDATED = "menu.updated"
    MENU_PUBLISHED = "menu.published"
    MENU_UNPUBLISHED = "menu.unpublished"
    MENU_DELETED = "menu.deleted"
    CATEGORY_CREATED = "category.created"
    CATEGORY_UPDATED = "category.updated"
    CATEGORY_DELETED = "category.deleted"
    ITEM_CREATED = "item.created"
    ITEM_UPDATED = "item.updated"
    ITEM_DELETED = "item.deleted"
    SETTINGS_UPDATED = "settings.updated"
    RESTAURANT_CREATED = "restaurant.created"
    RESTAURANT_UPDATED = "restaurant.updated"
    BRANCH_CREATED = "branch.created"
    BRANCH_UPDATED = "branch.updated"
    BRANCH_DELETED = "branch.deleted"
    QR_CREATED = "qr.created"
    QR_UPDATED = "qr.updated"
    QR_DEACTIVATED = "qr.deactivated"
    SUBSCRIPTION_CHANGED = "subscription.changed"
