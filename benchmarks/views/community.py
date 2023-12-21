from django.shortcuts import render
from django.views.decorators.cache import cache_page


from .index import get_context

def view(request):
    return render(request, 'benchmarks/community.html')
