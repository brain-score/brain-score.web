import logging
from ast import literal_eval
from collections import ChainMap, OrderedDict, namedtuple
import json

import numpy as np
from django.http import Http404
from django.shortcuts import render
from django.template.defaulttags import register

from .index import (_collect_benchmarks, _collect_models, _build_scores_dataframe,
                   _build_comparison_data, _collect_submittable_benchmarks,
                   BASE_DEPTH, ENGINEERING_ROOT, get_context)
from ..models import BenchmarkType, Model

_logger = logging.getLogger(__name__)

def view(request, id: int, domain: str):
    model, model_context, reference_context = determine_context(id, request, domain, model_filter={"model_id":id})

    # takes care of odd issue where valueError is raised when
    # models are scored on some benchmarks, but not others.
    try:
        contextualize_scores(model, reference_context)
    except ValueError:
        pass
    model_context['model'] = model
    del model_context['models']
    # visual degrees
    visual_degrees = Model.objects.get(id=model.id).visual_degrees
    model_context['visual_degrees'] = visual_degrees
    # layer assignment
    layers = get_layers(model)
    model_context['layers'] = layers

    # only show detailed model info to superuser or owner:
    if request.user.is_superuser or model.user.id == request.user.id:
        model_context['submission_details_visible'] = True
    return render(request, 'benchmarks/model.html', model_context)


def determine_context(id, request, domain: str, model_filter=None):
    # this is a bit hacky: we're loading scores for *all* public models as well as *all* of the user's models
    # so we're loading a lot of unnecessary detail. But it lets us re-use already existing code.
    reference_context = get_context(show_public=True, model_filter=model_filter, domain=domain)
    # first check if model is in public list
    model_context = reference_context
    model = [m for m in reference_context['models'] if m.id == id]
    if len(model) != 1 and not request.user.is_anonymous:  # model not found in public list, try user's private
        model_context = get_model_context(request.user)
        model = [m for m in model_context['models'] if m.id == id]
    if len(model) != 1:
        raise Http404(f"Model with id {id} not found or user does not have access")
    model = model[0]
    return model, model_context, reference_context

def get_model_context(show_public: bool, model_id: int, domain: str, user=None):
    benchmarks = _collect_benchmarks(domain, user_page=True if user is not None else False)
        
    model_filter = {'model_id': model_id}
    
    # Get just this model's data
    model_rows = _collect_models(
        domain=domain,
        benchmarks=benchmarks,
        show_public=show_public,  # We want to show the model regardless of public status (access control handled elsewhere)
        user=user,
        score_filter=model_filter
    )

    csv_data = _build_scores_dataframe(benchmarks, model_rows)

    # Build comparison data for just this model
    public_models = [model_row for model_row in model_rows if model_row.public]
    comparison_data = _build_comparison_data(public_models)

    # Get submittable benchmarks if user provided
    submittable_benchmarks = None
    if user is not None:
        submittable_benchmarks = _collect_submittable_benchmarks(benchmarks=benchmarks, user=user)

    # Get benchmark names (leaf nodes only)
    benchmark_names = [b.identifier for b in list(filter(lambda b: b.number_of_all_children == 0, benchmarks))]

    # Build benchmark hierarchy data
    benchmark_parents = {
        benchmark.identifier: f'{benchmark.benchmark_type.parent.identifier}_v0'
        if benchmark.benchmark_type.parent else None
        for benchmark in benchmarks
    }
    uniform_parents = set(benchmark_parents.values())
    not_shown_set = {
        benchmark.identifier for benchmark in benchmarks
        if benchmark.depth > BASE_DEPTH or
        (ENGINEERING_ROOT not in benchmark.identifier and ENGINEERING_ROOT in benchmark.root_parent)
    }

    return {
        'domain': domain,
        'models': model_rows,
        'benchmarks': benchmarks,
        'benchmark_names': benchmark_names,
        'submittable_benchmarks': submittable_benchmarks,
        'benchmark_parents': benchmark_parents,
        'uniform_parents': uniform_parents,
        'not_shown_set': not_shown_set,
        'BASE_DEPTH': BASE_DEPTH,
        'has_user': user is not None,
        'comparison_data': json.dumps(comparison_data),
        'csv_downloadable': csv_data
    }

def contextualize_scores(model, reference_context):
    # modify scores: add rank to score
    for i, score in enumerate(model.scores):
        other_scores = [other_score.score_ceiled
                        for other_model in reference_context['models']
                        for other_score in other_model.scores
                        if other_model.public
                        and other_score.versioned_benchmark_identifier == score.versioned_benchmark_identifier
                        ]
        other_scores = [simplify_score(other_score) for other_score in other_scores]
        # per-score ranks
        if score.score_ceiled == 'X' or score.score_ceiled == '':
            rank = score.score_ceiled
        else:
            better = [other_score for other_score in other_scores
                      if float(other_score) > float(score.score_ceiled)]
            rank = len(better) + 1
        best = np.max(other_scores)
        best = best * 100  # convert to percent
        median = np.median(other_scores)
        median = median * 100  # convert to percent
        # score is a namedtuple, need to create a new one with the new fields
        score_rank_class = namedtuple(score.__class__.__name__, score._fields + ('median', 'best', 'rank'))
        score = score_rank_class(*([getattr(score, field) for field in score._fields] + [median, best, rank]))
        model.scores[i] = score


def get_layers(model):
    LAYERS_MARKER = 'layers: '
    layer_comments = [score.comment.replace(LAYERS_MARKER, '') for score in model.scores
                      if score.comment is not None and score.comment.startswith(LAYERS_MARKER)]
    layer_comments = [literal_eval(comment_dict) for comment_dict in layer_comments]
    merged_layers = dict(ChainMap(*layer_comments))
    region_order = {benchmark_type.identifier: benchmark_type.order for benchmark_type in
                    BenchmarkType.objects.filter(identifier__in=list(merged_layers))}
    merged_layers = OrderedDict([(region, layer) for region, layer in
                                 sorted(merged_layers.items(),
                                        key=lambda region_layer: region_order[region_layer[0]])])
    return merged_layers


def simplify_score(score):
    try:
        return float(score)
    except ValueError:  # score is '', 'X', or nan
        return 0


@register.filter
def score_style(score_ceiled):
    if score_ceiled == '' or score_ceiled == 'X':
        return score_ceiled
    return 100 * float(score_ceiled)


@register.filter
def is_parent(benchmark):
    return hasattr(benchmark, 'children') and len(benchmark.children) > 0


@register.filter
def scores_bibtex(scores):
    bibtexs = []
    for score_row in scores:
        if score_row.score_ceiled and score_row.benchmark.benchmark_type.reference:
            bibtex = score_row.benchmark.benchmark_type.reference.bibtex
            bibtex = bibtex.strip().strip('﻿')
            bibtexs.append(bibtex)
    # filter unique, but maintain order
    _, idx = np.unique(bibtexs, return_index=True)
    bibtexs = np.array(bibtexs)[np.sort(idx)]
    return bibtexs


@register.filter
def should_hide(benchmark) -> bool:
    return benchmark.depth >= 1 or benchmark.benchmark_type_id.startswith('engineering')
