from django.shortcuts import render
from .index import get_context


def view(request):
    context = get_context(domain="language")
    return render(request, 'benchmarks/index.html', context)
