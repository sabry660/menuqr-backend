# QR codes

Each `QRCode` belongs to exactly one `Restaurant` and, optionally, one
`Branch` (nullable — a restaurant-wide QR code has no branch). `target_url` is
generated server-side at creation time as `{FRONTEND_URL}/menu/{restaurant.slug}`
— the frontend is expected to render this as an actual QR code image (this
backend does not generate QR image bytes; that is a frontend/rendering
concern, and `target_url` is all a frontend QR-rendering library needs).

## Endpoints

```
POST   /api/v1/restaurants/{restaurant_id}/qr-codes
GET    /api/v1/restaurants/{restaurant_id}/qr-codes
GET    /api/v1/restaurants/{restaurant_id}/qr-codes/{qr_id}
PATCH  /api/v1/restaurants/{restaurant_id}/qr-codes/{qr_id}
POST   /api/v1/restaurants/{restaurant_id}/qr-codes/{qr_id}/deactivate
```

`branch_id`, if supplied, is validated to belong to the same
`restaurant_id` (`422` otherwise). Tenant ownership is enforced the same way
as every other nested resource — see `docs/multi_tenancy.md`.

`scans_count` exists on the model for a future scan-tracking redirect
endpoint; incrementing it is out of scope for this build (no order/analytics
pipeline exists yet) and is called out under "remaining work" in the final
report rather than being silently half-wired.
