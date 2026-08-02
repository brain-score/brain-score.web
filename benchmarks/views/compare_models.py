import logging
import re
from decimal import Decimal
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
    "neural_language": "Neural",
    "behavior_language": "Behavioral",
    "engineering_language": "Engineering",
    "average_language": "Average Language",
}

_VERSION_SUFFIX = re.compile(r"_v(?P<version>\d+)$")


def _build_benchmark_domain_map(benchmarks: List[FinalBenchmarkContext]) -> Dict[str, str]:
    """
    Map every benchmark's versioned identifier to a display domain.

    Walks the parent chain for every benchmark (leaves and parents) to find
    the first neural, behavioral, engineering, or domain-average ancestor.
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
    """Map model id -> card metadata without assuming model names are unique."""
    metadata: Dict[str, Dict[str, Any]] = {}
    for model in models:
        user = model.user if isinstance(model.user, dict) else {}
        contributor = user.get("display_name", "")
        metadata[str(model.model_id)] = {
            "name": model.name,
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


def _version_from_identifier(identifier: str, fallback: int = 0) -> int:
    match = _VERSION_SUFFIX.search(identifier or "")
    return int(match.group("version")) if match else int(fallback or 0)


def _strip_version(identifier: str) -> str:
    return _VERSION_SUFFIX.sub("", identifier or "")


def _isoformat(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _json_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _merge_version_window(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """Fill a benchmark version window from any score row that carries it."""
    valid_from = source.get("version_valid_from")
    valid_to = source.get("version_valid_to")
    if valid_from and not target.get("valid_from"):
        target["valid_from"] = _isoformat(valid_from)
    if valid_to and not target.get("valid_to"):
        target["valid_to"] = _isoformat(valid_to)


def _build_compare_dashboard_payload(
    benchmarks: List[FinalBenchmarkContext],
    models: List[FinalModelContext],
    domain: str,
    datetime_range: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the normalized score timelines used by the compare dashboard.

    The existing ``comparison_data`` is intentionally left intact for other
    pages. This payload keeps version windows separate from per-model values,
    which avoids repeating historical benchmark metadata in every chart.
    """
    benchmark_by_type = {benchmark.benchmark_type_id: benchmark for benchmark in benchmarks}
    benchmark_by_base = {
        _strip_version(benchmark.identifier): benchmark for benchmark in benchmarks
    }
    domain_map = _build_benchmark_domain_map(benchmarks)

    def resolve_parent(benchmark: FinalBenchmarkContext) -> Any:
        parent = benchmark.parent if isinstance(benchmark.parent, dict) else {}
        parent_identifier = parent.get("identifier")
        if not parent_identifier:
            return None
        parent_benchmark = (
            benchmark_by_type.get(parent_identifier)
            or benchmark_by_base.get(_strip_version(parent_identifier))
        )
        return parent_benchmark.identifier if parent_benchmark else parent_identifier

    def is_engineering(benchmark: FinalBenchmarkContext) -> bool:
        current = benchmark
        visited = set()
        while current and current.benchmark_type_id not in visited:
            visited.add(current.benchmark_type_id)
            if "engineering" in current.benchmark_type_id.lower():
                return True
            parent = current.parent if isinstance(current.parent, dict) else {}
            parent_identifier = parent.get("identifier")
            current = (
                benchmark_by_type.get(parent_identifier)
                or benchmark_by_base.get(_strip_version(parent_identifier))
            )
        return False

    benchmark_payload = []
    version_windows: Dict[str, Dict[int, Dict[str, Any]]] = {}
    for benchmark in benchmarks:
        current_version = int(benchmark.version or 0)
        version_windows[benchmark.benchmark_type_id] = {
            current_version: {
                "version": current_version,
                "identifier": benchmark.identifier,
                "valid_from": None,
                "valid_to": None,
            }
        }
        benchmark_payload.append({
            "id": benchmark.identifier,
            "type_id": benchmark.benchmark_type_id,
            "label": benchmark.short_name,
            "parent_id": resolve_parent(benchmark),
            "is_leaf": benchmark.number_of_all_children == 0,
            "is_engineering": is_engineering(benchmark),
            "display_domain": domain_map.get(benchmark.identifier, "Unknown"),
        })

    model_payload = []
    for model in models:
        serialized_scores: Dict[str, List[Dict[str, Any]]] = {}
        for score in model.scores or []:
            type_id = score.get("benchmark_type_id")
            if type_id not in benchmark_by_type:
                continue

            current_identifier = score.get("versioned_benchmark_identifier", "")
            current_version = _version_from_identifier(
                current_identifier,
                getattr(benchmark_by_type[type_id], "version", 0),
            )
            current_window = version_windows[type_id].setdefault(current_version, {
                "version": current_version,
                "identifier": current_identifier or f"{type_id}_v{current_version}",
                "valid_from": None,
                "valid_to": None,
            })
            _merge_version_window(current_window, score)

            versions = [{
                "version": current_version,
                "value": _json_scalar(score.get("score_ceiled")),
                "error": _json_scalar(score.get("error")),
                "timestamp": _isoformat(score.get("end_timestamp")),
            }]

            historical = score.get("historical_versions") or {}
            historical_items = historical.items() if isinstance(historical, dict) else []
            for version_key, historical_score in historical_items:
                if not isinstance(historical_score, dict):
                    continue
                historical_version = int(historical_score.get("version", version_key))
                historical_window = version_windows[type_id].setdefault(historical_version, {
                    "version": historical_version,
                    "identifier": f"{type_id}_v{historical_version}",
                    "valid_from": None,
                    "valid_to": None,
                })
                _merge_version_window(historical_window, historical_score)
                versions.append({
                    "version": historical_version,
                    "value": _json_scalar(historical_score.get("value")),
                    "error": _json_scalar(historical_score.get("error")),
                    "timestamp": _isoformat(historical_score.get("timestamp")),
                })

            serialized_scores[type_id] = sorted(versions, key=lambda item: item["version"])

        model_payload.append({
            "id": model.model_id,
            "name": model.name,
            "rank": getattr(model, "rank", None),
            "submission_timestamp": _isoformat(getattr(model, "timestamp", None)),
            "scores": serialized_scores,
        })

    benchmark_payload_by_type = {item["type_id"]: item for item in benchmark_payload}
    for type_id, versions in version_windows.items():
        benchmark_payload_by_type[type_id]["versions"] = sorted(
            versions.values(), key=lambda item: item["version"]
        )

    return {
        "domain": domain,
        "datetime_range": datetime_range,
        "benchmarks": benchmark_payload,
        "models": model_payload,
    }
