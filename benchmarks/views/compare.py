import json

from django.shortcuts import render

from .index import get_context
from .compare_models import (
    _build_benchmark_domain_map,
    _build_model_metadata,
    _build_benchmark_url_map,
)


def view(request, domain: str):
    context = get_context(show_public=True, domain=domain)
    benchmark_domain_map = _build_benchmark_domain_map(context["benchmarks"])
    context["benchmark_domain_map"] = json.dumps(benchmark_domain_map)
    context["model_metadata"] = json.dumps(
        _build_model_metadata(context["models"], domain)
    )
    context["benchmark_url_map"] = json.dumps(
        _build_benchmark_url_map(context["benchmarks"], domain)
    )
    return render(request, 'benchmarks/compare.html', context)
