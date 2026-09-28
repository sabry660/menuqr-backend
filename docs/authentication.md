# Authentication

## Overview

- Passwords: bcrypt via `passlib` (`app/core/security.py`). Never logged, never
  returned in any response (see `docs/error_handling.md` for how the exception
  handlers avoid leaking internals, and `app/core/logging.py` for structured-log
  redaction of any field named `password`/`token`/`secret`/etc.).
- Access tokens: JWT, HS256, 15 minutes default (`ACCESS_TOKEN_EXPIRE_MINUTES`).
  Stateless — not stored server-side.
- Refresh tokens: JWT, 30 days default (`REFRESH_TOKEN_EXPIRE_DAYS`), **and**
  persisted server-side as a `RefreshToken` row (hash only — `hash_secret_token`,
  SHA-256 — never the raw token) so they can be revoked and reuse can be detected.

## Registration

`POST /api/v1/auth/register` creates a `User`, a new `Tenant` (named from
`tenant_name`), and a `Membership` with role `OWNER` in a single transaction
(`app/services/auth_service.register_user`). It also creates an
`EmailVerificationToken` and sends a verification email (console provider in
dev). Duplicate emails are rejected with a generic `409 RESOURCE_CONFLICT` —
the message is the same whether the account existed with a different
password or not, to avoid confirming account existence through response
differences.

## Login

`POST /api/v1/auth/login` verifies the password with a constant-shape failure
path: an unknown email and a known email with a wrong password both return
the same `401 AUTHENTICATION_FAILED` with the same message, so the endpoint
cannot be used to enumerate registered emails.

## Refresh rotation & reuse detection

Every successful `POST /api/v1/auth/refresh`:

1. Decodes and validates the presented refresh JWT.
2. Looks up the corresponding `RefreshToken` row by `jti`.
3. If that row is **already revoked**, this is treated as a stolen/replayed
   token: the entire session family for that user (every `RefreshToken` row,
   not just this one) is revoked immediately, and the request is rejected.
   This is "refresh token reuse detection" — a legitimate client only ever
   presents a given refresh token once (it immediately gets a new one back),
   so a second presentation of an already-rotated token means someone else
   has a copy of it.
4. Otherwise, the old row is marked revoked (`revoked_at`, `replaced_by_jti`),
   a new `RefreshToken` row is created, and a new access+refresh token pair is
   returned.

Tested in `tests/api/test_auth.py::test_refresh_token_reuse_is_detected_and_revokes_session`.

## Logout

`POST /api/v1/auth/logout` revokes the specific presented refresh token.
Idempotent — logging out with an already-invalid token still returns `204`.

## Password reset

1. `POST /api/v1/auth/forgot-password` — always returns `202` with the same
   message regardless of whether the email exists (no enumeration). If it
   does exist, a `PasswordResetToken` (SHA-256 hash of a random 32-byte token)
   is created with a 60-minute expiry and emailed.
2. `POST /api/v1/auth/reset-password` — validates the token is unused and
   unexpired, updates the password hash, marks the token used, and **revokes
   every active refresh token for that user** (a password reset should log out
   all existing sessions).

## Email verification

`POST /api/v1/auth/verify-email` and `POST /api/v1/auth/resend-verification`
follow the same single-use-hashed-token pattern. Resend also avoids leaking
account existence/verification state.

## Session/token security properties

- Refresh tokens are single-use (rotation on every refresh).
- A stolen-and-replayed refresh token triggers full session revocation for
  that user, not just invalidation of the one token.
- All secret tokens (refresh, password reset, email verification, invitation)
  are stored only as SHA-256 hashes; the raw value exists only in the HTTP
  response / outgoing email, never in the database.
- JWTs carry a `jti` and `exp`; expired/invalid tokens are rejected before any
  database lookup happens.
