import hashlib
import logging
from functools import wraps
from django.core.cache import cache
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db.models import Q
from benchmarks.models import FinalBenchmarkContext
logger = logging.getLogger(__name__)

# Cache utility functions and decorators

def cache_get_context(timeout=24 * 60 * 60):  # 24 hour cache by default
    '''
    Decorator that caches results of get_context function for faster loading of leaderboard view and model card view.
    Two-level caching:
        - Global cache for public data
        - User-specific cache for non-public data
    Args:
        timeout (int): Cache timeout in seconds. Defaults to 24 hours.
    '''
    def decorator(func):  # Take function to be decorated (i.e., get_context)
        @wraps(func)  # Preserving original function's metadata attributes
        def wrapper(user=None, domain="vision", benchmark_filter=None, model_filter=None, show_public=False):
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


def cache_base_model_query(timeout=24 * 60 * 60):  # 24 hour cache by default
    def decorator(func):
        @wraps(func)
        def wrapper(domain="vision"):
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


def invalidate_domain_cache(domain="vision"):
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
def refresh_cache(request, domain="vision"):
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
    # For debugging - show token info
    if settings.DEBUG and request.GET.get('show_token') == 'true':
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


# Function for testing trigger via code
def trigger_recache(domain="vision", rebuild=True, base_url="http://localhost:8000"):
    """
    Programmatically trigger cache refresh.
    
    Args:
        domain: The domain to refresh cache for (e.g., "vision", "language")
        rebuild: Whether to rebuild the cache immediately
        base_url: Base URL of the application
        
    Returns:
        Dict: The response JSON
    """
    import requests
    
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
def show_token(request):
    """Debug view to show the current token."""
    if not settings.DEBUG:
        return JsonResponse({"error": "Only available in DEBUG mode"}, status=403)
    
    return JsonResponse({
        "token": settings.CACHE_REFRESH_TOKEN
    })


"""
Leaderboard Views Related Functions
"""

def get_benchmark_exclusion_list(identifiers, domain="vision"):
    """
    Get a list of benchmark identifiers that should be excluded from the leaderboard.
    """
    # Get all benchmark identifiers and sort paths
    benchmark_paths = list(FinalBenchmarkContext.objects.filter(domain=domain, visible=True).values_list('short_name', 'sort_path').distinct())
    
    # Generate exclusion patterns for each identifier
    exclusion_patterns = []

    for identifier, sort_path in benchmark_paths:
        if identifier in identifiers:
            exclusion_patterns.append({
                'type': 'contains',
                'field': 'sort_path',
                'value': sort_path
            })
            
    return exclusion_patterns

def apply_exclusion_patterns(queryset, patterns, field_mapping=None):
    """
    Apply exclusion patterns to any queryset.
    
    Args:
        queryset: Any Django queryset
        patterns: List of pattern dictionaries from get_benchmark_exclusion_patterns()
        field_mapping: Optional dictionary mapping standard field names to model-specific ones
                      e.g., {'sort_path': 'benchmark_sort_path'} for FlattenedModelContext
        
    Returns:
        Filtered queryset with exclusions applied
    """

    if not patterns:
        return queryset

    # Use default field mapping if none provided
    if field_mapping is None:
        field_mapping = {}
    
    # Build exclusion conditions
    for pattern in patterns:
        # Get the field name for this model (or use default)
        field = field_mapping.get(pattern['field'], pattern['field'])

        # Build the query condition based on pattern type
        if pattern['type'] == 'exact':
            kwargs = {field: pattern['value']}
            exclusion_conditions |= Q(**kwargs)
        elif pattern['type'] == 'contains':
            kwargs = {f"{field}__contains": pattern['value']}
            exclusion_conditions |= Q(**kwargs)
    
    # Apply exclusions
    return queryset.exclude(exclusion_conditions)
