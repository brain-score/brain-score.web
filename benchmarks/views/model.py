import logging
from ast import literal_eval
from collections import ChainMap, OrderedDict, namedtuple

import numpy as np
from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.template.defaulttags import register

from .index import get_context, display_model, display_submitter, get_visibility
from ..models import BenchmarkType, Model, FinalModelContext

_logger = logging.getLogger(__name__)

import time

def view(request, id: int, domain: str):
    user = request.user if request.user.is_authenticated else None
    
    try:
        start_time = time.time()
        # Get the model from FinalModelContext
        start_time2 = time.time()
        model_obj = FinalModelContext.objects.get(model_id=id, domain=domain)
        print(f"Time taken to get model from FinalModelContext: {time.time() - start_time2} seconds")
        
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
        # Get context based on user authentication - this will include both public and private data
        start_time2 = time.time()
        context = get_context(user=user, domain=domain, show_public=False) if user else get_context(domain=domain, show_public=True)
        print(f"Time taken to get possible user-specific context: {time.time() - start_time2} seconds")
        
        # The public models are now cached within the user context
        public_models = context.get('public_models', context['models']) if user else context['models']
        
        # Determine if submission details should be visible
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
                is_submitter = user.id =w= model_obj.submitter.id
        
        submission_details_visible = user and (user.is_superuser or is_owner or is_submitter)
        
        # Get the visibility level for this model
        visibility = get_visibility(model_obj, user)
        
        # Try to find the model in the context
        filtered_models = [model for model in context['models'] if model.model_id == id]
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
        }
        
        # Add visual degrees if available
        try:
            db_model = Model.objects.get(id=id)
            model_context['visual_degrees'] = db_model.visual_degrees
        except Model.DoesNotExist:
            model_context['visual_degrees'] = None
        
        # Add layer information if available
        model_context['layers'] = getattr(model, 'layers', None)
        end_time = time.time()
        print(f"Total model card time taken: {end_time - start_time} seconds")
        return render(request, 'benchmarks/model.html', model_context)
        
    except FinalModelContext.DoesNotExist:
        raise Http404("Model not found")


def add_benchmark_rankings(model, reference_context):
    """
    Add per-benchmark ranking information to each score in the model
    """
    # Get all public models for comparison
    public_models = [m for m in reference_context['models'] if getattr(m, 'public', True)]

    # Process each score in the model
    for i, score in enumerate(model.scores):
        # Skip if score is not a dictionary
        if not isinstance(score, dict):
            continue
            
        versioned_benchmark_id = score.get('versioned_benchmark_identifier')
        if not versioned_benchmark_id:
            continue
            
        # Get the score value
        score_ceiled = score.get('score_ceiled')
        
        # Skip if score is not valid
        if score_ceiled in ('', 'X', None):
            score['rank'] = score_ceiled
            continue
            
        try:
            score_value = float(score_ceiled)
            
            # Collect all scores for this benchmark from public models
            other_scores = []
            for other_model in public_models:
                # Skip comparing with itself
                if getattr(other_model, 'model_id', None) == getattr(model, 'model_id', None):
                    continue
                    
                for other_score in getattr(other_model, 'scores', []) or []:
                    if isinstance(other_score, dict) and other_score.get('versioned_benchmark_identifier') == versioned_benchmark_id:
                        other_score_value = other_score.get('score_ceiled')
                        if other_score_value not in ('', 'X', None):
                            try:
                                other_scores.append(float(other_score_value))
                            except (ValueError, TypeError):
                                pass
            
            # Calculate rank (number of better scores + 1)
            better_scores = [s for s in other_scores if s > score_value]
            rank = len(better_scores) + 1
            
            # Add the rank to the score dictionary
            score['rank'] = rank
            
        except (ValueError, TypeError):
            # If score can't be converted to float, set rank to N/A
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


@register.filter
def is_parent(benchmark):
    """Check if benchmark has children in dictionary structure"""
    if isinstance(benchmark, dict):
        return benchmark.get('children') is not None and len(benchmark.get('children', [])) > 0
    return hasattr(benchmark, 'children') and len(benchmark.children) > 0


@register.filter
def should_hide(benchmark):
    """Check if benchmark should be hidden based on depth and identifier"""
    if isinstance(benchmark, dict):
        return benchmark.get('depth', 0) >= 1 or benchmark.get('benchmark_type_id', '').startswith('engineering')
    return benchmark.depth >= 1 or benchmark.benchmark_type_id.startswith('engineering')


@register.filter
def get_benchmark_short_name(score_row):
    """Get benchmark short name from score row dictionary"""
    if isinstance(score_row, dict):
        return score_row.get('benchmark', {}).get('short_name', '')
    return score_row.benchmark.short_name if hasattr(score_row, 'benchmark') else ''


@register.filter
def get_benchmark_version(score_row):
    """Get benchmark version from score row dictionary"""
    return score_row.get('benchmark', {}).get('version')


@register.filter
def get_benchmark_url(score_row):
    """Get benchmark URL from score row dictionary"""
    return score_row.get('benchmark', {}).get('url')


@register.filter
def get_benchmark_type_id(score_row):
    """Get benchmark type ID from score row dictionary"""
    return score_row.get('benchmark', {}).get('benchmark_type_id')


@register.filter
def get_benchmark_children_count(score_row):
    """Get number of children from score row dictionary"""
    return score_row.get('benchmark', {}).get('number_of_all_children', 0)


@register.filter
def scores_bibtex(scores):
    bibtexs = []
    for score_row in scores:
        if isinstance(score_row, dict):
            if score_row.get('score_ceiled') and score_row.get('benchmark', {}).get('bibtex'):
                bibtex = score_row['benchmark']['bibtex'].strip()
                bibtexs.append(bibtex)
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
    return score_row.get('benchmark', {}).get('depth', 0)


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
