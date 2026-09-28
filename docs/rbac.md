# RBAC (Role-Based Access Control)

## Roles

`Owner > Admin > Manager > Editor > Staff` (see `app/models/enums.RoleName` and
the rank ordering in `app/permissions/definitions.ROLE_RANK`).

- **Owner** — created automatically at registration (one per tenant in this
  build); full permissions; cannot be removed or have its role changed via the
  members API.
- **Admin** — full permissions, same set as Owner, but is a regular membership
  (can be removed, can have its role changed by the Owner).
- **Manager** — operational access: branches, menus (including publish),
  categories, items, modifiers, invite staff, read-only settings+audit+subscription.
- **Editor** — content-focused: read restaurant/branch, edit menu content
  (categories/items/modifiers), no publish, no staff management.
- **Staff** — read-only across restaurant/branch/menu/settings/QR.

## Permission catalog

All permission strings live in `app/permissions/definitions.py` as `Perm.*`
constants (`restaurant.read`, `menu.publish`, `member.invite`, etc — the exact
names from the original spec). The role → permission matrix is a Python
`dict[RoleName, set[str]]` (`ROLE_PERMISSIONS`), so the full authorization
matrix is readable in one place rather than scattered across route handlers.

## Enforcement

Every protected endpoint depends on:

```python
ctx: TenantContext = Depends(require_permission(Perm.MENU_UPDATE))
```

`require_permission` (`app/permissions/dependencies.py`) is a dependency
factory: it first resolves `TenantContext` (see `docs/multi_tenancy.md`), then
checks whether `permissions_for_role(ctx.role)` contains the required
permission, raising `403 FORBIDDEN` if not. There is no other authorization
path — a missing `require_permission(...)` on a route is the only way a check
could be skipped, which is why every router in `app/api/v1/` uses it
consistently (verified by the static review in the final report).

## Privilege-escalation guards (`app/services/member_service.py`)

- A member can never change their own role (`update_role` rejects
  `target.user_id == actor_membership.user_id`).
- The `Owner` role can't be assigned or removed through
  `PATCH /members/{id}` at all — ownership transfer isn't supported by this
  endpoint.
- A non-Owner actor can never assign a role whose `ROLE_RANK` is **≥** their
  own rank. E.g. an Admin (rank 3) cannot promote anyone to Admin or Owner
  (ranks 3/4); a Manager (rank 2) cannot promote anyone to Manager or above.
  Only the Owner can grant Admin.
- The Owner membership can never be removed via `DELETE /members/{id}`.

These are tested exhaustively in `tests/security/test_rbac_privilege_escalation.py`.
