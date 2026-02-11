import json

from django.shortcuts import render

from .index import get_context
from .compare_models import _build_benchmark_domain_map


def view(request, domain: str):
    context = get_context(show_public=True, domain=domain)
    benchmark_domain_map = _build_benchmark_domain_map(context["benchmarks"])
    context["benchmark_domain_map"] = json.dumps(benchmark_domain_map)
    return render(request, 'benchmarks/compare.html', context)
