from colour import Color
from django.shortcuts import render

from benchmarks.models import CandidateModel

colors = list(Color('red').range_to(Color('green'), 100))
color_suffix = '_color'

ceilings = {
    'v4': .892,
    'it': .817,
    'behavior': .479,
    'imagenet_top1': 100,
}


def _is_ie(user_agent):
    user_agent = user_agent.lower()
    return 'trident' in user_agent or 'msie' in user_agent


def view(request):
    user_agent = request.META['HTTP_USER_AGENT']
    is_ie = _is_ie(user_agent)
    models = CandidateModel.objects.order_by('-brain_score')
    data = {}
    for field in ['brain_score', 'v4', 'it', 'behavior', 'imagenet_top1']:
        ceiling = ceilings[field] if field in ceilings else None
        values = [getattr(model, field) for model in models]
        min_value, max_value = min(values), max(values)
        data[field] = represent(max_value)
        normalized_max = normalize(max_value, 0, max_value=ceiling)
        min_normalized_max = normalize(max_value, min_value, max_value=ceiling)
        data[field + color_suffix] = representative_color(min_normalized_max, is_ie=is_ie, alpha_max=normalized_max)

        for model in models:
            value = getattr(model, field)
            setattr(model, field, represent(value))

            if field == 'brain_score':
                rank = values.index(value)
                setattr(model, 'rank', rank + 1)

            normalized_value = normalize(value, min_value, max_value=ceiling)
            color = representative_color(normalized_value, is_ie=is_ie, alpha_max=normalized_max)
            setattr(model, field + color_suffix, color)
    context = {'models': models, 'data': data}
    return render(request, 'benchmarks/index.html', context)


def normalize(value, min_value, max_value=None):
    max_value = max_value or (1 if value < 1 else 100)
    return (value - min_value) / (max_value - min_value)


def represent(value):
    return "{:.3f}".format(value).lstrip('0') if value < 1 else "{:.1f}".format(value)


def representative_color(value, is_ie=False, alpha_max=100):
    if value < 1:
        value *= 100
        if alpha_max < 1:
            alpha_max *= 100
    step = int(value)
    color = colors[step]
    color = tuple(c * 255 for c in color.rgb)
    if not is_ie:
        color += (value / alpha_max,)
    else:
        color = tuple(round(c) for c in color)
    return "rgb{}{}".format("a" if not is_ie else "", color)
