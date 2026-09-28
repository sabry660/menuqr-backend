# Architecture

## Layering

```
Router (app/api/v1/*.py)
  -> validates request shape via Pydantic schemas
  -> resolves auth/tenant/permission via FastAPI dependencies
  -> calls a Service function
  -> returns whatever the Service returns (FastAPI serializes via response_model)

Service (app/services/*.py)
  -> ALL business logic and authorization-relevant queries live here
  -> resolves tenant ownership by joining up to Restaurant.tenant_id (never
     trusts a client-supplied tenant_id/restaurant_id alone)
  -> writes audit log entries alongside the business change, in the same
     transaction (see app/services/audit_service.py)
  -> commits its own transaction

Model (app/models/*.py)
  -> SQLAlchemy 2.x declarative models, one file per domain area
  -> app/models/__init__.py imports everything so relationships resolve and
     Alembic autogenerate/create_all see the full metadata
```

Route handlers are intentionally thin: parse input, call one service function,
return. No business logic, no direct SQL, in `app/api/v1/*.py`.

## Why settings live inside `restaurants.py`

The original spec lists `settings.py` as its own router file. In this
implementation, `RestaurantSettings` is a 1:1 child of `Restaurant` with no
independent lifecycle (it's created automatically when a restaurant is
created, and its only operations are get/update), so its two endpoints
(`GET`/`PATCH /restaurants/{id}/settings`) live in `app/api/v1/restaurants.py`
next to the resource they configure. This avoids an extra near-empty router
module for two endpoints that always require a resolved `restaurant_id`. The
`Settings` tag still appears distinctly in Swagger via each endpoint's tag.

## Why modifiers are nested under menu items, not top-level

A `ModifierGroup`/`ModifierOption` has no meaning outside its parent
`MenuItem` (you can't list "all modifier groups for a tenant" usefully — they
only make sense grouped under the item they modify), so they're exposed as
sub-resources under `.../items/{item_id}/modifier-groups` rather than a
sibling top-level `/modifiers` router. This mirrors how `MenuCategory` is
nested under `Menu` and `MenuItem` under `MenuCategory`.

## Public menu: allow-list, not serialize-and-filter

`app/services/public_service.py` hand-builds the response dict field by field
rather than calling `.model_validate()` on the ORM objects. This is a
deliberate defense: if a private column is added to `Restaurant`,
`RestaurantSettings`, or any menu model in the future, it does **not**
automatically leak through the public endpoint — someone has to explicitly
add it to the allow-list in `public_service.py`. See `docs/public_menu.md`.

## Request flow for a typical protected write

```
PATCH /api/v1/restaurants/{id}/menus/{menu_id}
  -> get_current_user           (app/api/deps.py)   decode & validate JWT
  -> get_tenant_context          (app/api/deps.py)   resolve Membership row for X-Tenant-ID header
  -> require_permission(Perm.X)  (app/permissions/dependencies.py)  check role has permission
  -> menu_service.update_menu    (app/services/menu_service.py)     re-verify tenant ownership via join, apply change, write audit log, commit
```
