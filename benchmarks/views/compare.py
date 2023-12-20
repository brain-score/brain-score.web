from django.shortcuts import render
from django.views.decorators.cache import cache_page


from .index import get_context

@cache_page(24 * 60 * 60)
def view(request, domain: str):
    context = get_context(show_public=True, domain=domain)

    return render(request, 'benchmarks/compare.html', context)
