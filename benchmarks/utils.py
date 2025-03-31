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
from tqdm import tqdm
import json
import numpy as np
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
    
    # Initialize exclusion_conditions as an empty Q object
    exclusion_conditions = Q()

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
"""
domain = "vision"
benchmark_filter = lambda benchmarks: apply_exclusion_patterns(benchmarks, get_benchmark_exclusion_list(['V1', 'IT'], domain=domain))
benchmarks = list(benchmark_filter(FinalBenchmarkContext.objects.filter(domain=domain)).order_by('overall_order'))
"""
def rebuild_model_tree(model_benchmark_pairs):
    """
    Rebuild the model structure from flattened model-benchmark pairs,
    returning a list of dictionaries that match the FinalModelContext schema.
    
    Args:
        model_benchmark_pairs: List of FlattenedModelContext objects
        
    Returns:
        List of restructured model dictionaries.
    """
    models_dict = {}
    all_benchmark_ids = set()

    # Count unique models (by model_id) for progress display
    unique_models = set(item.model_id for item in model_benchmark_pairs)
    total_models = len(unique_models)

    # Process each pair and group by model_id
    for item in tqdm(model_benchmark_pairs, desc=f"Rebuilding {total_models} models", unit="pairs"):
        model_id = item.model_id

        if model_id not in models_dict:
            models_dict[model_id] = {
                "id": model_id,
                "model_id": model_id,  # integer
                "name": item.model_name,
                "reference_identifier": item.model_reference_identifier,
                "url": item.model_url,
                # For JSONB fields, keep them as dictionaries (or None if not provided)
                "user": item.submitter_info if isinstance(item.submitter_info, dict) else None,
                "user_id": item.submitter_info.get('id') if isinstance(item.submitter_info, dict) and 'id' in item.submitter_info else None,
                "owner": item.model_owner_info if isinstance(item.model_owner_info, dict) else None,
                "public": bool(item.model_public),
                "competition": item.competition if item.competition else None,
                "domain": item.model_domain,
                # Ensure visual_degrees is an integer or None
                "visual_degrees": int(item.visual_degrees) if item.visual_degrees is not None else None,
                "layers": item.layers if item.layers else None,
                # Overall rank is stored as an integer
                "rank": int(item.overall_rank) if item.overall_rank is not None else 0,
                # This will be populated below
                "scores": None,
                "build_status": item.build_status if item.build_status else "",
                "submitter": item.submitter_info if isinstance(item.submitter_info, dict) else None,
                "submission_id": item.submission_id if item.submission_id is not None else None,
                "jenkins_id": item.jenkins_id if item.jenkins_id is not None else None,
                "timestamp": item.submission_timestamp,  # assuming this is already a datetime object
                "primary_model_id": None,  # To be set later if needed
                "num_secondary_models": 0,
                "model_meta": item.model_meta if item.model_meta else None,
                # Temporary dictionary to accumulate scores by benchmark identifier
                "scores_temp": {}
            }

        # Add the score for this benchmark if available
        if item.benchmark_identifier:
            all_benchmark_ids.add(item.benchmark_identifier)
            
            benchmark = {
                "url": getattr(item, 'benchmark_url', None),
                "meta": getattr(item, 'benchmark_meta', None),
                "year": getattr(item, 'benchmark_year', None),
                "depth": item.depth,
                "author": getattr(item, 'benchmark_author', None),
                "bibtex": getattr(item, 'benchmark_bibtex', None),
                "parent": item.benchmark_parent,
                "ceiling": getattr(item, 'benchmark_ceiling', "X"),
                "meta_id": getattr(item, 'benchmark_meta_id', None),
                "version": item.benchmark_version,
                "children": getattr(item, 'benchmark_children', None),
                "identifier": item.benchmark_identifier,
                "short_name": item.benchmark_short_name,
                "root_parent": getattr(item, 'benchmark_root_parent', "average_vision"),
                "ceiling_error": getattr(item, 'benchmark_ceiling_error', None),
                "overall_order": getattr(item, 'benchmark_overall_order', item.depth),
                "benchmark_type_id": item.benchmark_type_id,
                "reference_identifier": getattr(item, 'benchmark_reference_identifier', None),
                "number_of_all_children": getattr(item, 'benchmark_number_of_all_children', 0)
            }
            
            score = {
                "best": item.best_score,
                "rank": item.benchmark_rank,
                "color": item.color,
                "error": item.error,
                "median": getattr(item, 'median_score', None),
                "comment": getattr(item, 'comment', None),
                "benchmark": benchmark,
                "score_raw": item.score_raw,
                # Use score_ceiled_label if available; otherwise, compute a fallback
                "score_ceiled": item.score_ceiled_label if hasattr(item, 'score_ceiled_label') else (
                    f".{int(item.score_ceiled_raw * 1000)}" if item.score_ceiled_raw is not None else ""
                ),
                "visual_degrees": item.visual_degrees,
                "score_ceiled_raw": item.score_ceiled_raw,
                "versioned_benchmark_identifier": f"{item.benchmark_identifier}",
                "is_complete": 1 if item.is_complete == 'True' else 0,
            }
            
            models_dict[model_id]["scores_temp"][item.benchmark_identifier] = score

    # Determine canonical benchmark order from the FinalBenchmarkContext model
    canonical_benchmarks = FinalBenchmarkContext.objects.filter(
        identifier__in=list(all_benchmark_ids)
    ).order_by('overall_order')
    canonical_order = [b.identifier for b in canonical_benchmarks]

    # Convert temporary scores dictionary into an ordered list for each model
    for model_id, model_data in models_dict.items():
        scores_list = []
        # First add scores following the canonical order
        for bench_id in canonical_order:
            if bench_id in model_data["scores_temp"]:
                scores_list.append(model_data["scores_temp"][bench_id])
        # Then add any scores not in the canonical order
        for bench_id, score in model_data["scores_temp"].items():
            if bench_id not in canonical_order:
                scores_list.append(score)
        model_data["scores"] = scores_list
        del model_data["scores_temp"]

    models = list(models_dict.values())
    return models


