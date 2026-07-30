import logging
from typing import Any, Dict, List

from benchmarks.models import FinalBenchmarkContext, FinalModelContext

_logger = logging.getLogger(__name__)

_DOMAIN_MARKERS = {
    "V1": "V1",
    "V2": "V2",
    "V4": "V4",
    "IT": "IT",
    "neural_vision": "Neural",
    "behavior_vision": "Behavioral",
    "engineering_vision": "Engineering",
    "average_vision": "Average Vision",
}


def _build_benchmark_domain_map(benchmarks: List[FinalBenchmarkContext]) -> Dict[str, str]:
    """
    Map every benchmark's versioned identifier to a display domain.

    Walks the parent chain for every benchmark (leaves and parents) to find
    the first domain marker ancestor (V1/V2/V4/IT/behavior_vision/engineering_vision).
    comparison_data includes scores for parent aggregates too, so we must
    classify all of them -- not just leaves.
    """
    by_type_id = {b.benchmark_type_id: b for b in benchmarks}
    domain_map: Dict[str, str] = {}

    for bench in benchmarks:
        domain = _walk_parent_chain(bench, by_type_id)
        if domain:
            domain_map[bench.identifier] = domain

    return domain_map


def _walk_parent_chain(
    bench: FinalBenchmarkContext,
    lookup: Dict[str, FinalBenchmarkContext],
) -> str:
    """Walk up the parent chain to find the first domain marker ancestor."""
    current = bench
    visited: set = set()

    while current and current.benchmark_type_id not in visited:
        visited.add(current.benchmark_type_id)

        # Check if the current node itself is a domain marker
        if current.benchmark_type_id in _DOMAIN_MARKERS:
            return _DOMAIN_MARKERS[current.benchmark_type_id]

        # Check the parent
        if current.parent and isinstance(current.parent, dict):
            parent_id = current.parent.get("identifier", "")
            if parent_id in _DOMAIN_MARKERS:
                return _DOMAIN_MARKERS[parent_id]
            # Walk up to the parent node
            current = lookup.get(parent_id)
        else:
            break

    return None


def _build_model_metadata(
    models: List[FinalModelContext], domain: str
) -> Dict[str, Dict[str, Any]]:
    """Map model name -> {rank, model_id, contributor, url} for the model info cards."""
    metadata: Dict[str, Dict[str, Any]] = {}
    for model in models:
        user = model.user if isinstance(model.user, dict) else {}
        contributor = user.get("display_name", "")
        metadata[model.name] = {
            "rank": getattr(model, "rank", None),
            "model_id": model.model_id,
            "contributor": contributor,
            "url": f"/model/{domain}/{model.model_id}",
        }
    return metadata


def _build_benchmark_url_map(
    benchmarks: List[FinalBenchmarkContext], domain: str
) -> Dict[str, str]:
    """Map versioned benchmark identifier -> detail page URL."""
    url_map: Dict[str, str] = {}
    for bench in benchmarks:
        if bench.benchmark_id is not None:
            url_map[bench.identifier] = f"/benchmark/{domain}/{bench.benchmark_id}"
    return url_map
