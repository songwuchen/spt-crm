"""
Simple Redis cache layer with fallback to in-memory dict when Redis is unavailable.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("cache")

_redis_client = None
_memory_cache: dict[str, tuple[float, Any]] = {}  # key -> (expire_ts, value)


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        from app.config import settings
        url = getattr(settings, "REDIS_URL", None)
        if url:
            _redis_client = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
            _redis_client.ping()
            logger.info("Redis cache connected: %s", url)
            return _redis_client
    except Exception as e:
        logger.warning("Redis not available, using memory cache: %s", e)
        _redis_client = False  # Mark as unavailable
    return None


def cache_backend() -> dict:
    """报告缓存后端状态，供 /system/health 验证 Redis 是否真正启用。

    configured=True 但 backend=memory 说明有问题（redis 库未装、REDIS_URL 错、或 redis 不可达）。
    """
    from app.config import settings
    configured = bool(getattr(settings, "REDIS_URL", ""))
    r = _get_redis()
    if r:
        try:
            r.ping()
            return {"backend": "redis", "configured": True, "connected": True}
        except Exception:
            return {"backend": "memory", "configured": configured, "connected": False}
    return {"backend": "memory", "configured": configured, "connected": False}


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache. Returns None on miss."""
    r = _get_redis()
    if r:
        try:
            val = r.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.debug("Redis GET failed for key=%s: %s", key, e)
        return None

    # Fallback: memory cache
    import time
    entry = _memory_cache.get(key)
    if entry:
        expire_ts, val = entry
        if expire_ts > time.time():
            return val
        del _memory_cache[key]
    return None


async def cache_set(key: str, value: Any, ttl: int = 300):
    """Set value in cache with TTL in seconds."""
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
            return
        except Exception as e:
            logger.debug("Redis SET failed for key=%s: %s", key, e)

    # Fallback: memory cache
    import time
    _memory_cache[key] = (time.time() + ttl, value)


async def cache_delete(key: str):
    """Delete a key from cache."""
    r = _get_redis()
    if r:
        try:
            r.delete(key)
            return
        except Exception as e:
            logger.debug("Redis DELETE failed for key=%s: %s", key, e)
    _memory_cache.pop(key, None)


async def cache_delete_pattern(pattern: str):
    """Delete all keys matching a pattern."""
    r = _get_redis()
    if r:
        try:
            keys = r.keys(pattern)
            if keys:
                r.delete(*keys)
            return
        except Exception as e:
            logger.debug("Redis DELETE_PATTERN failed for pattern=%s: %s", pattern, e)
    # Memory fallback: simple prefix match
    prefix = pattern.rstrip("*")
    to_del = [k for k in _memory_cache if k.startswith(prefix)]
    for k in to_del:
        del _memory_cache[k]
