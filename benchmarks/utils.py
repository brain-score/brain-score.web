from typing import Callable, Optional, Dict, Any, List, Union
from django.contrib.auth.models import User
import hashlib
import logging
import requests
from functools import wraps
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpRequest

logger = logging.getLogger(__name__)

# Cache utility functions and decorators
def cache_get_context(timeout=24 * 60 * 60) -> Callable:  # 24 hour cache by default
    """
    Decorator that caches results of get_context function for faster loading of leaderboard view and model card view.
    Two-level caching:
        - Global cache for public data
        - User-specific cache for non-public data
    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
    """
    def decorator(func):  # Take function to be decorated (i.e., get_context)
        @wraps(func)  # Preserving original function's metadata attributes
        def wrapper(
            user: Optional[User] = None,
            domain: str = "vision",
            benchmark_filter: Optional[str] = None,
            model_filter: Optional[str] = None,
            show_public: bool = False
        ) -> Dict[str, Any]:
            """
            Wrapper function that implements the caching logic.
            
            Args:
                user (Optional[User]): The user requesting the context, if any
                domain (str): The domain to get context for (e.g. "vision", "language")
                benchmark_filter (Optional[str]): Filter to apply to benchmarks
                model_filter (Optional[str]): Filter to apply to models
                show_public (bool): Whether to show only public data
            
            Returns:
                Dict[str, Any]: The context dictionary containing models, benchmarks, and other data
            """            
            # Get cache version from cache or set to 1 if not exists
            cache_version_key = f'cache_version_{domain}'
            from django.core.cache import caches, cache
            
            # Try to use Redis cache if available, otherwise fall back to default cache
            try:
                redis_cache = caches['redis']
                cache_version = redis_cache.get(cache_version_key, 1)
                logger.info(f"Using Redis cache for domain {domain}")
            except Exception as e:
                # Redis cache not available, use default cache
                redis_cache = cache
                cache_version = cache.get(cache_version_key, 1)
                logger.info(f"Redis cache not available for domain {domain}, using default cache: {e}")
            
            # Generate a more specific cache key that includes model_filter and benchmark_filter info
            if show_public and not user:
                # (CASE 1: Public data) Create unique key for public data cache
                key_parts = ['global_context', domain, 'public', f'v{cache_version}']
                if benchmark_filter:
                    key_parts.append('benchmark_filtered')
                if model_filter:
                    key_parts.append('model_filtered')
            elif user:
                # (CASE 2: User data) Create unique key for user-specific cache that includes public data
                key_parts = ['user_context', domain, str(user.id), str(show_public), f'v{cache_version}']
                if benchmark_filter:
                    key_parts.append('benchmark_filtered')
                if model_filter:
                    key_parts.append('model_filtered')
            else:
                # (CASE 3: No caching) Neither public nor user-specific
                return func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                          model_filter=model_filter, show_public=show_public)
            
            # Generate SHA256 hash
            cache_key = hashlib.sha256('_'.join(key_parts).encode()).hexdigest()
            
            # Try to get cached result
            try:
                import time
                cache_start = time.time()
                cached_result = redis_cache.get(cache_key)
                cache_end = time.time()
                logger.info(f"Cache GET took {cache_end - cache_start:.3f}s for key {cache_key[:50]}...")
                
                if cached_result is not None:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cached_result
            except Exception as e:
                logger.warning(f"Cache get failed for key {cache_key}: {e}, falling back to direct execution")

            # If no cache found, calculate result
            logger.debug(f"Cache miss for key: {cache_key}")
            func_start = time.time()
            result = func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                        model_filter=model_filter, show_public=show_public)
            func_end = time.time()
            logger.info(f"Function execution took {func_end - func_start:.3f}s")
            
            # For user contexts, also cache the public data within the user context
            if user and not show_public:
                result['public_models'] = [m for m in result['models'] if getattr(m, 'public', True)]
            
            # Store result in cache
            try:
                set_start = time.time()
                redis_cache.set(cache_key, result, timeout)
                set_end = time.time()
                logger.info(f"Cache SET took {set_end - set_start:.3f}s, size ~{len(str(result))} chars")
                logger.debug(f"Cached result for key: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set failed for key {cache_key}: {e}, continuing without caching")
            return result

        return wrapper
    return decorator


def cache_base_model_query(timeout: int = 24 * 60 * 60) -> Callable:
    """
    Decorator that caches results of base model query function for faster loading.
    
    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
    
    Returns:
        Callable: Decorated function that implements caching logic
    """
    def decorator(func: Callable[[str], Dict[str, Any]]) -> Callable[[str], Dict[str, Any]]:
        @wraps(func)
        def wrapper(domain: str = "vision") -> Dict[str, Any]:
            """
            Wrapper function that implements the caching logic for base model queries.
            
            Args:
                domain (str): The domain to get base models for (e.g. "vision", "language")
            
            Returns:
                Dict[str, Any]: The base model query results
            """
            # Create unique key for domain
            key_parts = ['base_model_query', domain]
            cache_key = hashlib.sha256('_'.join(key_parts).encode()).hexdigest()
            
            # Try to get cached result
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for base model query: {cache_key}")
                return cached_result
            
            # If no cache found, calculate result
            logger.debug(f"Cache miss for base model query: {cache_key}")
            result = func(domain)
            
            # Store result in cache
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached base model query result for key: {cache_key}")
            return result
        return wrapper
    return decorator


