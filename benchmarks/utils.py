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
from django.views.decorators.cache import cache_page
from django.http import JsonResponse, HttpRequest
import boto3
import time
import pickle
import gzip
import os

logger = logging.getLogger(__name__)


def cache_page_for_public_only(timeout: int):
    """
    Cache decorator that only caches public leaderboard requests.
    Profile views (user_view=true) bypass the cache entirely.

    Args:
        timeout: Cache timeout in seconds
    """
    def decorator(view_func):
        # Pre-create the cached version
        cached_view = cache_page(timeout)(view_func)

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Check if this is a user-specific view
            user_view = request.GET.get('user_view', 'false').lower() == 'true'

            if user_view and request.user.is_authenticated:
                # Profile view - skip page cache, call view directly
                response = view_func(request, *args, **kwargs)
                response['Cache-Control'] = 'private, no-store'
                return response
            else:
                # Public view - use cached version
                return cached_view(request, *args, **kwargs)

        return wrapper
    return decorator

# Compression utilities for cache
def compress_data(data: Any) -> bytes:
    """Compress data using pickle + gzip for cache storage"""
    pickled_data = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    return gzip.compress(pickled_data, compresslevel=6)

def decompress_data(compressed_data: bytes) -> Any:
    """Decompress cached data"""
    pickled_data = gzip.decompress(compressed_data)
    return pickle.loads(pickled_data)

