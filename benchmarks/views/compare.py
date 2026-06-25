import json

from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .index import get_context
from .compare_models import (
    _build_benchmark_domain_map,
    _build_model_metadata,
    _build_benchmark_url_map,
)
from .model_trends import load_and_build_comparison_trend


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


@require_GET
def trend_pair(request, domain: str):
    """JSON for the compare-page overlaid trend. Query: ``mid_a``, ``mid_b``."""
    try:
        mid_a = int(request.GET.get('mid_a', ''))
        mid_b = int(request.GET.get('mid_b', ''))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('mid_a and mid_b must be integer model ids')
    if mid_a == mid_b:
        return JsonResponse({'score': None, 'rank': None})
    return JsonResponse(load_and_build_comparison_trend(mid_a, mid_b, domain))
