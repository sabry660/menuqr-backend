"""Storage abstraction so business logic never depends directly on S3 or the
local filesystem. Swap STORAGE_BACKEND=local|s3 via settings.
"""
import mimetypes
import os
import uuid
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationAppError

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _validate_upload(filename: str, content_type: str, size_bytes: int) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationAppError(f"File extension '{ext}' is not allowed.")
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValidationAppError(f"Content type '{content_type}' is not allowed.")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise ValidationAppError(f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_MB}MB.")


class StorageBackend:
    async def save(self, filename: str, content_type: str, data: bytes) -> str:
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content_type: str, data: bytes) -> str:
        _validate_upload(filename, content_type, len(data))
        ext = Path(filename).suffix.lower()
        key = f"{uuid.uuid4()}{ext}"
        (self.base_dir / key).write_bytes(data)
        return f"/media/{key}"

    async def delete(self, key: str) -> None:
        path = self.base_dir / os.path.basename(key)
        if path.exists():
            path.unlink()


class S3StorageBackend(StorageBackend):
    def __init__(self):
        import boto3

        self.bucket = settings.S3_BUCKET
        self.client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )

    async def save(self, filename: str, content_type: str, data: bytes) -> str:
        _validate_upload(filename, content_type, len(data))
        ext = Path(filename).suffix.lower()
        key = f"{uuid.uuid4()}{ext}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        if settings.S3_ENDPOINT_URL:
            return f"{settings.S3_ENDPOINT_URL}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.{settings.S3_REGION}.amazonaws.com/{key}"

    async def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key.split("/")[-1])


def get_storage_backend() -> StorageBackend:
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend()
    return LocalStorageBackend(settings.LOCAL_STORAGE_DIR)