def estimate_size(obj: Any) -> int:
    """Estimate object size in bytes for logging"""
    try:
        return len(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:
        return 0

# Cache utility functions and decorators
def cache_get_context(timeout=24 * 60 * 60, key_prefix: Optional[str] = None, use_compression: bool = False) -> Callable:
    """
    Decorator that caches get_context-like functions in Redis under a versioned key prefix.
    
    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
        key_prefix (Optional[str]): Additional prefix to namespace cache keys for different pages/views.
        use_compression (bool): Whether to compress cached data. Defaults to False for backward compatibility.
    """
    def decorator(func):  # Take function to be decorated (i.e., get_context)
        @wraps(func)  # Preserving original function's metadata attributes
        def wrapper(
            user: Optional[User] = None,
            domain: str = "vision",
            benchmark_filter: Optional[str] = None,
            model_filter: Optional[str] = None,
            show_public: bool = False,
            force_user_cache: bool = False,
            **kwargs  # Accept any additional parameters
        ) -> Dict[str, Any]:
            """
            Wrapper function that implements the caching logic.
            
            Args:
                user (Optional[User]): The user requesting the context, if any
                domain (str): The domain to get context for (e.g. "vision", "language")
                benchmark_filter (Optional[str]): Filter to apply to benchmarks
                model_filter (Optional[str]): Filter to apply to models
                show_public (bool): Whether to show only public data
                force_user_cache (bool): Force user-specific caching even when show_public=True
            
            Returns:
                Dict[str, Any]: The context dictionary containing models, benchmarks, and other data
            """
            # Try to use Redis cache if available, otherwise fall back to default cache
            try:
                cache_backend = caches["redis"]
                if os.getenv("DJANGO_ENV") != "test":
                    logger.error(f"✅ Redis/Valkey cache available for domain {domain}")
            except Exception as e:
                cache_backend = default_cache
                if os.getenv("DJANGO_ENV") != "test":
                    logger.error(f"❌ Redis/Valkey cache not available for domain {domain}, using LocMemCache: {e}")

            # Grab or initialize version
            version_key = f"cache_version_{domain}"
            cache_version = cache_backend.get(version_key, 1)
            
            # Generate key prefix - include custom key_prefix if provided
            base_parts = []
            if key_prefix:
                base_parts.append(key_prefix)
            
            # Determine caching strategy based on user context and force_user_cache
            if show_public and not force_user_cache and not user:
                # (CASE 1: Global public data) Use global cache for anonymous public views
                key_parts = base_parts + ['global', domain, 'public', f'v{cache_version}']
            elif user:
                # (CASE 2: User-specific data) Always use user-specific cache when user is present
                # This includes both user-only views and user+public views (profile toggle)
                cache_type = 'forced' if force_user_cache else 'normal'
                key_parts = base_parts + ['user', domain, str(user.id), str(show_public), cache_type, f'v{cache_version}']
            else:
                # (CASE 3: No caching) Neither public nor user-specific
                return func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                          model_filter=model_filter, show_public=show_public, force_user_cache=force_user_cache, **kwargs)
            
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
            
            # Add compression suffix to cache key if using compression
            if use_compression:
                cache_key += ":gzip"
            
            # Try to get cached result
            try:
                cached_result = cache_backend.get(cache_key)
                logger.info(f"[CACHE GET] {cache_key}")
                if cached_result is not None:
                    logger.info(f"Cache hit for {cache_key}")
                    
                    # Decompress if needed
                    if use_compression and isinstance(cached_result, bytes):
                        try:
                            decompressed_result = decompress_data(cached_result)
                            logger.info(f"Decompressed cache data for {cache_key}")
                            return decompressed_result
                        except Exception as e:
                            logger.warning(f"Failed to decompress cache data: {e}, falling back to function call")
                            # Fall through to recalculate
                    else:
                        return cached_result
            except Exception as e:
                logger.error(f"Cache GET error {cache_backend}: {e}")

            # If no cache found, calculate result
            logger.error(f"Cache miss for key: {cache_key}")
            func_start = time.time()
            result = func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                        model_filter=model_filter, show_public=show_public, force_user_cache=force_user_cache, **kwargs)
            func_end = time.time()
            logger.error(f"Context execution took {func_end - func_start:.3f}s")
            
            
            # Estimate and log the original size if compression is enabled
            if use_compression:
                original_size = estimate_size(result)
                      
            # Store result in cache
            try:
                if use_compression:
                    # Compress the data before storing
                    compress_start = time.time()
                    compressed_result = compress_data(result)
                    compress_end = time.time()
                    
                    compressed_size = len(compressed_result)
                    original_size = estimate_size(result)
                    compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
                    
                    logger.debug(f"COMPRESSION DEBUG: {original_size / (1024 * 1024):.2f} MB → {compressed_size / (1024 * 1024):.2f} MB "
                              f"(ratio: {compression_ratio:.2f}, time: {compress_end - compress_start:.3f}s)")
                    
                    cache_backend.set(cache_key, compressed_result, timeout)
                else:
                    logger.debug(f"COMPRESSION DEBUG: No compression, storing raw result")
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
        "*cache_header*",       # Django cache_page header entries (companion to cache_page body)
        "*compressor*",         # Django compressor caches
        "*django_compressor*",  # Django compressor alternative pattern
        "*cache_version*",      # Cache version keys (prefixed by django-redis KEY_PREFIX)
        "*leaderboard*",        # Leaderboard-specific caches
        "*index*",              # Index/profile caches
        "*models*",             # Model-related caches
        "*compare*",            # Comparison caches
        f"*:user:{domain}:*",      # User-specific caches for this domain
        f"*user_*:{domain}:*",     # Alternative user cache format
        f"*:{domain}:*:user_*",    # User caches with domain prefix
    ] 

    # Clear cache keys and track preserved ones
    deleted_count = 0
    preserved_sessions = 0
    preserved_keys = []
    total_keys = len(list(client.scan_iter(match="*", count=1000)))

    # First, collect all keys that match our patterns
    matching_keys = set()
    for pattern in cache_patterns:
        for key in client.scan_iter(match=pattern, count=100):
            key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
            matching_keys.add(key_str)

    # Process each matching key
    for key_str in matching_keys:
        # Preserve sessions if requested
        if preserve_sessions and ('session' in key_str.lower() or key_str.startswith('django.contrib.sessions')):
            preserved_sessions += 1
            # Add preserved key
            preserved_keys.append(f"SESSION: {key_str}")
            continue

        try:
            # Delete key that is not supposed to be preserved
            client.delete(key_str)
            deleted_count += 1
        except Exception as e:
            logger.warning(f"Error deleting cache key {key_str}: {e}")
            preserved_keys.append(f"ERROR: {key_str}")

    # Find keys that weren't matched by any pattern (these are the "other" preserved keys)
    # We now record this so we can explore any stray keys that are not being cleared.
    all_keys = set()
    for key in client.scan_iter(match="*", count=1000):
        key_str = key.decode('utf-8') if isinstance(key, bytes) else str(key)
        all_keys.add(key_str)
    
    unmatched_keys = all_keys - matching_keys
    for key_str in unmatched_keys:
        if not ('session' in key_str.lower() or key_str.startswith('django.contrib.sessions')):
            preserved_keys.append(f"UNMATCHED: {key_str}")

    logger.info(f"Deleted {deleted_count} cache keys for domain '{domain}' (including user-specific caches)")
    if preserved_keys:
        logger.info(f"Preserved keys: {preserved_keys[:10]}")  # Log first 10
    
    return {
        "status": "success",
        "domain": domain,
        "version": new_version,
        "keys_deleted": deleted_count,
        "total_keys": total_keys,
        "preserved_keys": total_keys - deleted_count,
        "preserved_sessions": preserved_sessions if preserve_sessions else None,
        "preserved_key_samples": preserved_keys[:10],  # Return first 10 preserved keys
        "message": f"Cleared {deleted_count} cache keys including user-specific caches" + 
                  (f", preserved {preserved_sessions} sessions" if preserve_sessions and preserved_sessions > 0 else "")
    }


