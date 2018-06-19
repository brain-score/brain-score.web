from colour import Color
from django.shortcuts import render

from .models import CandidateModel

colors = list(Color('red').range_to(Color('green'), 100))


def index(request):
    models = CandidateModel.objects.order_by('-brain_score')
    for model in models:
        for field in ['brain_score', 'v4', 'it', 'behavior', 'imagenet_top1']:
            value = getattr(model, field)
            step = int(value * (100 if value < 1 else 1))
            color = colors[step]
            setattr(model, field + '_color', color.hex)
    context = {'models': models}
    return render(request, 'frontend/index.html', context)
