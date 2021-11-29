from .index import get_context
from django.shortcuts import render


def view(request):
    context = get_context()
    context['models'] = [model for model in context['models'] if model.competition == 'cosyne2022']
    return render(request, 'benchmarks/competition.html', context)