def invalidate_cloudfront_cache(distribution_id: str, domain: str) -> bool:
    """
    Create a CloudFront invalidation for leaderboard paths.
    Only runs when CLOUDFRONT_DISTRIBUTION_ID is set (staging/production with CDN).
    Returns True on success, False on failure.
    """
    try:
        cf_client = boto3.client('cloudfront', region_name='us-east-1')
        cf_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': 2,
                    'Items': [
                        f'/{domain}/leaderboard/*',
                        f'/static/*',
                    ]
                },
                'CallerReference': f'{domain}-{int(time.time())}'
            }
        )
        logger.info(f"CloudFront invalidation created for /{domain}/leaderboard/*")
        return True
    except Exception as e:
        logger.error(f"CloudFront invalidation failed: {e}")
        return False


@csrf_exempt
@require_http_methods(["GET", "POST"])
def refresh_cache(request: HttpRequest, domain: str = "vision") -> JsonResponse:
    """
    Endpoint to manually trigger cache refresh for leaderboard data.
    Can be called via Jenkins job with proper authentication token or URL visit

    
    Usage:
    - POST /benchmarks/refresh_cache/vision/?token=your_secret_token
    - GET /benchmarks/refresh_cache/vision/?token=your_secret_token&preserve_sessions=false

    Request Args:
        domain: The domain to refresh cache for (e.g., "vision", "language")
        token: Token to authenticate request
        preserve_sessions: oolean whether to preserve sessions (default: true)
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
    
    # Clear cache (now includes user-specific caches by default)
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

    # Invalidate CloudFront edge cache if distribution is configured
    cf_invalidated = False
    if settings.CLOUDFRONT_DISTRIBUTION_ID:
        cf_invalidated = invalidate_cloudfront_cache(
            settings.CLOUDFRONT_DISTRIBUTION_ID, domain
        )

    return JsonResponse({
        "status": "success",
        "domain": result["domain"],
        "version": result["version"],
        "keys_deleted": result["keys_deleted"],
        "total_keys": result["total_keys"],
        "preserved_keys": result["preserved_keys"],
        "preserved_sessions": result.get("preserved_sessions"),
        "preserved_key_samples": result["preserved_key_samples"],
        "rebuilt": rebuild_success,
        "cloudfront_invalidated": cf_invalidated,
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
    
    # Use /debug/show_token/?test_redis=true to test Redis
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