def recompute_upstream_scores(model_benchmark_pairs):
    """
    Recomputes upstream (parent) benchmark scores after filtering.
    Works with flattened model-benchmark pairs and maintains score computation rules.
    Only updates score values in existing objects, preserving all other data.
    """
    pairs = list(model_benchmark_pairs)
    if not pairs:
        return pairs
        
    from itertools import groupby
    from operator import attrgetter
    
    # Sort by model_id and sort_path
    pairs.sort(key=lambda x: (x.model_id, x.sort_path))
    
    # Get unique model IDs for progress tracking
    unique_models = list({pair.model_id for pair in pairs})
    
    for model_id in tqdm(unique_models, desc="Recomputing scores", unit="model"):
        model_pairs = [p for p in pairs if p.model_id == model_id]
        
        # Create a mapping of sort_paths to their objects
        path_to_score = {pair.sort_path: pair for pair in model_pairs}
        
        # Group paths by their level (number of segments)
        paths_by_level = {}
        for path in path_to_score.keys():
            level = path.count('-')
            if level not in paths_by_level:
                paths_by_level[level] = []
            paths_by_level[level].append(path)
        
        # Process from deepest level up
        for level in sorted(paths_by_level.keys(), reverse=True):
            if level == 0:  # Skip root level
                continue
            
            # Process each path at this level
            for path in paths_by_level[level]:
                # Get parent path by removing last segment
                parent_path = '-'.join(path.split('-')[:-2])
                if not parent_path or parent_path not in path_to_score:
                    continue
                
                # Find all siblings (direct children of the parent)
                siblings = []
                parent_prefix = parent_path + '-'
                for sibling_path in paths_by_level[level]:
                    if sibling_path.startswith(parent_prefix):
                        siblings.append(path_to_score[sibling_path])
                
                if not siblings:
                    continue
                
                # Get parent benchmark object
                parent = path_to_score[parent_path]
                
                # Extract scores from siblings and convert to floats
                sibling_scores = []
                for s in siblings:
                    try:
                        if s.score_ceiled_raw and isinstance(s.score_ceiled_raw, str):
                            # Convert string score to float, removing leading '.' if present
                            score_str = s.score_ceiled_raw.lstrip('.')
                            score = float(score_str)
                            sibling_scores.append(score)
                        elif isinstance(s.score_ceiled_raw, (int, float)):
                            sibling_scores.append(float(s.score_ceiled_raw))
                        else:
                            sibling_scores.append(None)
                    except (ValueError, TypeError):
                        sibling_scores.append(None)
                
                # Apply score computation rules
                if all(score is None for score in sibling_scores):
                    new_score = None
                elif any(isinstance(score, float) and np.isnan(score) for score in sibling_scores) and \
                     all(score is None or (isinstance(score, float) and np.isnan(score)) for score in sibling_scores):
                    new_score = float('nan')
                else:
                    # Get valid scores (not None and not NaN)
                    valid_scores = [
                        score for score in sibling_scores 
                        if score is not None 
                        and isinstance(score, float) 
                        and not np.isnan(score)
                    ]
                    if valid_scores:
                        new_score = sum(valid_scores) / len(siblings)
                    else:
                        new_score = None
                
                # Update score fields in parent
                parent.score_ceiled_raw = new_score
                score_str = (
                    "" if new_score is None
                    else "NaN" if isinstance(new_score, float) and np.isnan(new_score)
                    else f".{int(new_score * 1000)}"
                )
                parent.score_ceiled = score_str
                parent.score_ceiled_label = score_str
    
    return pairs


def print_structure(data, indent=0):
    spacing = ' ' * indent
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{spacing}{key}: {type(value).__name__}")
            # If the value is a dictionary, recurse into it
            if isinstance(value, dict):
                print_structure(value, indent + 2)
            # If the value is a list, check its contents
            elif isinstance(value, list):
                if value:  # if list is not empty
                    # Check the type of the first element
                    first_type = type(value[0]).__name__
                    print(f"{spacing}  [List of {first_type}]")
                    # If the first element is a dictionary, you can optionally inspect each one
                    if isinstance(value[0], dict):
                        for i, item in enumerate(value):
                            print(f"{spacing}    - Element {i}:")
                            print_structure(item, indent + 6)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            print(f"{spacing}Element {i}:")
            print_structure(item, indent + 2)
    else:
        print(f"{spacing}{data} ({type(data).__name__})")

