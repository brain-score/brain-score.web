from typing import Callable, Optional, Dict, Any, List, Union
from django.contrib.auth.models import User
import hashlib
import logging
import requests
from functools import wraps
from django.core.cache import caches, cache as default_cache
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpRequest
import time
logger = logging.getLogger(__name__)

# Cache utility functions and decorators
def cache_get_context(timeout=24 * 60 * 60, key_prefix: Optional[str] = None) -> Callable:  # 24 hour cache by default
    """
    Decorator that caches get_context-like functions in Redis under a versioned key prefix.
    Any time invalidate_domain_cache() is called, the version bumps, and old keys get deleted.

    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
        key_prefix (Optional[str]): Additional prefix to namespace cache keys for different pages/views.
                                   Useful when multiple pages in the same domain need separate caches.
                                   Example: "leaderboard", "models", "compare"
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
            # Try to use Redis cache if available, otherwise fall back to default cache
            try:
                cache_backend = caches["redis"]
                logger.error(f"✅ Redis/Valkey cache available for domain {domain}")
            except Exception as e:
                cache_backend = default_cache
                logger.error(f"❌ Redis/Valkey cache not available for domain {domain}, using LocMemCache: {e}")

            # Grab or initialize version
            version_key = f"cache_version_{domain}"
            cache_version = cache_backend.get(version_key, 1)
            
            # Generate key prefix - include custom key_prefix if provided
            base_parts = []
            if key_prefix:
                base_parts.append(key_prefix)
            
            # Use global public cache when show_public=True, regardless of user
            if show_public:
                # (CASE 1: Public data) Create unique key for public data cache
                key_parts = base_parts + ['global', domain, 'public', f'v{cache_version}']
            elif user:
                # (CASE 2: User data) Create unique key for user-specific cache
                key_parts = base_parts + ['user', domain, str(user.id), str(show_public), f'v{cache_version}']
            else:
                # (CASE 3: No caching) Neither public nor user-specific
                return func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                          model_filter=model_filter, show_public=show_public)
            
            # Add filters to key prefix
            if benchmark_filter:
                key_parts.append("bench_filtered")
            if model_filter:
                key_parts.append("model_filtered")

            # Generate SHA256 hash for key prefix
            fingerprint = hashlib.sha256('_'.join(key_parts).encode()).hexdigest()
            
            # Include key_prefix in visible cache key structure if provided
            if key_prefix:
                cache_key = f"{domain}:{key_prefix}:v{cache_version}:{fingerprint}"
            else:
                cache_key = f"{domain}:v{cache_version}:{fingerprint}"
            
            # Try to get cached result
            try:
                cached_result = cache_backend.get(cache_key)
                logger.info(f"[CACHE GET] {cache_key}")
                if cached_result is not None:
                    logger.info(f"Cache hit for {cache_key}")
                    return cached_result
            except Exception as e:
                logger.error(f"Cache GET error {cache_backend}: {e}")

            # If no cache found, calculate result
            logger.error(f"Cache miss for key: {cache_key}")
            func_start = time.time()
            result = func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                        model_filter=model_filter, show_public=show_public)
            func_end = time.time()
            logger.error(f"Context execution took {func_end - func_start:.3f}s")
                       
            # Store result in cache
            try:
                cache_backend.set(cache_key, result, timeout)
                logger.debug(f"[CACHE SET] {cache_key}")
            except Exception as e:
                logger.warning(f"Cache SET error ({cache_backend}): {e}")
            return result
        return wrapper
    return decorator

def invalidate_domain_cache(domain: str = "vision", preserve_sessions: bool = True) -> dict:
    """
    Invalidates all cache keys for a specific domain and increments the version from
    Redis if available; otherwise only bump
    """ 
    version_key = f"cache_version_{domain}"
    
    # Try to use Redis cache if available, otherwise fall back to default cache
    try:
        cache_backend = caches["redis"]
        client        = cache_backend.client.get_client(write=True)
    except Exception:
        cache_backend = default_cache
        client        = None
        logger.warning("Redis cache unavailable, version will bump but old keys will not be purged")

    # Always bump the domain version (for cache key versioning)
    current_version = cache_backend.get(version_key, 1)
    new_version = current_version + 1
    cache_backend.set(version_key, new_version)

    # If Redis client is unavailable, return warning but still bump version
    if not client:
        return {
            "status": "warning",
            "message": "Redis client unavailable, version bumped but keys not purged",
            "version": new_version
        }

    cache_patterns = [
        f"*:{domain}:*",           # All keys containing this domain
        f"*cache_page*{domain}*",  # Page caches for this domain
        "*cache_page*",         # Django page caches
        "*compressor*",         # Django compressor caches
        "*django_compressor*",  # Django compressor alternative pattern
        "cache_version_*",      # Cache version keys
        "*leaderboard*",        # Leaderboard-specific caches
        "*index*",              # Index/profile caches
        "*models*",             # Model-related caches
        "*compare*",            # Comparison caches
    ] 

    # Clear cache keys
    deleted_count = 0
    preserved_sessions = 0
    total_keys = len(list(client.scan_iter(match="*", count=1000)))

    for pattern in cache_patterns:
        for key in client.scan_iter(match=pattern, count=100):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)

            # Preserve sessions if requested
            if preserve_sessions and ('session' in key_str.lower() or key_str.startswith('django.contrib.sessions')):
                preserved_sessions += 1
                continue

            try:
                client.delete(key)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Error deleting cache key {key}: {e}")

    logger.info(f"Deleted {deleted_count} cache keys for domain '{domain}'")
    
    return {
        "status": "success",
        "domain": domain,
        "version": new_version,
        "keys_deleted": deleted_count,
        "total_keys": total_keys,
        "preserved_keys": total_keys - deleted_count,
        "preserved_sessions": preserved_sessions if preserve_sessions else None,
        "message": f"Cleared {deleted_count} cache keys" + 
                  (f", preserved {preserved_sessions} sessions" if preserve_sessions and preserved_sessions > 0 else "")
    }



@csrf_exempt
@require_http_methods(["GET", "POST"])
def refresh_cache(request: HttpRequest, domain: str = "vision") -> JsonResponse:
    """
    Endpoint to manually trigger cache refresh for leaderboard data.
    
    Usage:
    - POST /benchmarks/refresh_cache/vision/?token=your_secret_token
    - GET /benchmarks/refresh_cache/vision/?token=your_secret_token&preserve_sessions=false
    """
    # Extract hostname from request without port
    hostname = request.get_host().split(':')[0]

    # For debugging - show token info
    if settings.DEBUG and request.GET.get('show_token') == 'true' and hostname in ['localhost', '127.0.0.1']:
        return JsonResponse({
            "token": settings.CACHE_REFRESH_TOKEN,
            "note": "Use this token in the 'token' parameter to refresh the cache",
            "preserve_sessions": "Add &preserve_sessions=false to allow session deletion (default: true)"
        })
    
    # Check for valid token
    token = request.GET.get('token')
    if token != settings.CACHE_REFRESH_TOKEN:
        logger.warning(f"Invalid token attempt for cache refresh: {domain}")
        return JsonResponse({
            "status": "error", 
            "message": "Invalid authentication token"
        }, status=403)
    
    # Check if preserve_sessions parameter is provided (default to True for safety)
    preserve_sessions = request.GET.get('preserve_sessions', 'true').lower() == 'true'
    
    # Clear cache
    result = invalidate_domain_cache(domain=domain, preserve_sessions=preserve_sessions)
    
    if result["status"] != "success":
        return JsonResponse(result, status=500 if result["status"] == "error" else 200)
    
    # Rebuild the leaderboard cache immediately
    try:
        from benchmarks.views.leaderboard import get_ag_grid_context
        logger.info(f"Rebuilding public leaderboard cache for domain '{domain}' after cache clear")
        public_context = get_ag_grid_context(domain=domain, show_public=True)
        logger.info(f"Cache rebuild completed for domain '{domain}'")
        rebuild_success = True
    except Exception as e:
        logger.error(f"Error rebuilding cache: {e}")
        rebuild_success = False
    
    return JsonResponse({
        "status": "success", 
        "domain": result["domain"],
        "version": result["version"],
        "keys_deleted": result["keys_deleted"],
        "preserved_keys": result["preserved_keys"],
        "preserved_sessions": result.get("preserved_sessions"),
        "rebuilt": rebuild_success,
        "message": f"{result['message']}. " + 
                  ("Rebuilt public leaderboard cache." if rebuild_success else "Cache rebuild failed.")
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
        "token": settings.CACHE_REFRESH_TOKEN if is_localhost else "***hidden token***"
    }
    
    # Test Redis if requested
    if request.GET.get('test_redis') == 'true':
        try:
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


