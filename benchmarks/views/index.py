import numpy as np
from colour import Color
from django.shortcuts import render

from benchmarks.models import CandidateModel

colors = list(Color('red').range_to(Color('green'), 100))
color_suffix = '_color'

ceilings = {
    'v4': .892,
    'it': .817,
    'behavior': .479,
    'imagenet_top1': 1.,
}
ceilings['brain_score'] = np.mean([np.mean([ceilings['v4'], ceilings['it']]), ceilings['behavior']])


def view(request):
    models = CandidateModel.objects.order_by('-brain_score')
    data = {}
    for field in ['brain_score', 'v4', 'it', 'behavior', 'imagenet_top1']:
        values = [getattr(model, field) / ceilings[field] for model in models]
        min_value, max_value = min(values), max(values)
        data[field] = represent(max_value)
        data_value = normalize(max_value, min_value)
        data[field + color_suffix] = representative_color(data_value, alpha_max=max_value)

        for model in models:
            value = getattr(model, field) / ceilings[field]
            setattr(model, field, represent(value))

            value = normalize(value, min_value)
            color = representative_color(value, alpha_max=max_value)
            setattr(model, field + color_suffix, color)
    context = {'models': models, 'data': data}
    return render(request, 'benchmarks/index.html', context)


def normalize(value, min_value):
    max_value = 1 if value < 1 else 100
    return (value - min_value) / (max_value - min_value)


def represent(value):
    return "{:.3f}".format(value).lstrip('0') if value < 1 else "{:.1f}".format(value)


def representative_color(value, alpha=True, alpha_max=100):
    if value < 1:
        value *= 100
        if alpha_max < 1:
            alpha_max *= 100
    step = int(value)
    color = colors[step]
    color = tuple(c * 255 for c in color.rgb)
    if alpha:
        color += (value / alpha_max,)
    return "rgb{}{}".format("a" if alpha else "", color)
