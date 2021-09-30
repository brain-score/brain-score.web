import logging
from ast import literal_eval
from collections import ChainMap, OrderedDict, namedtuple

import numpy as np
from django.http import Http404
from django.shortcuts import render
from django.template.defaulttags import register

from .index import get_context
from ..models import BenchmarkType, Model

_logger = logging.getLogger(__name__)


def view(request, id: int):
    # this is a bit hacky: we're loading scores for *all* public models as well as *all* of the user's models
    # so we're loading a lot of unnecessary detail. But it lets us re-use already existing code.
    reference_context = get_context(None)  # public models
    # first check if model is in public list
    model_context = reference_context
    model = [m for m in reference_context['models'] if m.id == id]
    if len(model) != 1 and not request.user.is_anonymous:  # model not found in public list, try user's private
        model_context = get_context(request.user)
        model = [m for m in model_context['models'] if m.id == id]
    if len(model) != 1:
        raise Http404(f"Model with id {id} not found or user does not have access")
    model = model[0]
    # modify scores: add rank to score
    for i, score in enumerate(model.scores):
        # per-score ranks
        if score.score_ceiled == 'X':
            rank = 'X'
        elif score.score_ceiled == '':
            rank = ''
        else:
            better = [other_score for other_model in reference_context['models'] for other_score in other_model.scores
                      if other_score.versioned_benchmark_identifier == score.versioned_benchmark_identifier
                      and len(other_score.score_ceiled) > 0 and other_score.score_ceiled != 'X'
                      and not np.isnan(float(other_score.score_ceiled))
                      and float(other_score.score_ceiled) > float(score.score_ceiled)]
            rank = len(better) + 1
        # score is a namedtuple, need to create a new one with the `rank` field
        score_rank_class = namedtuple(score.__class__.__name__, score._fields + ('rank',))
        score = score_rank_class(*([getattr(score, field) for field in score._fields] + [rank, ]))
        model.scores[i] = score

    model_context['model'] = model
    del model_context['models']

    # visual degrees
    visual_degrees = Model.objects.get(id=model.id).visual_degrees
    model_context['visual_degrees'] = visual_degrees
    # layer assignment
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
    model_context['layers'] = merged_layers
    return render(request, 'benchmarks/model.html', model_context)


@register.filter
def format_bibtex(bibtex):
    return bibtex.strip().strip('﻿')
