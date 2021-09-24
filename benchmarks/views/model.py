import logging
from ast import literal_eval
from collections import ChainMap, OrderedDict, namedtuple

import numpy as np
from django.shortcuts import render

from .index import get_context
from ..models import BenchmarkType

_logger = logging.getLogger(__name__)


def view(request, id: int):
    # TODO: authenticate user
    # TODO: use colors from main table

    # TODO: we want to contextualize the single-model score by the public scores.
    #  This needs to be changed more generally I think
    # TODO: make this a model-specific lookup without all the other models
    context = get_context(request.user if not request.user.is_anonymous else None)
    model = [m for m in context['models'] if m.id == id]
    assert len(model) == 1
    model = model[0]
    # per-score ranks
    for i, score in enumerate(model.scores):
        if score.score_ceiled == 'X':
            rank = 'X'
        elif score.score_ceiled == '':
            rank = ''
        else:
            better = [other_score for other_model in context['models'] for other_score in other_model.scores
                      if other_score.benchmark_specifier == score.benchmark_specifier
                      and len(other_score.score_ceiled) > 0 and other_score.score_ceiled != 'X'
                      and not np.isnan(float(other_score.score_ceiled))
                      and float(other_score.score_ceiled) > float(score.score_ceiled)]
            rank = len(better) + 1
        # score is a namedtuple, need to create a new one with the `rank` field
        score_rank_class = namedtuple(score.__class__.__name__, score._fields + ('rank',))
        score = score_rank_class(*([getattr(score, field) for field in score._fields] + [rank, ]))
        model.scores[i] = score
    context['model'] = model
    del context['models']

    # visual degrees
    # TODO: this is not stored anywhere -- we might have to re-think the storing of BrainModel translation:
    #  - could do the whole translation only once, store it in some table, and retrieve it again
    #    this would also prevent the case where the public translation data changes, and we get a different model
    #  - could require the user to perform this mapping for us
    context['visual_degrees'] = 8
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
    context['layers'] = merged_layers
    return render(request, 'benchmarks/model.html', context)
    # TODO: where to store info about benchmarks, e.g. number of images, recording sites, behavior?
