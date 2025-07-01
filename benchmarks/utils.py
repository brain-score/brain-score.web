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
            cache_version = cache.get(cache_version_key, 1) # Get cache version from cache or set to 1 if not exists
            
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
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result

            # If no cache found, calculate result
            logger.debug(f"Cache miss for key: {cache_key}")
            result = func(user=user, domain=domain, benchmark_filter=benchmark_filter, 
                        model_filter=model_filter, show_public=show_public)
            
            # For user contexts, also cache the public data within the user context
            if user and not show_public:
                result['public_models'] = [m for m in result['models'] if getattr(m, 'public', True)]
            
            # Store result in cache
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for key: {cache_key}")
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
        from benchmarks.views.leaderboard import ag_grid_leaderboard
        from django.test import RequestFactory
        
        # Force regeneration of main caches
        logger.info(f"Rebuilding cache for domain '{domain}'")
        public_context = get_context(domain=domain, show_public=True) # @cache_get_context decorator saves public context to cache
        
        # Also rebuild AG Grid leaderboard cache
        logger.info(f"Rebuilding AG Grid leaderboard cache for domain '{domain}'")
        factory = RequestFactory()
        fake_request = factory.get(f'/benchmarks/leaderboard/{domain}/')
        fake_request.user = None  # Anonymous user for public cache
        ag_grid_leaderboard(fake_request, domain)  # This will populate the cache
        
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


def cache_ag_grid_leaderboard(timeout=24 * 60 * 60) -> Callable:  # 24 hour cache by default
    """
    Decorator that caches results of ag_grid_leaderboard function for faster loading.
    Handles Django request objects and caches the complete processed context.
    
    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request: HttpRequest, domain: str):
            """
            Wrapper function that implements the caching logic for AG Grid leaderboard.
            
            Args:
                request (HttpRequest): Django request object
                domain (str): The domain to get leaderboard for (e.g. "vision", "language")
            
            Returns:
                HttpResponse: Rendered template response
            """
            # Extract user from request
            user = request.user if request.user.is_authenticated else None
            
            # Get cache version from cache or set to 1 if not exists
            cache_version_key = f'cache_version_{domain}'
            cache_version = cache.get(cache_version_key, 1)
            
            # Generate cache key based on user authentication and domain
            if not user:
                # Public data cache
                key_parts = ['ag_grid_leaderboard', domain, 'public', f'v{cache_version}']
            else:
                # User-specific cache (though AG Grid leaderboard shows public data for all users)
                key_parts = ['ag_grid_leaderboard', domain, str(user.id), f'v{cache_version}']
            
            # Generate SHA256 hash for cache key
            cache_key = hashlib.sha256('_'.join(key_parts).encode()).hexdigest()
            
            # Try to get cached result
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"AG Grid leaderboard cache hit for key: {cache_key}")
                return cached_result
            
            # If no cache found, calculate result
            logger.debug(f"AG Grid leaderboard cache miss for key: {cache_key}")
            result = func(request, domain)
            
            # Store result in cache
            cache.set(cache_key, result, timeout)
            logger.debug(f"Cached AG Grid leaderboard result for key: {cache_key}")
            return result
        
        return wrapper
    return decorator
