"""
OroGest Lex — Redis Service (Fase 15)
Connection pool, caching layer, and production-grade sliding window rate limiter.

Provides:
- Connection pool management
- Key-value cache with TTL
- Sliding window rate limiter (replaces in-memory for production)
- Session/token blacklist for logout
"""

# ruff: noqa: BLE001
# Every Redis call in this file is wrapped in `except Exception: return <fail-open
# default>` on purpose: Redis here is a best-effort cache/rate-limiter/blacklist,
# not a source of truth, and redis-py can raise many distinct exception types for
# the same underlying condition (connection down, timeout, cluster failover). The
# intent is "any Redis failure degrades gracefully" — narrowing to specific
# exception classes would just mean re-adding every one of them, or worse, an
# uncaught type taking down a request over what should be a soft dependency.

import json
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

# ── Connection Pool ──
_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create the Redis connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _pool


async def close_redis():
    """Close the Redis connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ═══════════════════════════════════════════
# CACHE LAYER
# ═══════════════════════════════════════════
class RedisCache:
    """Simple cache with JSON serialization and TTL."""

    PREFIX = "orogest:cache:"

    @staticmethod
    async def get(key: str) -> Any | None:
        r = await get_redis()
        try:
            value = await r.get(f"{RedisCache.PREFIX}{key}")
            return json.loads(value) if value else None
        except Exception:
            return None

    @staticmethod
    async def set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
        r = await get_redis()
        try:
            await r.setex(
                f"{RedisCache.PREFIX}{key}",
                ttl_seconds,
                json.dumps(value, default=str),
            )
            return True
        except Exception:
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        r = await get_redis()
        try:
            await r.delete(f"{RedisCache.PREFIX}{key}")
            return True
        except Exception:
            return False

    @staticmethod
    async def invalidate_pattern(pattern: str) -> int:
        """Delete all keys matching pattern. Use sparingly."""
        r = await get_redis()
        try:
            keys = []
            async for key in r.scan_iter(f"{RedisCache.PREFIX}{pattern}"):
                keys.append(key)
            if keys:
                await r.delete(*keys)
            return len(keys)
        except Exception:
            return 0


# ═══════════════════════════════════════════
# SLIDING WINDOW RATE LIMITER (Redis-based)
# ═══════════════════════════════════════════
class RedisRateLimiter:
    """
    Production-grade sliding window rate limiter using Redis sorted sets.
    Each request timestamp is stored as a member with score = timestamp.
    Expired entries are pruned on each check.
    """

    PREFIX = "orogest:ratelimit:"

    @staticmethod
    async def check(
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        Returns: (allowed, remaining, retry_after_seconds)
        """
        r = await get_redis()
        full_key = f"{RedisRateLimiter.PREFIX}{key}"
        now = time.time()
        window_start = now - window_seconds

        pipe = r.pipeline()
        try:
            # Remove expired entries
            pipe.zremrangebyscore(full_key, 0, window_start)
            # Count current entries
            pipe.zcard(full_key)
            # Add current request
            pipe.zadd(full_key, {str(now): now})
            # Set TTL on key
            pipe.expire(full_key, window_seconds + 1)

            results = await pipe.execute()
            current_count = results[1]  # zcard result

            if current_count >= max_requests:
                # Over limit — remove the entry we just added
                await r.zrem(full_key, str(now))
                # Calculate retry-after from oldest entry
                oldest = await r.zrange(full_key, 0, 0, withscores=True)
                retry_after = (
                    int(window_seconds - (now - oldest[0][1])) if oldest else window_seconds
                )
                return False, 0, max(1, retry_after)

            remaining = max_requests - current_count - 1
            return True, remaining, 0

        except Exception:
            # If Redis fails, allow the request (fail-open)
            return True, max_requests, 0


# ═══════════════════════════════════════════
# TOKEN BLACKLIST (for logout / token revocation)
# ═══════════════════════════════════════════
class TokenBlacklist:
    """
    Blacklist JWT tokens on logout.
    Stores the token's JTI (JWT ID) with TTL matching token expiration.
    """

    PREFIX = "orogest:blacklist:"

    @staticmethod
    async def add(jti: str, ttl_seconds: int | None = None) -> bool:
        r = await get_redis()
        try:
            ttl = ttl_seconds or (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
            await r.setex(f"{TokenBlacklist.PREFIX}{jti}", ttl, "1")
            return True
        except Exception:
            return False

    @staticmethod
    async def is_blacklisted(jti: str) -> bool:
        r = await get_redis()
        try:
            return bool(await r.exists(f"{TokenBlacklist.PREFIX}{jti}"))
        except Exception:
            return False  # Fail-open: if Redis is down, don't block


# ═══════════════════════════════════════════
# REAL-TIME COUNTERS (for dashboard)
# ═══════════════════════════════════════════
class RealtimeCounters:
    """Atomic counters for dashboard metrics."""

    PREFIX = "orogest:counter:"

    @staticmethod
    async def increment(name: str, amount: int = 1) -> int:
        r = await get_redis()
        try:
            return await r.incrby(f"{RealtimeCounters.PREFIX}{name}", amount)
        except Exception:
            return 0

    @staticmethod
    async def get(name: str) -> int:
        r = await get_redis()
        try:
            val = await r.get(f"{RealtimeCounters.PREFIX}{name}")
            return int(val) if val else 0
        except Exception:
            return 0

    @staticmethod
    async def get_many(names: list[str]) -> dict[str, int]:
        r = await get_redis()
        try:
            pipe = r.pipeline()
            for name in names:
                pipe.get(f"{RealtimeCounters.PREFIX}{name}")
            results = await pipe.execute()
            return {name: int(val) if val else 0 for name, val in zip(names, results)}
        except Exception:
            return {name: 0 for name in names}
