# Subscriptions & entitlements

## Design

`app/services/subscription_service.py` and the `Plan`/`Subscription` models
are deliberately billing-provider-agnostic, per the spec ("do not tightly
couple the domain to Stripe"). `Subscription.provider` (default `"internal"`)
and `Subscription.provider_ref` exist so a real processor (Stripe, Paddle,
etc.) can be plugged in later by writing to those columns from a webhook
handler, without changing anything about how entitlements are enforced.

Three plans ship by default (seeded on app startup by
`ensure_plans_seeded`, called from `app/main.py`'s lifespan handler):

| Plan | max_branches | max_staff | max_menu_items | price (display only) |
|---|---|---|---|---|
| Free | 1 | 3 | 30 | $0 |
| Pro | 5 | 15 | 300 | $29/mo |
| Business | 50 | 100 | 5000 | $99/mo |

Every tenant gets a `Free` subscription automatically the first time
`get_or_create_subscription` is called for it (lazy creation — there's no
explicit "assign free plan" step at registration).

## Enforcement points

- `branch_service.create_branch` calls `assert_can_add_branch` before
  inserting.
- `invitation_service.create_invitation` calls `assert_can_add_staff` before
  creating an invitation (so you can't out-invite your seat limit even before
  anyone accepts).
- `menu_service.create_item` calls `assert_can_add_menu_item` before
  inserting.

All three raise `PlanLimitError` → `402 PAYMENT_REQUIRED` with code
`PLAN_LIMIT_EXCEEDED`. Tested in `tests/api/test_restaurants_branches.py`
(`test_branch_plan_limit_enforced`) and
`tests/api/test_menus_items_modifiers.py` (`test_menu_item_plan_limit_enforced`).

## Endpoints

```
GET  /api/v1/subscription                 current plan + computed limits
POST /api/v1/subscription/change-plan     {"plan_code": "pro"}
```

Changing plans is instantaneous in this build (no proration, no payment
collection) — appropriate for a billing-agnostic core; a real payment
provider integration would call `change_plan` from its webhook handler after
confirming payment.
