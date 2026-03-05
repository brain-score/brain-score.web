import json
from datetime import datetime

from django.shortcuts import render

from .index import get_context, get_datetime_range
from .leaderboard import build_benchmark_tree
from .compare_models import _build_benchmark_domain_map


def view(request, domain: str):
    context = get_context(show_public=True, domain=domain)
    benchmark_domain_map = _build_benchmark_domain_map(context["benchmarks"])
    context["benchmark_domain_map"] = json.dumps(benchmark_domain_map)

    context["benchmark_tree"] = json.dumps(
        build_benchmark_tree(context["benchmarks"])
    )

    datetime_range = get_datetime_range(domain=domain)
    min_ts = datetime.fromisoformat(datetime_range["min"])
    max_ts = datetime.fromisoformat(datetime_range["max"])
    context["datetime_range"] = json.dumps({
        "min": datetime_range["min"],
        "max": datetime_range["max"],
        "min_unix": int(min_ts.timestamp()),
        "max_unix": int(max_ts.timestamp()),
    })

    return render(request, "benchmarks/compare.html", context)
