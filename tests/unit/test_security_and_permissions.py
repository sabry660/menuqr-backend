from app.core.security import (
    generate_secure_token,
    hash_password,
    hash_secret_token,
    verify_password,
)
from app.models.enums import RoleName
from app.permissions.definitions import Perm, ROLE_RANK, permissions_for_role


def test_password_hash_and_verify_roundtrip():
    hashed = hash_password("SuperSecret123")
    assert hashed != "SuperSecret123"
    assert verify_password("SuperSecret123", hashed)
    assert not verify_password("WrongPassword", hashed)


def test_secure_token_is_high_entropy_and_unique():
    tokens = {generate_secure_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 32 for t in tokens)


def test_hash_secret_token_is_deterministic_and_one_way():
    token = "some-raw-secret"
    h1 = hash_secret_token(token)
    h2 = hash_secret_token(token)
    assert h1 == h2
    assert h1 != token


def test_owner_and_admin_have_full_permission_set():
    owner_perms = permissions_for_role(RoleName.OWNER)
    admin_perms = permissions_for_role(RoleName.ADMIN)
    assert Perm.SUBSCRIPTION_MANAGE in owner_perms
    assert Perm.MEMBER_REMOVE in admin_perms


def test_staff_has_only_read_permissions():
    staff_perms = permissions_for_role(RoleName.STAFF)
    assert Perm.MENU_READ in staff_perms
    assert Perm.MENU_CREATE not in staff_perms
    assert Perm.MEMBER_REMOVE not in staff_perms


def test_role_rank_is_strictly_ordered():
    assert ROLE_RANK[RoleName.STAFF] < ROLE_RANK[RoleName.EDITOR] < ROLE_RANK[RoleName.MANAGER]
    assert ROLE_RANK[RoleName.MANAGER] < ROLE_RANK[RoleName.ADMIN] < ROLE_RANK[RoleName.OWNER]
