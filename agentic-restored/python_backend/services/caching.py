"""
Request-Level Caching Utilities

Provides decorators and utilities for caching frequently accessed configuration data
to reduce database queries and improve response times.
"""

import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar
from datetime import datetime, timedelta
import cachetools

logger = logging.getLogger(__name__)

# Global cache storage
_cache_store: Dict[str, Any] = {}

T = TypeVar('T')


class TTLCache:
    """Simple TTL-based cache with automatic expiration."""
    
    def __init__(self, maxsize: int = 128, ttl: int = 300):
        """
        Initialize TTL cache.
        
        Args:
            maxsize: Maximum number of items to store
            ttl: Time-to-live in seconds (default: 5 minutes)
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = cachetools.TTLCache(maxsize=maxsize, ttl=ttl)
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache if it exists and hasn't expired."""
        return self.cache.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """Store value in cache with TTL."""
        self.cache[key] = value
    
    def clear(self) -> None:
        """Clear all cached values."""
        self.cache.clear()
    
    def invalidate(self, pattern: str) -> int:
        """
        Invalidate all cache keys matching a pattern.
        
        Args:
            pattern: Pattern to match (supports wildcards: *)
            
        Returns:
            Number of keys invalidated
        """
        if not pattern:
            return 0
        
        # Convert pattern to regex
        regex_pattern = pattern.replace('*', '.*')
        keys_to_remove = [k for k in self.cache.keys() if self._matches_pattern(k, regex_pattern)]
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.debug(f"Invalidated {len(keys_to_remove)} cache entries matching pattern: {pattern}")
        
        return len(keys_to_remove)
    
    @staticmethod
    def _matches_pattern(key: str, pattern: str) -> bool:
        """Check if key matches the regex pattern."""
        import re
        return re.match(f"^{pattern}$", key) is not None


# Global cache instance
_global_cache = TTLCache(maxsize=256, ttl=300)  # 5-minute TTL, 256 max items


def cache_with_ttl(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results with TTL.
    
    Usage:
        @cache_with_ttl(ttl=300, key_prefix="llm_provider")
        async def get_default_llm_provider():
            return db_query()
    
    Args:
        ttl: Time-to-live in seconds (default: 300 = 5 minutes)
        key_prefix: Prefix for cache key (if not provided, uses function name)
    
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache_key_prefix = key_prefix or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Generate cache key from function args
            cache_key = _generate_cache_key(cache_key_prefix, args, kwargs)
            
            # Try to get from cache
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Cache miss - call original function
            logger.debug(f"Cache miss: {cache_key}, calling {func.__name__}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            _global_cache.set(cache_key, result)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # Generate cache key from function args
            cache_key = _generate_cache_key(cache_key_prefix, args, kwargs)
            
            # Try to get from cache
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # Cache miss - call original function
            logger.debug(f"Cache miss: {cache_key}, calling {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in cache
            _global_cache.set(cache_key, result)
            
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _generate_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Generate a cache key from function arguments."""
    # Filter out 'self' and 'cls' arguments
    filtered_args = [str(arg) for arg in args if arg not in (None,) and not hasattr(arg, '__dict__')]
    
    # Filter out db sessions and other non-serializable objects
    filtered_kwargs = {
        k: str(v) for k, v in kwargs.items() 
        if k not in ('db', 'session', 'request') and v is not None
    }
    
    # Build cache key
    args_str = "_".join(filtered_args) if filtered_args else ""
    kwargs_str = "_".join(f"{k}:{v}" for k, v in sorted(filtered_kwargs.items()))
    
    parts = [prefix]
    if args_str:
        parts.append(args_str)
    if kwargs_str:
        parts.append(kwargs_str)
    
    cache_key = ":".join(parts) if parts else prefix
    return cache_key


def invalidate_cache(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern.
    
    Usage:
        invalidate_cache("llm_provider*")  # Clear all LLM provider caches
        invalidate_cache("*")  # Clear entire cache
    
    Args:
        pattern: Pattern to match (supports wildcards: *)
    
    Returns:
        Number of cache entries invalidated
    """
    return _global_cache.invalidate(pattern)


def clear_cache() -> None:
    """Clear entire cache."""
    _global_cache.clear()
    logger.info("Cache cleared")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    return {
        "size": len(_global_cache.cache),
        "maxsize": _global_cache.maxsize,
        "ttl": _global_cache.ttl,
        "keys": list(_global_cache.cache.keys()),
    }
