"""
Redis caching service for trading system.

Provides async Redis operations with connection pooling, error handling,
and automatic TTL management.
"""
import json
import logging
import pickle
from typing import Any, Optional, Union
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

logger = logging.getLogger(__name__)


class RedisService:
    """
    Async Redis service for caching API responses and database queries.
    
    Features:
    - Connection pooling
    - Automatic serialization/deserialization
    - TTL management
    - Error handling with fallback
    - Cache statistics
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
        decode_responses: bool = False
    ):
        """
        Initialize Redis service with connection pool.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number (0-15)
            password: Redis password (if any)
            max_connections: Maximum connections in pool
            decode_responses: Whether to decode responses to strings
        """
        self.pool = ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            max_connections=max_connections,
            decode_responses=decode_responses,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        self._client: Optional[redis.Redis] = None
        self._connected = False
        
        # Cache statistics
        self._hits = 0
        self._misses = 0
        self._errors = 0
    
    async def connect(self) -> bool:
        """
        Connect to Redis server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._client = redis.Redis(connection_pool=self.pool)
            await self._client.ping()
            self._connected = True
            logger.info("✅ Redis connection established")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Redis and close connection pool."""
        if self._client:
            await self._client.close()
            await self.pool.disconnect()
            self._connected = False
            logger.info("Redis connection closed")
    
    async def get(
        self,
        key: str,
        default: Any = None,
        deserialize: str = "json"
    ) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            deserialize: Deserialization method ('json', 'pickle', or 'raw')
        
        Returns:
            Cached value or default
        """
        if not self._connected:
            return default
        
        try:
            value = await self._client.get(key)
            
            if value is None:
                self._misses += 1
                return default
            
            self._hits += 1
            
            # Deserialize based on method
            if deserialize == "json":
                return json.loads(value)
            elif deserialize == "pickle":
                return pickle.loads(value)
            else:  # raw
                return value
                
        except Exception as e:
            self._errors += 1
            logger.warning(f"Redis GET error for key '{key}': {e}")
            return default
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        serialize: str = "json"
    ) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
            serialize: Serialization method ('json', 'pickle', or 'raw')
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            return False
        
        try:
            # Serialize based on method
            if serialize == "json":
                serialized = json.dumps(value, default=str)
            elif serialize == "pickle":
                serialized = pickle.dumps(value)
            else:  # raw
                serialized = value
            
            if ttl:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            
            return True
            
        except Exception as e:
            self._errors += 1
            logger.warning(f"Redis SET error for key '{key}': {e}")
            return False
    
    async def delete(self, *keys: str) -> int:
        """
        Delete one or more keys from cache.
        
        Args:
            *keys: Keys to delete
        
        Returns:
            Number of keys deleted
        """
        if not self._connected or not keys:
            return 0
        
        try:
            return await self._client.delete(*keys)
        except Exception as e:
            self._errors += 1
            logger.warning(f"Redis DELETE error: {e}")
            return 0
    
    async def exists(self, *keys: str) -> int:
        """
        Check if keys exist.
        
        Args:
            *keys: Keys to check
        
        Returns:
            Number of keys that exist
        """
        if not self._connected or not keys:
            return 0
        
        try:
            return await self._client.exists(*keys)
        except Exception as e:
            logger.warning(f"Redis EXISTS error: {e}")
            return 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration time for a key.
        
        Args:
            key: Cache key
            ttl: Time to live in seconds
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            return False
        
        try:
            return await self._client.expire(key, ttl)
        except Exception as e:
            logger.warning(f"Redis EXPIRE error for key '{key}': {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., "user:*", "cache:api:*")
        
        Returns:
            Number of keys deleted
        """
        if not self._connected:
            return 0
        
        try:
            keys = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self._client.delete(*keys)
            return 0
            
        except Exception as e:
            logger.warning(f"Redis CLEAR_PATTERN error for pattern '{pattern}': {e}")
            return 0
    
    async def flush_db(self) -> bool:
        """
        Clear all keys from current database.
        
        Returns:
            True if successful, False otherwise
        """
        if not self._connected:
            return False
        
        try:
            await self._client.flushdb()
            logger.info("Redis database flushed")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            return False
    
    async def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        
        stats = {
            "hits": self._hits,
            "misses": self._misses,
            "errors": self._errors,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "connected": self._connected
        }
        
        # Get Redis server info if connected
        if self._connected:
            try:
                info = await self._client.info("stats")
                stats["redis_total_commands"] = info.get("total_commands_processed", 0)
                stats["redis_keyspace_hits"] = info.get("keyspace_hits", 0)
                stats["redis_keyspace_misses"] = info.get("keyspace_misses", 0)
                
                # Calculate Redis server hit rate
                redis_hits = stats["redis_keyspace_hits"]
                redis_misses = stats["redis_keyspace_misses"]
                redis_total = redis_hits + redis_misses
                if redis_total > 0:
                    stats["redis_hit_rate_percent"] = round(redis_hits / redis_total * 100, 2)
                
            except Exception as e:
                logger.warning(f"Could not fetch Redis server stats: {e}")
        
        return stats
    
    async def reset_stats(self):
        """Reset cache statistics counters."""
        self._hits = 0
        self._misses = 0
        self._errors = 0
        logger.info("Redis statistics reset")
    
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected


# Cache key prefixes for organization
class CacheKeys:
    """Standard cache key prefixes."""
    
    # API response caching (30-60 seconds)
    API_HOLDINGS = "api:holdings"
    API_POSITIONS = "api:positions"
    API_MARGINS = "api:margins"
    API_ORDERS = "api:orders"
    API_CANDLES = "api:candles:{symbol}:{interval}:{from_date}:{to_date}"
    API_CONTRACTS = "api:contracts:{exchange}"
    
    # Database query caching (5-10 minutes)
    DB_WATCHLIST = "db:watchlist:all"
    DB_WATCHLIST_ITEM = "db:watchlist:{symbol}"
    DB_SIGNALS = "db:signals:recent:{limit}"
    DB_SETTINGS = "db:settings:all"
    DB_RISK_EVENTS = "db:risk:recent:{limit}"
    
    # Computed data caching (1-5 minutes)
    PORTFOLIO_SUMMARY = "computed:portfolio:summary"
    PORTFOLIO_PERFORMANCE = "computed:portfolio:performance"
    SIGNAL_ANALYSIS = "computed:signals:analysis"
    
    @staticmethod
    def format_key(template: str, **kwargs) -> str:
        """Format cache key with parameters."""
        return template.format(**kwargs)


# Default TTL values (in seconds)
class CacheTTL:
    """Standard TTL values for different data types."""
    
    # API responses
    API_FAST = 30          # Fast-changing data (holdings, positions)
    API_MEDIUM = 300       # Medium-changing data (margins, orders)
    API_SLOW = 3600        # Slow-changing data (contracts, symbols)
    API_HISTORICAL = 86400 # Historical data (candles) - 24 hours
    
    # Database queries
    DB_FAST = 60           # Frequently updated tables
    DB_MEDIUM = 300        # Medium update frequency
    DB_SLOW = 600          # Rarely updated tables
    
    # Computed data
    COMPUTED_FAST = 60     # Real-time computations
    COMPUTED_MEDIUM = 300  # Aggregated data
    
    # User sessions
    SESSION = 3600         # 1 hour


# Singleton instance
_redis_instance: Optional[RedisService] = None


async def get_redis_service() -> RedisService:
    """
    Get or create Redis service singleton.
    
    Returns:
        RedisService instance
    """
    global _redis_instance
    
    if _redis_instance is None:
        _redis_instance = RedisService()
        await _redis_instance.connect()
    
    return _redis_instance


async def close_redis_service():
    """Close Redis service singleton."""
    global _redis_instance
    
    if _redis_instance:
        await _redis_instance.disconnect()
        _redis_instance = None
