import logging
import threading
import numpy as np
from django.http import Http404
from django.shortcuts import render
from django.template.defaulttags import register

from .index import get_context, display_model, display_submitter, get_visibility
from .leaderboard import get_ag_grid_context
from ..models import FinalModelContext
from time import time
_logger = logging.getLogger(__name__)

# Thread-local storage for benchmark lookup (used by template filters)
_thread_locals = threading.local()

def view(request, id: int, domain: str):
    start_time = time()
    # Check if user is logged in
    user = request.user if request.user.is_authenticated else None
    
    # Try to get model object
    try:
        model_obj = FinalModelContext.objects.get(model_id=id, domain=domain)
        
        # Check if user has permission to view this model
        if not model_obj.public:
            if not user:
                # Anonymous users can see private models with redacted info
                pass
            elif not user.is_superuser:
                # Regular users can see private models if they own them
                model_owner_id = model_obj.user.get('id') if isinstance(model_obj.user, dict) else getattr(model_obj.user, 'id', None)
                if model_owner_id != user.id:
                    # User is not the owner, but can still see with redacted info
                    pass

        # Get context for model cards - always use global public context for consistent ranking
        context = get_context(user=None, domain=domain, show_public=True)
        
        # The public models are now cached within the user context
        public_models = context.get('public_models', context['models']) if user else context['models']
        
        # Determine if submission details should be visible (in most/possible all cases, owner == submitter, and therefore, this can be condensed)
        is_owner = False
        if user and model_obj.user:
            if isinstance(model_obj.user, dict):
                is_owner = user.id == model_obj.user.get('id')
            else:
                is_owner = user.id == model_obj.user.id
        
        is_submitter = False
        if user and model_obj.submitter:
            if isinstance(model_obj.submitter, dict):
                is_submitter = user.id == model_obj.submitter.get('id')
            else:
                is_submitter = user.id == model_obj.submitter.id
        
        submission_details_visible = user and (user.is_superuser or is_owner or is_submitter)
        
        # Get the visibility level for this model
        visibility = get_visibility(model_obj, user)
        
        # Try to find the model in the context
        filtered_models = [model for model in context['models'] if model.model_id == id]

        # The below is used to make use of get_context caching and provides a fallback in case returned cache is missing data
        if filtered_models:
            # Found in context, use this for complete data
            model = filtered_models[0]
            
            # Add per-benchmark ranking information using public models
            try:
                add_benchmark_rankings(model, {'models': public_models})
            except ValueError:
                pass
        else:
            # Not found in context, use the database object
            model = model_obj
            
            # If using the database object directly, still calculate rankings
            if hasattr(model, 'scores') and model.scores:
                try:
                    # Add the current model to the public models temporarily for ranking
                    ranking_context = {'models': public_models + [model]}
                    add_benchmark_rankings(model, ranking_context)
                except ValueError:
                    pass

        # Build benchmark lookup map for template filters (keyed by versioned identifier)
        benchmark_lookup = {}
        for bench in context.get('benchmarks', []):
            # Get parent identifier if parent exists
            parent_id = None
            if hasattr(bench, 'parent') and bench.parent:
                if isinstance(bench.parent, dict):
                    parent_id = bench.parent.get('identifier')
                else:
                    parent_id = getattr(bench.parent, 'identifier', None)

            # Build combined meta from the three meta fields
            meta = {}
            data_meta = getattr(bench, 'benchmark_data_meta', None) or {}
            stimuli_meta = getattr(bench, 'benchmark_stimuli_meta', None) or {}
            if isinstance(data_meta, dict):
                if data_meta.get('num_recording_sites'):
                    meta['number_of_recording_sites'] = data_meta['num_recording_sites']
                if data_meta.get('region'):
                    meta['recording_sites'] = data_meta['region']
                if data_meta.get('task'):
                    meta['behavioral_task'] = data_meta['task']
            if isinstance(stimuli_meta, dict):
                if stimuli_meta.get('num_stimuli'):
                    meta['number_of_stimuli'] = stimuli_meta['num_stimuli']

            benchmark_lookup[bench.identifier] = {
                'short_name': bench.short_name,
                'version': bench.version,
                'url': getattr(bench, 'benchmark_url', None),
                'bibtex': getattr(bench, 'benchmark_bibtex', None),
                'depth': bench.depth,
                'number_of_all_children': bench.number_of_all_children,
                'benchmark_type_id': bench.benchmark_type_id,
                'parent_identifier': parent_id,
                'meta': meta if meta else None,
            }

        # Prepare the context for the template
        model_context = {
            'model': model,
            'benchmark_parents': context['benchmark_parents'],
            'uniform_parents': context['uniform_parents'],
            'not_shown_set': context['not_shown_set'],
            'BASE_DEPTH': context['BASE_DEPTH'],
            'domain': domain,
            'submission_details_visible': submission_details_visible,
            'has_user': user is not None,
            'user': user,
            'visibility': visibility,
            'model_name': display_model(model_obj, user),
            'submitter_name': display_submitter(model_obj, user),
            'visual_degrees': model.visual_degrees,
            'layers': getattr(model, 'layers', None),
            'benchmark_lookup': benchmark_lookup,
        }
        
        # Set thread-local benchmark lookup for template filters
        _thread_locals.benchmark_lookup = benchmark_lookup

        end_time = time()
        print(f"Total time taken to get model context: {end_time - start_time} seconds")
        return render(request, 'benchmarks/model.html', model_context)
        
    except FinalModelContext.DoesNotExist:
        raise Http404("Model not found")

