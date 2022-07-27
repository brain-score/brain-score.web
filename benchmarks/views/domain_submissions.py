from django.shortcuts import render
from .index import get_context


def view(request):
    if "language" in request.path:
        context = get_context(domain="language")
    else:
        context = get_context(domain="vision")
    return render(request, 'benchmarks/domain-submissions.html', context)
