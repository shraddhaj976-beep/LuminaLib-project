import time

import redis.asyncio as redis

from app.core.config import settings

_redis_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def revoke_token(jti: str, exp: int) -> None:
    ttl = max(0, int(exp) - int(time.time()))
    client = _get_client()
    await client.set(f"revoked:{jti}", "1", ex=ttl)


async def token_is_revoked(jti: str) -> bool:
    client = _get_client()
    value = await client.get(f"revoked:{jti}")
    return value == "1"
