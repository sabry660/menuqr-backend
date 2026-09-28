# Multi-tenancy & IDOR protection

## The core rule

**The tenant a request operates on is never taken from anything the client
can freely set.** Concretely:

1. The client sends an `X-Tenant-ID` header naming which of *its own*
   tenants it wants to act as (a user can belong to more than one tenant).
2. `get_tenant_context` (`app/api/deps.py`) looks up the `Membership` row for
   `(current_user.id, X-Tenant-ID)`. If no such row exists — including if the
   tenant ID is real but belongs to someone else — the request is rejected
   with `403 FORBIDDEN`, the *same* error whether the tenant doesn't exist or
   just isn't the caller's. This prevents using the header to probe which
   tenant IDs exist.
3. Every subsequent resource lookup in every service function re-derives
   ownership from the database by **joining from the requested resource up to
   `Restaurant.tenant_id == ctx.tenant_id`** — never by trusting that a
   `restaurant_id`/`menu_id`/`branch_id`/etc. path parameter belongs to the
   caller's tenant just because it parses as a UUID.

## Why every service function re-checks, even nested ones

A menu item's ownership chain is
`MenuItem -> MenuCategory -> Menu -> Restaurant -> Tenant`. If we only checked
that `restaurant_id` (from the URL) belongs to the tenant, but not that the
`category_id` and `item_id` in the URL actually belong to *that* restaurant,
a caller from Tenant A could supply their own `restaurant_id` (which passes
the top-level check) together with a guessed `category_id`/`item_id`
belonging to Tenant B, and the query could still resolve if we didn't join
the whole chain. `app/services/menu_service.py`'s `_owned_item` (and its
siblings `_owned_menu`, `_owned_category`) therefore join **all the way** from
the leaf resource up through every intermediate table to `Restaurant.tenant_id`
in a single `WHERE` clause — a partial match anywhere in the chain returns
"not found."

The same pattern is used in `branch_service._owned_branch`,
`qr_service._owned_qr`, `restaurant_service._get_owned_restaurant`, and
`invitation_service`/`member_service` (which scope directly by `tenant_id` on
`Invitation`/`Membership`).

## IDOR test coverage

`tests/security/test_multitenancy_idor.py` and
`tests/api/test_qr_settings_subscriptions_audit.py` exercise:

- Missing `X-Tenant-ID` header → `422`.
- `X-Tenant-ID` for a tenant the caller has no membership in → `403`.
- Cross-tenant `GET`/`PATCH`/`DELETE` on a restaurant → `404` (not `403` —
  we don't confirm the resource exists to an unauthorized caller).
- Cross-tenant access to a nested resource (branch, QR code) even when the
  top-level `restaurant_id` in the path is real → `403`/`404`.
- Restaurant listing is scoped per-tenant (Tenant B never sees Tenant A's
  restaurants in a list response).

## `404` vs `403` for cross-tenant access

Resource-level cross-tenant access intentionally returns `404 RESOURCE_NOT_FOUND`
rather than `403 FORBIDDEN`, because returning `403` would confirm to an
attacker that a resource with that ID exists (just not accessible to them).
`403` is reserved for cases where the caller is provably not a member of the
tenant at all (wrong `X-Tenant-ID`) or lacks the RBAC permission for an
operation on a resource they otherwise *can* see.
