from __future__ import annotations

import redis

from codepilot.core.config import Settings


def get_redis(settings: Settings) -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def ping_redis(settings: Settings) -> bool:
    try:
        return bool(get_redis(settings).ping())
    except redis.RedisError:
        return False
