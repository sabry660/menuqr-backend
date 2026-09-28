# Email abstraction

`app/services/email_service.py` defines `EmailMessage` and `send()`, which
dispatches to `_console_send` (dev — prints to stdout, used whenever
`EMAIL_PROVIDER=console`, the default) or `_smtp_send` (prints via `smtplib`,
used when `EMAIL_PROVIDER=smtp` with `SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/
`SMTP_PASSWORD` configured).

Four typed helpers build the actual messages so call sites never construct
email bodies inline:

- `send_verification_email`
- `send_password_reset_email`
- `send_invitation_email`
- `send_invitation_accepted_email`

## Never sends real email during tests

`tests/conftest.py`'s `client` fixture monkeypatches `email_service.send` to
append to an in-memory list (`client.sent_emails`) instead of dispatching
anywhere. Tests that need to complete a token-based flow (password reset,
email verification, invitation accept) read the raw token back out of
`client.sent_emails[i].body` rather than querying the database directly —
this doubles as a check that the email actually contains a working link.

## Production

Set `EMAIL_PROVIDER=smtp` and the `SMTP_*` variables. For a provider with its
own SDK (SES, SendGrid, Postmark, etc.) rather than plain SMTP, replace the
body of `_smtp_send` with a call to that SDK — the four typed helpers and
every call site elsewhere in the codebase are unaffected, since they only
depend on the `send(EmailMessage)` interface.
