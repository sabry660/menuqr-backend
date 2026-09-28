# Background jobs

`app/jobs/` is reserved for a real task-queue integration (Celery, RQ, arq,
etc.). In this build, the operations the spec calls out as job candidates are
implemented as direct `await`ed calls inside the request/response cycle,
behind the same abstractions a queue-based implementation would use:

- **Invitation emails** — `email_service.send_invitation_email`, called from
  `invitation_service.create_invitation`/`resend_invitation`.
- **Password reset emails** — `email_service.send_password_reset_email`,
  called from `auth_service.request_password_reset`.
- **Verification emails** — `email_service.send_verification_email`, called
  from `auth_service.register_user`/`resend_verification`.
- **Token cleanup** (expired `RefreshToken`/`PasswordResetToken`/
  `EmailVerificationToken`/`Invitation` rows) — not scheduled anywhere in this
  build. Expired rows are excluded by application-level `expires_at` checks
  at read time, but nothing periodically deletes them. A real deployment
  should add a scheduled job (cron, Celery beat, etc.) running something like:

  ```sql
  DELETE FROM refresh_tokens WHERE expires_at < now() - interval '7 days';
  DELETE FROM password_reset_tokens WHERE expires_at < now() - interval '7 days';
  DELETE FROM email_verification_tokens WHERE expires_at < now() - interval '7 days';
  UPDATE invitations SET status = 'expired' WHERE status = 'pending' AND expires_at < now();
  ```

- **Asynchronous audit processing** — audit rows are written synchronously,
  in the same transaction as the business change they record
  (`app/services/audit_service.record`), which is the correct behavior here:
  an audit entry for "menu published" should never be lost because a queue
  worker crashed after the menu was already published. There's no async
  fan-out step to make async in this design.

## Why call sites are already queue-ready

Every "job" above is invoked as `await some_abstraction_call(...)` where
`some_abstraction_call` takes plain, serializable arguments (an email address,
a token, a tenant ID). Moving any of them to a real queue means wrapping that
one call in `queue.enqueue(...)` instead of `await`ing it directly — no
business logic needs to move.
