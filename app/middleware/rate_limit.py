"""Rate limiting for sensitive endpoints (login, register, password reset, etc).

Production: Redis-backed fixed-window counter (works correctly across multiple
app instances). If Redis is unreachable, or in tests, we fall back to a per-process
in-memory counter so the API still degrades gracefully rather than hard-failing —
this fallback is NOT safe across multiple instances and is clearly marked as such.
"""
import time
from collections import defaultdict

import structlog
from fastapi import Depends, Request

from app.core.config import settings
from app.core.exceptions import RateLimitError

logger = structlog.get_logger(__name__)

_memory_buckets: dict[str, list[float]] = defaultdict(list)
_redis_client = None


async def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as redis

        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await _redis_client.ping()
        return _redis_client
    except Exception:
        logger.warning("rate_limit.redis_unavailable_using_memory_fallback")
        _redis_client = False  # sentinel: "tried and failed"
        return None


def _client_key(request: Request, bucket: str) -> str:
    ip = request.client.host if request.client else "unknown"
    return f"ratelimit:{bucket}:{ip}"


async def _check_memory(key: str, per_minute: int) -> None:
    now = time.time()
    window_start = now - 60
    bucket = _memory_buckets[key]
    bucket[:] = [t for t in bucket if t > window_start]
    if len(bucket) >= per_minute:
        raise RateLimitError("Too many requests. Please try again later.")
    bucket.append(now)


async def _check_redis(client, key: str, per_minute: int) -> None:
    count = await client.incr(key)
    if count == 1:
        await client.expire(key, 60)
    if count > per_minute:
        raise RateLimitError("Too many requests. Please try again later.")


def rate_limit(bucket_name: str, per_minute: int):
    async def _dependency(request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return
        key = _client_key(request, bucket_name)
        client = await _get_redis()
        if client:
            try:
                await _check_redis(client, key, per_minute)
                return
            except RateLimitError:
                raise
            except Exception:
                logger.warning("rate_limit.redis_error_fallback_to_memory")
        await _check_memory(key, per_minute)

    return _dependency
