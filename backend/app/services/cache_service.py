import redis.asyncio as redis
import json
from typing import Optional, Any
import sys
import os

# Add project root to sys.path to allow importing hot_cache
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from backend.app.config import settings
from hot_cache import LRUCache


class CacheService:
    """
    Cache service class using Redis with a fallback to in-memory cache.
    """

    _client: Optional[redis.Redis] = None
    _redis_unavailable: bool = False
    _memory_cache: LRUCache = LRUCache(max_size=100)

    async def _get_redis_client(self) -> Optional[redis.Redis]:
        """Initializes and returns a Redis client if available."""
        if self._redis_unavailable:
            return None

        if self._client is None:
            try:
                print("--- Initializing Redis Client ---")
                # Set a timeout to avoid long waits if Redis is not running
                client = redis.from_url(
                    settings.REDIS_URL, socket_connect_timeout=1, encoding="utf-8", decode_responses=True
                )
                await client.ping()
                self._client = client
                print("--- Redis Client Initialized Successfully. Redis caching is active. ---")
            except Exception as e:
                print(f"--- Redis connection failed: {e}. Falling back to in-memory cache. ---")
                self._redis_unavailable = True
                self._client = None
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        """Fetches a value from the cache by key."""
        client = await self._get_redis_client()
        if client:
            try:
                cached_value = await client.get(key)
                if cached_value:
                    print(f"REDIS CACHE HIT for key: {key}")
                    return json.loads(cached_value)
            except Exception as e:
                print(f"Redis GET error: {e}. Disabling Redis for this session.")
                self.__class__._redis_unavailable = True # Use class attribute to disable for all instances
                self.__class__._client = None

        # Fallback to in-memory cache
        value = self._memory_cache.get(key)
        if value:
            print(f"MEMORY CACHE HIT for key: {key}")
            return value

        print(f"CACHE MISS for key: {key}")
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Sets a key-value pair in the cache with a TTL."""
        client = await self._get_redis_client()
        if client:
            try:
                value_to_cache = json.dumps(value, default=str)
                await client.set(key, value_to_cache, ex=ttl)
                print(f"REDIS CACHE SET for key: {key}")
                return
            except Exception as e:
                print(f"Redis SET error: {e}. Disabling Redis for this session.")
                self.__class__._redis_unavailable = True # Use class attribute to disable for all instances
                self.__class__._client = None

        # Fallback to in-memory cache
        self._memory_cache[key] = value
        print(f"MEMORY CACHE SET for key: {key}")

# --- Dependency Injection Function ---
async def get_cache_service() -> "CacheService":
    """
    Factory function for dependency injection.
    Returns an instance of the CacheService.
    """
    return CacheService()
