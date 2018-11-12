import numpy as np
from colour import Color
from django.shortcuts import render

from benchmarks.models import CandidateModel

colors = list(Color('red').range_to(Color('green'), 101))
# scale colors: highlight differences at the top-end of the spectrum more than at the lower end
a, b = .002270617, 2.321928  # fit to (0, 0), (50, 20), (100, 100)
colors = [colors[int(a * np.power(i, b))] for i in range(len(colors))]
color_suffix = '_color'

ceilings = {
    'V4': .892,
    'IT': .817,
    'behavior': .479,
    'imagenet_top1': 100,
}
ceilings['brain_score'] = np.mean([ceilings[field] for field in ['V4', 'IT', 'behavior']])


def view(request):
    models = CandidateModel.objects.order_by('-brain_score')
    data = {}
    for field in ['brain_score', 'V4', 'IT', 'behavior', 'imagenet_top1']:
        ceiling = ceilings[field] if field in ceilings else None
        values = [getattr(model, field) for model in models]
        data[field] = represent(ceiling)
        data[field + color_suffix] = representative_color(ceiling, ceiling=ceiling)  # ceiling is 100% by definition
        min_value, max_value = min(values), max(values)

        for model in models:
            value = getattr(model, field)
            setattr(model, field, represent(value))

            if field == 'brain_score':
                rank = values.index(value)
                setattr(model, 'rank', rank + 1)

            color = representative_color(value, ceiling=ceiling, alpha_min=min_value, alpha_max=max_value)
            setattr(model, field + color_suffix, color)
    context = {'models': models, 'data': data}
    return render(request, 'benchmarks/index.html', context)


def normalize(value, min_value, max_value):
    # intercept and slope equations are from solving `y = slope * x + intercept`
    # with points [min_value, 10] (10 instead of 0 to not make it completely transparent) and [max_value, 100].
    slope = -.9 / (min_value - max_value)
    intercept = .1 - slope * min_value
    result = slope * value + intercept
    return result


def represent(value):
    return "{:.3f}".format(value).lstrip('0') if value < 1 else "{:.1f}".format(value)


def representative_color(value, ceiling, alpha_min=None, alpha_max=None):
    step = int(100 * value / ceiling)
    color = colors[step]
    color = tuple(c * 255 for c in color.rgb)
    fallback_color = tuple(round(c) for c in color)
    normalized_value = normalize(value, min_value=alpha_min, max_value=alpha_max) \
        if alpha_min is not None else (100 * value / ceiling)
    color += (normalized_value,)
    return f"background-color: rgb{fallback_color}; background-color: rgba{color};"
