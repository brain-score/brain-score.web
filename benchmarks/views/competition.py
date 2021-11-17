from .index import get_context
from django.shortcuts import render

def view(request):
    context = get_context()
    return render(request, 'benchmarks/competition.html', context)