# Generate per-benchmark rankings for a model
# This should be moved to database materialized view in future
def add_benchmark_rankings(model, reference_context):
    """
    Add per-benchmark ranking information to each score in the model.
    For both public and private models: compute rank against public models + self
    """
    # Get all public models for comparison
    public_models = [m for m in reference_context['models'] if getattr(m, 'public', True)]
    
    # Pre-compute scores for each benchmark to avoid repeated lookups
    benchmark_scores = {}
    for other_model in public_models + [model]:
        if getattr(other_model, 'model_id', None) == getattr(model, 'model_id', None):
            continue
        for other_score in getattr(other_model, 'scores', []) or []:
            if not isinstance(other_score, dict):
                continue
            versioned_id = other_score.get('versioned_benchmark_identifier')
            if not versioned_id:
                continue
            score_value = other_score.get('score_ceiled')
            if score_value in ('', 'X', None):
                continue
            try:
                score_float = float(score_value)
                if versioned_id not in benchmark_scores:
                    benchmark_scores[versioned_id] = []
                benchmark_scores[versioned_id].append(score_float)
            except (ValueError, TypeError):
                continue
    
    # Process scores
    for score in model.scores:
        if not isinstance(score, dict):
            continue
            
        versioned_benchmark_id = score.get('versioned_benchmark_identifier')
        if not versioned_benchmark_id:
            continue
        
        # If score is invalid, set rank to be same as invalid score
        # i.e., if score is empty, rank is empty. If score is "X", rank is "X", if score is nan, rank is nan
        # Allows us to preserve invalid state in the rank and avoid casting invalid score to float
        score_ceiled = score.get('score_ceiled')
        if score_ceiled in ('', 'X', None):
            score['rank'] = score_ceiled
            continue
            
        try:
            score_value = float(score_ceiled)
            all_scores = benchmark_scores.get(versioned_benchmark_id, [])
            # Sort scores in descending order and find the rank
            sorted_scores = sorted(all_scores, reverse=True)
            # Find the position of the current score (1-indexed)
            # If there are ties, all tied scores get the same rank
            rank = 1
            for i, s in enumerate(sorted_scores):
                if s > score_value:
                    rank = i + 2  # +2 because we want 1-indexed and we're looking for the next position
                elif s == score_value:
                    rank = i + 1  # +1 for 1-indexed
                    break
            score['rank'] = rank
        except (ValueError, TypeError):
            score['rank'] = 'N/A'


