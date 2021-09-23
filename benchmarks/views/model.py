import logging
from collections import ChainMap

from django.shortcuts import render
from ast import literal_eval
from .index import get_context

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
    context['layers'] = merged_layers
    return render(request, 'benchmarks/model.html', context)
