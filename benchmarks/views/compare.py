import json
from datetime import datetime

from django.http import JsonResponse, HttpResponseBadRequest, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .index import get_context, get_datetime_range
from .compare_models import (
    _build_benchmark_domain_map,
    _build_compare_dashboard_payload,
    _build_model_metadata,
    _build_benchmark_url_map,
)
from .model_trends import load_and_build_comparison_trend
from ..models import FinalModelContext


def view(request, domain: str):
    context = get_context(show_public=True, domain=domain)
    datetime_range = get_datetime_range(domain=domain)
    min_timestamp = datetime.fromisoformat(datetime_range["min"])
    max_timestamp = datetime.fromisoformat(datetime_range["max"])
    serialized_datetime_range = {
        "min": datetime_range["min"],
        "max": datetime_range["max"],
        "min_unix": int(min_timestamp.timestamp()),
        "max_unix": int(max_timestamp.timestamp()),
    }
    benchmark_domain_map = _build_benchmark_domain_map(context["benchmarks"])
    context["benchmark_domain_map"] = json.dumps(benchmark_domain_map)
    context["model_metadata"] = json.dumps(
        _build_model_metadata(context["models"], domain)
    )
    context["benchmark_url_map"] = json.dumps(
        _build_benchmark_url_map(context["benchmarks"], domain)
    )
    context["compare_dashboard_data"] = json.dumps(
        _build_compare_dashboard_payload(
            context["benchmarks"],
            context["models"],
            domain,
            serialized_datetime_range,
        )
    )
    # The dashboard payload supersedes the legacy flat matrix on this page.
    # Avoid sending both copies; the dashboard initializes ``comparison_data``
    # before the existing chart modules run.
    context["comparison_data"] = "[]"
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
    # The compare page is public-only; gate the endpoint the same way so it
    # can't be used to read private models' aggregates by id.
    public_ids = set(FinalModelContext.objects
                     .filter(domain=domain, model_id__in=(mid_a, mid_b), public=True)
                     .values_list('model_id', flat=True))
    if mid_a not in public_ids or mid_b not in public_ids:
        raise Http404('unknown or non-public model id')
    return JsonResponse(load_and_build_comparison_trend(mid_a, mid_b, domain))
