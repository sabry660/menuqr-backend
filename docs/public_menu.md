# Public menu endpoint

`GET /api/v1/public/{restaurant_slug}/menu` — no authentication required.

## What it returns

- Restaurant name/slug/currency/locale.
- Branding: logo/cover URLs, theme color, social links, public description
  (from `RestaurantSettings`, excluding `internal_notes`).
- Every `Menu` with `status == published` and `is_archived == False`.
- Within each menu, every `MenuCategory` with `is_archived == False`, ordered
  by `position`.
- Within each category, every `MenuItem` with `is_archived == False and
  is_visible == True`, ordered by `position`.
- Within each item, every active `ModifierGroup` (`is_active == True`) and its
  active `ModifierOption`s, ordered by `position`.

## What it never returns

- `tenant_id`, `Restaurant.id`'s tenant linkage, or anything about the tenant.
- `Membership`/staff/user data.
- `AuditLog` entries.
- `Subscription`/billing data.
- `RestaurantSettings.internal_notes`.
- Draft or archived menus/categories/items, or invisible/inactive items,
  modifier groups, or options.
- Archived restaurants (a slug belonging to an archived restaurant 404s).

## Implementation approach

`app/services/public_service.get_public_menu` builds the response as a plain
dict, field by field, rather than serializing the ORM objects directly
through a `from_attributes` schema. This is an explicit allow-list: a new
column added to `Restaurant`/`RestaurantSettings`/`Menu`/... in the future
does not automatically appear in the public response — someone has to
deliberately add it here. See `tests/api/test_public_menu.py` for the
leakage-prevention tests, including one that plants a secret string in
`internal_notes` and asserts it never appears in the public response body.