def simplify_score(score):
    try:
        return float(score)
    except ValueError:  # score is '', 'X', or nan
        return 0


@register.filter
def score_style(score_ceiled):
    if not score_ceiled or score_ceiled == '' or score_ceiled == 'X':
        return score_ceiled
    try:
        return 100 * float(score_ceiled)
    except (ValueError, TypeError):
        return score_ceiled


def _get_benchmark_data(score_row, field, default=None):
    """
    Helper to get benchmark field from score_row.
    First tries score_row['benchmark'][field] (embedded data).
    Falls back to thread-local benchmark_lookup using versioned_benchmark_identifier.
    """
    if isinstance(score_row, dict):
        # Try embedded benchmark data first
        benchmark = score_row.get('benchmark', {})
        if field in benchmark and benchmark[field] is not None:
            return benchmark[field]

        # Fall back to thread-local lookup
        versioned_id = score_row.get('versioned_benchmark_identifier')
        if versioned_id:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(versioned_id, {})
            return benchmark_data.get(field, default)

    # Handle namedtuple/object case
    if hasattr(score_row, 'benchmark'):
        return getattr(score_row.benchmark, field, default)

    return default


@register.filter
def is_parent(score_row_or_benchmark):
    """Check if benchmark has children. Accepts score_row or benchmark dict."""
    if isinstance(score_row_or_benchmark, dict):
        # If it's a score_row dict, get the children count via lookup
        versioned_id = score_row_or_benchmark.get('versioned_benchmark_identifier')
        if versioned_id:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(versioned_id, {})
            return benchmark_data.get('number_of_all_children', 0) > 0

        # If it's a benchmark dict directly, check embedded children
        children = score_row_or_benchmark.get('children')
        if children is not None:
            return len(children) > 0

        # Fall back to lookup using identifier
        identifier = score_row_or_benchmark.get('identifier')
        if identifier:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(identifier, {})
            return benchmark_data.get('number_of_all_children', 0) > 0
        return False
    return hasattr(score_row_or_benchmark, 'children') and len(score_row_or_benchmark.children) > 0


@register.filter
def should_hide(score_row_or_benchmark):
    """Check if benchmark should be hidden based on depth and identifier. Accepts score_row or benchmark dict."""
    if isinstance(score_row_or_benchmark, dict):
        # If it's a score_row dict, get depth and type via lookup
        versioned_id = score_row_or_benchmark.get('versioned_benchmark_identifier')
        if versioned_id:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(versioned_id, {})
            depth = benchmark_data.get('depth', 0)
            benchmark_type_id = benchmark_data.get('benchmark_type_id', '')
            return depth >= 1 or benchmark_type_id.startswith('engineering')

        # If it's a benchmark dict directly
        depth = score_row_or_benchmark.get('depth')
        benchmark_type_id = score_row_or_benchmark.get('benchmark_type_id', '')

        # Fall back to lookup if not embedded
        if depth is None:
            identifier = score_row_or_benchmark.get('identifier')
            if identifier:
                lookup = getattr(_thread_locals, 'benchmark_lookup', {})
                benchmark_data = lookup.get(identifier, {})
                depth = benchmark_data.get('depth', 0)
                benchmark_type_id = benchmark_data.get('benchmark_type_id', '')
            else:
                depth = 0

        return depth >= 1 or benchmark_type_id.startswith('engineering')
    return score_row_or_benchmark.depth >= 1 or score_row_or_benchmark.benchmark_type_id.startswith('engineering')


@register.filter
def get_benchmark_short_name(score_row):
    """Get benchmark short name from score row dictionary"""
    return _get_benchmark_data(score_row, 'short_name', '')


@register.filter
def get_benchmark_version(score_row):
    """Get benchmark version from score row dictionary"""
    return _get_benchmark_data(score_row, 'version')


@register.filter
def get_benchmark_url(score_row):
    """Get benchmark URL from score row dictionary"""
    return _get_benchmark_data(score_row, 'url')


@register.filter
def get_benchmark_type_id(score_row):
    """Get benchmark type ID from score row dictionary"""
    return _get_benchmark_data(score_row, 'benchmark_type_id')


