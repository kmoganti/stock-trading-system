#!/usr/bin/env python3
"""
Test script to verify Redis caching performance without running full server.
"""
import asyncio
import time
from services.redis_service import get_redis_service, CacheKeys, CacheTTL
from services.watchlist import WatchlistService
from models.database import AsyncSessionLocal


async def test_watchlist_caching():
    """Test watchlist caching performance"""
    print("=" * 70)
    print("🧪 Redis Caching Performance Test")
    print("=" * 70)
    
    # Connect to Redis
    redis = await get_redis_service()
    if not redis.is_connected():
        print("❌ Redis not connected")
        return
    
    print(f"✅ Redis connected")
    print()
    
    # Clear cache to start fresh
    await redis.clear_pattern("*")
    print("🗑️  Cache cleared")
    print()
    
    # Test 1: First call (cache MISS)
    print("Test 1: First watchlist query (cache MISS + database)")
    async with AsyncSessionLocal() as session:
        service = WatchlistService(session)
        start = time.time()
        symbols1 = await service.get_watchlist()
        time1 = (time.time() - start) * 1000
        print(f"   ⏱️  Time: {time1:.2f}ms")
        print(f"   📊 Symbols: {len(symbols1)} found")
    print()
    
    # Test 2: Second call (cache HIT)
    print("Test 2: Second watchlist query (cache HIT)")
    async with AsyncSessionLocal() as session:
        service = WatchlistService(session)
        start = time.time()
        symbols2 = await service.get_watchlist()
        time2 = (time.time() - start) * 1000
        print(f"   ⏱️  Time: {time2:.2f}ms")
        print(f"   📊 Symbols: {len(symbols2)} found")
    print()
    
    # Calculate speedup
    speedup = time1 / time2 if time2 > 0 else 0
    print(f"⚡ Cache speedup: {speedup:.1f}x faster")
    print()
    
    # Test 3: Multiple concurrent reads (all cache HITs)
    print("Test 3: 20 concurrent queries (all cache HITs)")
    start = time.time()
    tasks = []
    for i in range(20):
        async def read_watchlist():
            async with AsyncSessionLocal() as session:
                service = WatchlistService(session)
                return await service.get_watchlist()
        tasks.append(read_watchlist())
    
    results = await asyncio.gather(*tasks)
    time3 = (time.time() - start) * 1000
    print(f"   ⏱️  Total time: {time3:.2f}ms")
    print(f"   ⏱️  Average per request: {time3/20:.2f}ms")
    print(f"   📊 All requests returned {len(results[0])} symbols")
    print()
    
    # Get cache stats
    print("📈 Final Cache Statistics:")
    stats = await redis.get_stats()
    print(f"   Hits: {stats['hits']}")
    print(f"   Misses: {stats['misses']}")
    print(f"   Hit Rate: {stats['hit_rate_percent']}%")
    print(f"   Redis Server Hits: {stats.get('redis_keyspace_hits', 0)}")
    print(f"   Redis Server Misses: {stats.get('redis_keyspace_misses', 0)}")
    print()
    
    # Close Redis
    from services.redis_service import close_redis_service
    await close_redis_service()
    
    print("=" * 70)
    print("✅ Redis caching test completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_watchlist_caching())
