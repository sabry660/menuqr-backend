# Menu system

## Hierarchy

```
Restaurant
  -> Menu (draft | published | archived)
    -> MenuCategory (ordered by `position`)
      -> MenuItem (ordered by `position`; price is Numeric(10,2), never float)
        -> ModifierGroup (required/optional, min/max selections; ordered)
          -> ModifierOption (price_delta; ordered)
```

## Lifecycle

A `Menu` starts as `draft`. `POST /menus/{id}/publish` sets it to `published`
(visible on the public endpoint); `POST /menus/{id}/unpublish` reverts it to
`draft`. `DELETE /menus/{id}` archives it (`is_archived=True`,
`status=archived`) — this is a soft delete; archived menus are excluded from
both the authenticated list endpoint and the public endpoint, but the rows
remain for audit/history purposes (see `docs/error_handling.md` for the
general soft-delete stance and `app/models/menu.py`).

## Ordering

`MenuCategory.position` and `MenuItem.position` are plain integers. Reorder
endpoints (`POST .../categories/reorder`, `POST .../items/reorder`) accept the
*complete* ordered list of IDs for that parent and validate that the set of
IDs matches exactly what currently exists (`app/services/menu_service.py`
`reorder_categories`/`reorder_items`) — a partial or mismatched list is
rejected with `422`, rather than silently reordering only some items or
leaving orphaned positions.

## Money

Every price-bearing column (`menu_items.price`, `modifier_options.price_delta`)
is `Numeric(10,2)` in Postgres and `Decimal` in Python/Pydantic — never
`float`. Prices are serialized as JSON strings (Pydantic's default for
`Decimal`) to avoid floating-point round-tripping. `MenuItemCreate.price`
requires `> 0`.

## Modifiers

A `ModifierGroup` enforces `min_selections <= max_selections` at creation
(`422` otherwise) and belongs to exactly one `MenuItem`. `is_required`,
`min_selections`, and `max_selections` describe selection constraints for the
ordering/POS frontend to enforce at order time (this backend doesn't process
orders — MenuQR is a menu-management platform, not a POS).

## Availability vs. visibility

`MenuItem.is_available` (e.g., temporarily out of stock) and
`MenuItem.is_visible` (permanently hidden from the public menu without
deleting it) are independent flags. Only `is_visible=True` items on a
`published` menu appear on the public endpoint; `is_available=False` items
still appear (so diners can see "currently unavailable" items) — this
distinction is left to the frontend to render, both flags are exposed on the
public schema.
