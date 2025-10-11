"""
Utilities for optimizing async operations and database queries in the trading system.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union
from functools import wraps
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from models.database import AsyncSessionLocal

T = TypeVar('T')
logger = logging.getLogger(__name__)

class AsyncCache:
    """
    Thread-safe async cache for frequently accessed data with TTL support.
    """
    
    def __init__(self, default_ttl: int = 300):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        async with self._lock:
            if key not in self._cache:
                return None
            
            import time
            if time.time() - self._timestamps[key] > self._default_ttl:
                # Expired, remove from cache
                del self._cache[key]
                del self._timestamps[key]
                return None
            
            return self._cache[key]
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional custom TTL."""
        async with self._lock:
            import time
            self._cache[key] = value
            self._timestamps[key] = time.time()
    
    async def delete(self, key: str) -> None:
        """Remove key from cache."""
        async with self._lock:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._timestamps.clear()


def cache_result(ttl: int = 300, key_func: Optional[Callable] = None):
    """
    Decorator for caching async function results.
    
    Args:
        ttl: Time to live in seconds
        key_func: Optional function to generate cache key from function args
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = AsyncCache(ttl)
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # Check cache first
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result)
            return result
        
        # Add cache management methods
        wrapper.cache_clear = cache.clear  # type: ignore
        wrapper.cache_delete = cache.delete  # type: ignore
        return wrapper
    
    return decorator


async def batch_execute(
    operations: List[Callable],
    batch_size: int = 10,
    delay_between_batches: float = 0.1
) -> List[Any]:
    """
    Execute operations in batches to avoid overwhelming resources.
    
    Args:
        operations: List of async callable operations
        batch_size: Number of operations to execute concurrently
        delay_between_batches: Delay in seconds between batches
    
    Returns:
        List of results in the same order as operations
    """
    results = []
    
    for i in range(0, len(operations), batch_size):
        batch = operations[i:i + batch_size]
        batch_results = await asyncio.gather(*[op() for op in batch], return_exceptions=True)
        results.extend(batch_results)
        
        # Add delay between batches (except for the last batch)
        if i + batch_size < len(operations):
            await asyncio.sleep(delay_between_batches)
    
    return results


@asynccontextmanager
async def get_db_session():
    """
    Optimized database session context manager with proper error handling.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def execute_with_retry(
    operation: Callable[..., T],
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[type, ...] = (Exception,)
) -> T:
    """
    Execute an operation with exponential backoff retry logic.
    
    Args:
        operation: Async operation to execute
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exception types to retry on
    
    Returns:
        Result of the operation
    
    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except exceptions as e:
            last_exception = e
            
            if attempt == max_retries:
                break
            
            logger.warning(
                f"Operation failed on attempt {attempt + 1}, "
                f"retrying in {current_delay}s: {str(e)}"
            )
            
            await asyncio.sleep(current_delay)
            current_delay *= backoff_factor
    
    raise last_exception


class RateLimiter:
    """
    Async rate limiter for API calls and other operations.
    """
    
    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_called = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            import time
            now = time.time()
            time_since_last = now - self.last_called
            
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                await asyncio.sleep(sleep_time)
                self.last_called = time.time()
            else:
                self.last_called = now


def rate_limit(calls_per_second: float):
    """
    Decorator for rate limiting async functions.
    
    Args:
        calls_per_second: Maximum number of calls per second
    """
    limiter = RateLimiter(calls_per_second)
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            await limiter.acquire()
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


async def gather_with_concurrency(
    *coroutines,
    limit: int = 10,
    return_exceptions: bool = False
) -> List[Any]:
    """
    Execute coroutines with a concurrency limit.
    
    Args:
        *coroutines: Coroutines to execute
        limit: Maximum number of concurrent executions
        return_exceptions: Whether to return exceptions as results
    
    Returns:
        List of results
    """
    semaphore = asyncio.Semaphore(limit)
    
    async def limited_coroutine(coro):
        async with semaphore:
            return await coro
    
    limited_coroutines = [limited_coroutine(coro) for coro in coroutines]
    return await asyncio.gather(*limited_coroutines, return_exceptions=return_exceptions)


class AsyncBatch:
    """
    Utility for batching async operations efficiently.
    """
    
    def __init__(self, batch_size: int = 50, flush_interval: float = 1.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._items: List[Any] = []
        self._lock = asyncio.Lock()
        self._last_flush = 0.0
        self._processor: Optional[Callable] = None
    
    async def add(self, item: Any) -> None:
        """Add item to batch."""
        async with self._lock:
            self._items.append(item)
            
            import time
            now = time.time()
            
            # Flush if batch is full or flush interval exceeded
            if (len(self._items) >= self.batch_size or 
                now - self._last_flush >= self.flush_interval):
                await self._flush()
    
    async def _flush(self) -> None:
        """Flush current batch items."""
        if not self._items:
            return
        
        items_to_process = self._items.copy()
        self._items.clear()
        
        import time
        self._last_flush = time.time()
        
        if self._processor:
            await self._processor(items_to_process)
    
    def set_processor(self, processor: Callable[[List[Any]], Any]) -> None:
        """Set the batch processor function."""
        self._processor = processor
    
    async def flush(self) -> None:
        """Manually flush current batch."""
        async with self._lock:
            await self._flush()