# Storage abstraction

`app/integrations/storage.py` defines `StorageBackend` (an ABC-like base with
`save`/`delete`) and two implementations:

- `LocalStorageBackend` — writes to `LOCAL_STORAGE_DIR` (default `./storage`),
  served back out at `/media/*` (mounted in `app/main.py`). Used when
  `STORAGE_BACKEND=local` (the default, suitable for development).
- `S3StorageBackend` — uses `boto3`, configurable via `S3_BUCKET`,
  `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and
  `S3_ENDPOINT_URL` (the last one lets this point at any S3-compatible
  service — MinIO, R2, Spaces — not just AWS). Used when `STORAGE_BACKEND=s3`.

`get_storage_backend()` returns the configured implementation; calling code
(e.g. a future logo-upload endpoint) depends on `StorageBackend`, never on
`boto3` or `pathlib` directly, so business logic never depends on S3.

## Validation

Every upload goes through `_validate_upload` before being written, regardless
of backend:

- File extension must be one of `.png .jpg .jpeg .webp .gif`.
- Declared `content_type` must be one of the matching image MIME types.
- Size must be under `MAX_UPLOAD_SIZE_MB` (default 5MB).

A random UUID filename is always generated server-side — the original
filename is never used as the storage key (avoids path traversal / collision
/ injection via a malicious filename).

## Note on wiring

The abstraction is complete and tested for its validation logic
(`_validate_upload`), but no HTTP upload endpoint (e.g.
`POST /restaurants/{id}/settings/logo`) is wired into a router in this build
— `RestaurantSettings.logo_url`/`cover_url` are plain string fields settable
via `PATCH /restaurants/{id}/settings` (the client is expected to upload to
its own storage or a signed URL and pass the resulting URL). Adding a
multipart upload endpoint that calls `get_storage_backend().save(...)` and
writes the returned URL into `RestaurantSettings.logo_url` is a small,
isolated addition — see "remaining work" in the final report.
