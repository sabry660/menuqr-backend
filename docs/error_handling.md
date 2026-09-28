# Error handling & API conventions

## Error shape

Every error response, regardless of source, has this shape:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Restaurant not found.",
    "details": {}
  }
}
```

Registered in `app/core/exceptions.py::register_exception_handlers`:

| Exception | HTTP status | code |
|---|---|---|
| `NotFoundError` | 404 | `RESOURCE_NOT_FOUND` |
| `ConflictError` | 409 | `RESOURCE_CONFLICT` |
| `ValidationAppError` | 422 | `VALIDATION_ERROR` |
| `AuthenticationError` | 401 | `AUTHENTICATION_FAILED` |
| `AuthorizationError` | 403 | `FORBIDDEN` |
| `BusinessRuleError` | 400 | `BUSINESS_RULE_VIOLATION` |
| `RateLimitError` | 429 | `RATE_LIMITED` |
| `PlanLimitError` | 402 | `PLAN_LIMIT_EXCEEDED` |
| `RequestValidationError` (Pydantic) | 422 | `VALIDATION_ERROR` (with per-field `details.errors`) |
| `IntegrityError` (DB constraint) | 409 | `INTEGRITY_ERROR` |
| any other `Exception` | 500 | `INTERNAL_SERVER_ERROR` (message never includes the exception text or a traceback) |

Every service function raises one of the typed `AppError` subclasses from
`app/core/exceptions.py` rather than a bare `HTTPException` or letting a
`sqlalchemy` exception propagate — this is what keeps the error shape
consistent across all 14+ router modules. Tested in
`tests/api/test_error_handling.py`.

## Pagination

`app/schemas/common.py`: every list endpoint accepts `?page=1&page_size=20`
(`PaginationParams`, `page >= 1`, `1 <= page_size <= 100`, both validated by
Pydantic — out-of-range values are `422`, not silently clamped) and returns:

```json
{
  "items": [...],
  "pagination": {"page": 1, "page_size": 20, "total_items": 57, "total_pages": 3}
}
```

Used consistently for: restaurants, branches, members, invitations, menus,
QR codes, audit logs. (Categories and items are returned as plain lists,
since in practice a menu has a bounded, small number of categories/items per
category and reorder operations need the full set anyway — see
`docs/menu_system.md`.)

## Soft delete / archiving

Resources with business history worth preserving (`Restaurant`, `Branch`,
`Menu`, `MenuCategory`, `MenuItem`) use an `is_archived` boolean (or, for
`Branch`, a `status` enum including `archived`) rather than a hard `DELETE`.
Archived rows are excluded from list/public endpoints but remain in the
database for audit-trail integrity — an `audit_logs` row referencing a menu
that was later archived still resolves to a real `resource_id`.
`Membership` uses a `status` enum (`active`/`suspended`/`removed`) for the
same reason — a removed staff member's audit history is preserved.

`RefreshToken`/`PasswordResetToken`/`EmailVerificationToken`/`Invitation`
rows are genuinely deleted only by an (unscheduled — see
`docs/background_jobs.md`) cleanup job; day-to-day they're just marked
used/revoked/expired and left in place.

## Slugs

`Tenant.slug`, `Restaurant.slug`, and `Branch.slug` (scoped to its restaurant)
are generated server-side with `python-slugify` from the provided name (or an
explicit `slug` field if supplied, which is itself slugified — so
`"Cool Café!!"` becomes `cool-cafe`). Collisions are resolved by appending
`-2`, `-3`, etc. until a unique value is found (see `_unique_tenant_slug` /
`_unique_restaurant_slug` in the relevant services, and the inline loop in
`branch_service.create_branch`). Restaurant slugs are globally unique (used
as the public URL segment); branch slugs are unique per-restaurant.