@register.filter
def get_benchmark_children_count(score_row):
    """Get number of children from score row dictionary"""
    return _get_benchmark_data(score_row, 'number_of_all_children', 0)


@register.filter
def scores_bibtex(scores):
    """Get unique bibtex entries from scores, using thread-local benchmark lookup."""
    bibtexs = []
    lookup = getattr(_thread_locals, 'benchmark_lookup', {})

    for score_row in scores:
        if isinstance(score_row, dict):
            if not score_row.get('score_ceiled'):
                continue

            # Try embedded bibtex first
            bibtex = score_row.get('benchmark', {}).get('bibtex')

            # Fall back to lookup
            if not bibtex:
                versioned_id = score_row.get('versioned_benchmark_identifier')
                if versioned_id:
                    benchmark_data = lookup.get(versioned_id, {})
                    bibtex = benchmark_data.get('bibtex')

            if bibtex:
                bibtexs.append(bibtex.strip())
        else:  # namedtuple
            if hasattr(score_row, 'score_ceiled') and score_row.score_ceiled and \
               hasattr(score_row, 'benchmark') and hasattr(score_row.benchmark, 'benchmark_type') and \
               score_row.benchmark.benchmark_type.reference:
                bibtex = score_row.benchmark.benchmark_type.reference.bibtex
                bibtex = bibtex.strip().strip('﻿')
                bibtexs.append(bibtex)

    # filter unique, maintain order
    if bibtexs:
        _, idx = np.unique(bibtexs, return_index=True)
        bibtexs = np.array(bibtexs)[np.sort(idx)]
    return bibtexs


@register.filter
def get_benchmark_depth(score_row):
    """Get benchmark depth from score row dictionary"""
    return _get_benchmark_data(score_row, 'depth', 0)


@register.filter
def get_score_color(score_row):
    """Get color style from score row dictionary"""
    return score_row.get('color', '')


@register.filter
def get_score_ceiled(score_row):
    """Get ceiled score from score row dictionary"""
    return score_row.get('score_ceiled', '')


@register.filter
def get_score_best(score_row):
    """Get best score from score row dictionary"""
    try:
        return float(score_row.get('best', 0)) * 100  # Convert to percentage
    except (ValueError, TypeError):
        return 0

@register.filter
def get_score_median(score_row):
    """Get median score from score row dictionary"""
    try:
        return float(score_row.get('median', 0)) * 100  # Convert to percentage
    except (ValueError, TypeError):
        return 0

# Database returns layers in alphabetical order, so reorder them in specific sequence
@register.filter
def order_layers(layers_dict):
    """Order layers in the specific sequence: V1, V2, V4, IT"""
    if not layers_dict:
        return []
        
    # Define the desired order
    desired_order = ['V1', 'V2', 'V4', 'IT']
    # Create a list to store ordered items
    ordered_items = []
    
    # First add items in the desired order
    for key in desired_order:
        if key in layers_dict:
            ordered_items.append((key, layers_dict[key]))
    
    # Then add any remaining items that weren't in the desired order
    for key, value in layers_dict.items():
        if key not in desired_order:
            ordered_items.append((key, value))
            
    return ordered_items

@register.filter
def has_valid_score(score_row):
    """Check if the score row has a valid score (not X or empty)"""
    score = score_row.get('score_ceiled', '')
    return score and score != "X"


@register.filter
def get_benchmark_parent_identifier(score_row):
    """Get parent benchmark identifier from score row dictionary"""
    return _get_benchmark_data(score_row, 'parent_identifier')


@register.filter
def get_benchmark_meta(score_row):
    """Get benchmark meta dict from score row dictionary"""
    return _get_benchmark_data(score_row, 'meta')


@register.filter
def get_benchmark_meta_field(score_row, field):
    """Get specific field from benchmark meta"""
    meta = _get_benchmark_data(score_row, 'meta')
    if meta and isinstance(meta, dict):
        return meta.get(field)
    return None
