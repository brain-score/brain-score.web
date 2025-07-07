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
import gzip
import pickle
import sys

logger = logging.getLogger(__name__)

# Cache utility functions and decorators
def compress_large_context(context, size_threshold_mb=50):
    """
    Compress large context data to reduce memory usage.
    
    Args:
        context: Dictionary containing context data
        size_threshold_mb: Compress if estimated size exceeds this threshold
    
    Returns:
        Tuple of (compressed_context, compression_info)
    """
    # Estimate size
    estimated_size = sys.getsizeof(str(context)) / (1024 * 1024)
    
    if estimated_size < size_threshold_mb:
        return context, {'compressed': False, 'original_size_mb': estimated_size}
    
    compressed_context = {}
    compression_info = {'compressed': True, 'original_size_mb': estimated_size, 'compressed_fields': []}
    
    # Compress large JSON fields
    large_json_fields = ['row_data', 'column_defs', 'benchmark_groups', 'benchmark_tree']
    
    for key, value in context.items():
        if key in large_json_fields and isinstance(value, str):
            try:
                # Compress the JSON string
                compressed_bytes = gzip.compress(value.encode('utf-8'))
                compressed_context[f'{key}_compressed'] = compressed_bytes
                compressed_context[f'{key}_original_size'] = len(value.encode('utf-8'))
                compression_info['compressed_fields'].append(key)
                logger.debug(f"Compressed {key}: {len(value.encode('utf-8'))} -> {len(compressed_bytes)} bytes")
            except Exception as e:
                logger.warning(f"Failed to compress {key}: {e}")
                compressed_context[key] = value
        else:
            compressed_context[key] = value
    
    compressed_size = sys.getsizeof(str(compressed_context)) / (1024 * 1024)
    compression_info['compressed_size_mb'] = compressed_size
    compression_info['compression_ratio'] = estimated_size / compressed_size if compressed_size > 0 else 1
    
    logger.info(f"Context compression: {estimated_size:.1f}MB -> {compressed_size:.1f}MB (ratio: {compression_info['compression_ratio']:.1f}x)")
    
    return compressed_context, compression_info


def decompress_context(compressed_context):
    """
    Decompress context data that was compressed by compress_large_context.
    
    Args:
        compressed_context: Dictionary containing compressed context data
        
    Returns:
        Decompressed context dictionary
    """
    if not isinstance(compressed_context, dict):
        return compressed_context
    
    decompressed_context = {}
    
    for key, value in compressed_context.items():
        if key.endswith('_compressed'):
            # This is compressed data - decompress it
            original_key = key.replace('_compressed', '')
            try:
                decompressed_bytes = gzip.decompress(value)
                decompressed_context[original_key] = decompressed_bytes.decode('utf-8')
                logger.debug(f"Decompressed {original_key}")
            except Exception as e:
                logger.warning(f"Failed to decompress {original_key}: {e}")
                decompressed_context[original_key] = str(value)  # Fallback
        elif key.endswith('_original_size'):
            # Skip size metadata
            continue
        else:
            decompressed_context[key] = value
    
    return decompressed_context