def invalidate_domain_cache(domain: str = "vision") -> int:
    """
    Invalidates all caches for a specific domain by incrementing the version number.
    This is more efficient than deleting individual cache keys.
    """
    from django.core.cache import caches, cache
    
    cache_version_key = f'cache_version_{domain}'
    
    # Try to use Redis cache if available, otherwise fall back to default cache
    try:
        redis_cache = caches['redis']
        current_version = redis_cache.get(cache_version_key, 1)
        new_version = current_version + 1
        redis_cache.set(cache_version_key, new_version)
    except Exception:
        # Redis cache not available, use default cache
        current_version = cache.get(cache_version_key, 1)
        new_version = current_version + 1
        cache.set(cache_version_key, new_version)
    
    logger.info(f"Invalidated cache for domain '{domain}' (new version: {new_version})")
    return new_version


@csrf_exempt
@require_http_methods(["GET", "POST"])
def refresh_cache(request: HttpRequest, domain: str = "vision") -> JsonResponse:
    """
    Endpoint to manually trigger cache refresh for leaderboard data.
    Can be called via Jenkins job with proper authentication token or URL visit
    
    Usage:
    - POST /benchmarks/refresh_cache/vision/?token=your_secret_token
    - GET /benchmarks/refresh_cache/vision/?token=your_secret_token&rebuild=true

    Request Args:
        domain: The domain to refresh cache for (e.g., "vision", "language")
        token: Token to authenticate request
        rebuild: Boolean whether to rebuild the cache immediately
    """
    # Extract hostname from request without port
    hostname = request.get_host().split(':')[0]

    # For debugging - show token info
    if settings.DEBUG and request.GET.get('show_token') == 'true' and hostname in ['localhost', '127.0.0.1']:
        return JsonResponse({
            "token": settings.CACHE_REFRESH_TOKEN,
            "note": "Use this token in the 'token' parameter to refresh the cache"
        })
    
    # Check for valid token
    token = request.GET.get('token') # Get token from URL
    if token != settings.CACHE_REFRESH_TOKEN: # Check if token provided matches token in settings
        logger.warning(f"Invalid token attempt for cache refresh: {domain}")
        return JsonResponse({
            "status": "error", 
            "message": "Invalid authentication token"
        }, status=403)
    
    # Invalidate cache by incrementing version
    new_version = invalidate_domain_cache(domain)
    
    # Always rebuild the cache immediately when invalidation is triggered
    # This ensures users never experience slow cache misses
    rebuild = True  # Force rebuild since invalidation is event-driven
    
    # Rebuild the leaderboard cache immediately
    if rebuild:
        # Import here to avoid circular imports
        from benchmarks.views.leaderboard import get_ag_grid_context
        
        # Force regeneration of main caches
        logger.info(f"Rebuilding cache for domain '{domain}'")
        public_context = get_ag_grid_context(domain=domain, show_public=True) # @cache_get_context decorator saves public context to cache
        logger.info(f"Cache rebuild completed for domain '{domain}'")
    
    return JsonResponse({
        "status": "success", 
        "message": f"Cache for {domain} domain has been invalidated (new version: {new_version})" + 
                 (" and rebuilt" if rebuild else "")
    })


def trigger_recache(domain: str = "vision", rebuild: bool = True, base_url: str = "http://localhost:8000") -> dict:
    """
    Trigger cache refresh via code. Not used in production.
    
    Args:
        domain: The domain to refresh cache for (e.g., "vision", "language")
        rebuild: Whether to rebuild the cache immediately
        base_url: Base URL of the application
        
    Returns:
        Dict: The response JSON
    """    
    token = settings.CACHE_REFRESH_TOKEN
    url = f"{base_url}/refresh_cache/{domain}/"
    params = {"token": token, "rebuild": str(rebuild).lower()}
    
    try:
        response = requests.post(url, params=params)
        return response.json()
    except Exception as e:
        logger.error(f"Error triggering cache refresh: {str(e)}")
        return {"status": "error", "message": str(e)} 
    
@require_http_methods(["GET"])
def show_token(request: HttpRequest) -> JsonResponse:
    """
    Debug view to show the current token and optionally test Redis.
    Available in DEBUG mode on localhost, or on staging with proper authentication.
    """
    hostname = request.get_host().split(':')[0]

    # Allow on localhost in DEBUG mode, or on staging with token authentication
    is_localhost = hostname in ['localhost', '127.0.0.1'] and settings.DEBUG
    is_staging_with_token = 'staging' in hostname.lower() and request.GET.get('token') == settings.CACHE_REFRESH_TOKEN
    
    if not (is_localhost or is_staging_with_token):
        return JsonResponse({"error": "Only available in DEBUG mode on localhost, or on staging with valid token"}, status=403)

    response_data = {
        "environment": "localhost" if is_localhost else "staging",
        "token": settings.CACHE_REFRESH_TOKEN if is_localhost else "***hidden***"
    }
    
    # Test Redis if requested
    if request.GET.get('test_redis') == 'true':
        try:
            from django.core.cache import caches
            import time
            
            redis_cache = caches['redis']
            
            # Test SET
            start = time.time()
            redis_cache.set('debug_test_key', 'debug_test_value', 30)
            set_time = time.time() - start
            
            # Test GET
            start = time.time()
            result = redis_cache.get('debug_test_key')
            get_time = time.time() - start
            
            response_data.update({
                "redis_status": "success" if result == 'debug_test_value' else "failed",
                "redis_set_time": f"{set_time:.3f}s",
                "redis_get_time": f"{get_time:.3f}s",
                "redis_result": result,
                "redis_backend": str(redis_cache.__class__)
            })
        except Exception as e:
            response_data.update({
                "redis_status": "error",
                "redis_error": str(e)
            })

    return JsonResponse(response_data)


