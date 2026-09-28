"""Centralized permission catalog and the default role -> permission matrix.

Permissions are plain strings ("resource.action"). Role -> permission mapping is
data (not scattered `if role == "admin"` checks) so authorization stays in one
place and is easy to audit. See app/permissions/dependencies.py for enforcement.
"""
from app.models.enums import RoleName


class Perm:
    RESTAURANT_READ = "restaurant.read"
    RESTAURANT_UPDATE = "restaurant.update"

    BRANCH_READ = "branch.read"
    BRANCH_CREATE = "branch.create"
    BRANCH_UPDATE = "branch.update"
    BRANCH_DELETE = "branch.delete"

    MENU_READ = "menu.read"
    MENU_CREATE = "menu.create"
    MENU_UPDATE = "menu.update"
    MENU_DELETE = "menu.delete"
    MENU_PUBLISH = "menu.publish"

    CATEGORY_CREATE = "menu_category.create"
    CATEGORY_UPDATE = "menu_category.update"
    CATEGORY_DELETE = "menu_category.delete"

    ITEM_CREATE = "menu_item.create"
    ITEM_UPDATE = "menu_item.update"
    ITEM_DELETE = "menu_item.delete"
    ITEM_REORDER = "menu_item.reorder"

    MODIFIER_MANAGE = "modifier.manage"

    MEMBER_READ = "member.read"
    MEMBER_INVITE = "member.invite"
    MEMBER_UPDATE = "member.update"
    MEMBER_REMOVE = "member.remove"

    SETTINGS_READ = "settings.read"
    SETTINGS_UPDATE = "settings.update"

    AUDIT_READ = "audit.read"

    SUBSCRIPTION_READ = "subscription.read"
    SUBSCRIPTION_MANAGE = "subscription.manage"

    QR_READ = "qr.read"
    QR_CREATE = "qr.create"
    QR_UPDATE = "qr.update"
    QR_DELETE = "qr.delete"


ALL_PERMISSIONS: list[str] = sorted(
    {v for k, v in vars(Perm).items() if not k.startswith("_") and isinstance(v, str)}
)

# Owner and Admin get everything; lower roles get a strict subset.
_OWNER_ADMIN = set(ALL_PERMISSIONS)

_MANAGER = {
    Perm.RESTAURANT_READ,
    Perm.BRANCH_READ,
    Perm.BRANCH_CREATE,
    Perm.BRANCH_UPDATE,
    Perm.MENU_READ,
    Perm.MENU_CREATE,
    Perm.MENU_UPDATE,
    Perm.MENU_PUBLISH,
    Perm.CATEGORY_CREATE,
    Perm.CATEGORY_UPDATE,
    Perm.CATEGORY_DELETE,
    Perm.ITEM_CREATE,
    Perm.ITEM_UPDATE,
    Perm.ITEM_DELETE,
    Perm.ITEM_REORDER,
    Perm.MODIFIER_MANAGE,
    Perm.MEMBER_READ,
    Perm.MEMBER_INVITE,
    Perm.SETTINGS_READ,
    Perm.SETTINGS_UPDATE,
    Perm.QR_READ,
    Perm.QR_CREATE,
    Perm.QR_UPDATE,
    Perm.AUDIT_READ,
    Perm.SUBSCRIPTION_READ,
}

_EDITOR = {
    Perm.RESTAURANT_READ,
    Perm.BRANCH_READ,
    Perm.MENU_READ,
    Perm.MENU_UPDATE,
    Perm.CATEGORY_CREATE,
    Perm.CATEGORY_UPDATE,
    Perm.CATEGORY_DELETE,
    Perm.ITEM_CREATE,
    Perm.ITEM_UPDATE,
    Perm.ITEM_DELETE,
    Perm.ITEM_REORDER,
    Perm.MODIFIER_MANAGE,
    Perm.SETTINGS_READ,
    Perm.QR_READ,
}

_STAFF = {
    Perm.RESTAURANT_READ,
    Perm.BRANCH_READ,
    Perm.MENU_READ,
    Perm.SETTINGS_READ,
    Perm.QR_READ,
}

ROLE_PERMISSIONS: dict[RoleName, set[str]] = {
    RoleName.OWNER: _OWNER_ADMIN,
    RoleName.ADMIN: _OWNER_ADMIN,
    RoleName.MANAGER: _MANAGER,
    RoleName.EDITOR: _EDITOR,
    RoleName.STAFF: _STAFF,
}


def permissions_for_role(role: RoleName) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())


# Roles that a non-owner is never allowed to assign to someone else, to prevent
# privilege escalation via the member-update endpoint.
ROLE_RANK = {
    RoleName.STAFF: 0,
    RoleName.EDITOR: 1,
    RoleName.MANAGER: 2,
    RoleName.ADMIN: 3,
    RoleName.OWNER: 4,
}