def cache_get_context(timeout=24 * 60 * 60, compress_threshold_mb=50) -> Callable:  # 24 hour cache by default
    """
    Decorator that caches results of get_context function for faster loading of leaderboard view and model card view.
    Two-level caching:
        - Global cache for public data
        - User-specific cache for non-public data
    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
        compress_threshold_mb (int): Compress cache if size exceeds this threshold. Defaults to 50MB.
    """
    def decorator(func):  # Take function to be decorated (i.e., get_context)
        @wraps(func)  # Preserving original function's metadata attributes
        def wrapper(
            user: Optional[User] = None,
            domain: str = "vision",
            benchmark_filter: Optional[str] = None,
            model_filter: Optional[str] = None,
            show_public: bool = False,
            **kwargs  # Accept additional keyword arguments
        ) -> Dict[str, Any]:
            """
            Wrapper function that implements the caching logic.
            
            Args:
                user (Optional[User]): The user requesting the context, if any
                domain (str): The domain to get context for (e.g. "vision", "language")
                benchmark_filter (Optional[str]): Filter to apply to benchmarks
                model_filter (Optional[str]): Filter to apply to models
                show_public (bool): Whether to show only public data
                **kwargs: Additional keyword arguments (e.g., page_size)
            
            Returns:
                Dict[str, Any]: The context dictionary containing models, benchmarks, and other data
            """            
            # Get cache version from cache or set to 1 if not exists
            cache_version_key = f'cache_version_{domain}'
            cache_version = cache.get(cache_version_key, 1)
            
            # Include kwargs in cache key generation for pagination support
            kwargs_str = '_'.join(f'{k}_{v}' for k, v in sorted(kwargs.items())) if kwargs else ''
            
            # Generate a more specific cache key that includes model_filter and benchmark_filter info
            if show_public and not user:
                # (CASE 1: Public data) Create unique key for public data cache
                key_parts = ['global_context', domain, 'public', f'v{cache_version}']
                if benchmark_filter:
                    key_parts.append('benchmark_filtered')
                if model_filter:
                    key_parts.append('model_filtered')
                if kwargs_str:
                    key_parts.append(kwargs_str)
            elif user:
                # (CASE 2: User data) Create unique key for user-specific cache that includes public data
                key_parts = ['user_context', domain, str(user.id), str(show_public), f'v{cache_version}']
                if benchmark_filter:
                    key_parts.append('benchmark_filtered')
                if model_filter:
                    key_parts.append('model_filtered')
                if kwargs_str:
                    key_parts.append(kwargs_str)
            else:
                # (CASE 3: No caching) Neither public nor user-specific
                return func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                          model_filter=model_filter, show_public=show_public, **kwargs)
            
            # Generate SHA256 hash
            cache_key = hashlib.sha256('_'.join(key_parts).encode()).hexdigest()
            
            # Try to get cached result
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                # Decompress if needed
                if isinstance(cached_result, dict) and any(k.endswith('_compressed') for k in cached_result.keys()):
                    print(f"CACHE HIT (compressed)")
                    return decompress_context(cached_result)
                print(f"CACHE HIT")
                return cached_result

            # If no cache found, calculate result
            print(f"CACHE MISS", end="")
            result = func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                        model_filter=model_filter, show_public=show_public, **kwargs)
            
            # For user contexts, also cache the public data within the user context
            if user and not show_public:
                result['public_models'] = [m for m in result['models'] if getattr(m, 'public', True)]
            
            # Compress large data before caching
            compressed_result, compression_info = compress_large_context(result, compress_threshold_mb)
            
            # Store result in cache
            cache.set(cache_key, compressed_result, timeout)
            
            # Print compression status on same line as cache miss
            if compression_info['compressed']:
                print(f" (compressed: {compression_info['original_size_mb']:.0f}MB→{compression_info['compressed_size_mb']:.0f}MB)")
            else:
                print()
            
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
    cache_version_key = f'cache_version_{domain}'
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
    cache.clear()
    
    # Optionally rebuild the cache immediately
    rebuild = request.GET.get('rebuild', 'false').lower() == 'true' # Get rebuild parameter from URL
    # If rebuild is true, rebuild the leaderboard cache immediately
    if rebuild:
        # Import here to avoid circular imports
        from benchmarks.views.index import get_context
        
        # Force regeneration of main caches
        logger.info(f"Rebuilding cache for domain '{domain}'")
        public_context = get_context(domain=domain, show_public=True) # @cache_get_context decorator saves public context to cache
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
    Debug view to show the current token.
    Only available in localhost DEBUG mode.
    """
    hostname = request.get_host().split(':')[0]

    if not settings.DEBUG or hostname not in ['localhost', '127.0.0.1']:
        return JsonResponse({"error": "Only available in DEBUG mode on localhost"}, status=403)

    return JsonResponse({
        "token": settings.CACHE_REFRESH_TOKEN
    })


