import logging
import math

from django.core.cache import cache
from django.db import DatabaseError
from django.shortcuts import render
from django.views import View

from benchmarks.models import FinalBenchmarkContext, FinalModelContext
from benchmarks.utils import load_news


_logger = logging.getLogger(__name__)

PCA_BENCHMARKS = (
    ("V1", "V1"),
    ("V2", "V2"),
    ("V4", "V4"),
    ("IT", "IT"),
    ("behavior_vision", "Behavior"),
)


def _finite_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score) or score == 0:
        return None
    return score


def _score_lookup(model):
    return {
        score.get("benchmark_type_id"): _finite_score(score.get("score_ceiled"))
        for score in (model.scores or [])
    }


def _normalize(vector):
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        return None
    return [value / length for value in vector]


def _principal_vector(covariance, orthogonal_to=()):
    dimension = len(covariance)
    vector = _normalize([1 / (index + 1) for index in range(dimension)])
    if vector is None:
        return None, 0

    for _ in range(100):
        candidate = [
            sum(covariance[row][column] * vector[column] for column in range(dimension))
            for row in range(dimension)
        ]
        for basis in orthogonal_to:
            projection = sum(candidate[index] * basis[index] for index in range(dimension))
            candidate = [
                candidate[index] - projection * basis[index]
                for index in range(dimension)
            ]
        candidate = _normalize(candidate)
        if candidate is None:
            return None, 0
        if sum(abs(candidate[index] - vector[index]) for index in range(dimension)) < 1e-10:
            vector = candidate
            break
        vector = candidate

    transformed = [
        sum(covariance[row][column] * vector[column] for column in range(dimension))
        for row in range(dimension)
    ]
    eigenvalue = max(0, sum(vector[index] * transformed[index] for index in range(dimension)))
    return vector, eigenvalue


def _orthogonal_vector(dimension, orthogonal_to):
    """Return a deterministic unused axis when a component has zero variance."""
    best = None
    best_length = 0
    for axis in range(dimension):
        candidate = [1 if index == axis else 0 for index in range(dimension)]
        for basis in orthogonal_to:
            projection = sum(candidate[index] * basis[index] for index in range(dimension))
            candidate = [
                candidate[index] - projection * basis[index]
                for index in range(dimension)
            ]
        length = math.sqrt(sum(value * value for value in candidate))
        if length > best_length:
            best = candidate
            best_length = length
    return _normalize(best) if best is not None else None


def _initials(display_name):
    if not display_name or display_name.lower() == "anonymous user":
        return "BS"
    words = [word for word in display_name.replace("_", " ").split() if word]
    if len(words) > 1:
        return (words[0][0] + words[-1][0]).upper()
    return words[0][:2].upper()


def _submitter_name(model):
    submitter = model.submitter if isinstance(model.submitter, dict) else {}
    display_name = submitter.get("display_name")
    if not display_name or display_name.lower() == "anonymous user":
        return "Brain-Score community"
    return display_name


def _model_summary(model):
    scores = _score_lookup(model)
    return {
        "id": model.model_id,
        "name": model.name,
        "rank": model.rank,
        "score": scores.get("average_vision"),
        "timestamp": model.timestamp,
        "submitter": _submitter_name(model),
        "initials": _initials(_submitter_name(model)),
    }


def build_benchmark_space(models):
    """Project complete high-level vision scores onto three principal components."""
    identifiers = [identifier for identifier, _ in PCA_BENCHMARKS]
    rows = []
    for model in models:
        scores = _score_lookup(model)
        values = [scores.get(identifier) for identifier in identifiers]
        if any(value is None for value in values):
            continue
        rows.append((model, values))

    if len(rows) < 3:
        return {"points": [], "variance": [0, 0, 0], "benchmarks": []}

    columns = list(zip(*(values for _, values in rows)))
    means = [sum(column) / len(column) for column in columns]
    deviations = [
        math.sqrt(sum((value - means[index]) ** 2 for value in column) / len(column))
        for index, column in enumerate(columns)
    ]
    standardized = [
        [
            (value - means[index]) / deviations[index] if deviations[index] > 1e-12 else 0
            for index, value in enumerate(values)
        ]
        for _, values in rows
    ]

    dimension = len(identifiers)
    covariance = [
        [
            sum(row[left] * row[right] for row in standardized) / (len(standardized) - 1)
            for right in range(dimension)
        ]
        for left in range(dimension)
    ]
    first, first_value = _principal_vector(covariance)
    second, second_value = _principal_vector(covariance, (first,)) if first else (None, 0)
    if second is None and first is not None:
        second = _orthogonal_vector(dimension, (first,))
    third, third_value = (
        _principal_vector(covariance, (first, second))
        if first and second else (None, 0)
    )
    if third is None and first is not None and second is not None:
        third = _orthogonal_vector(dimension, (first, second))
    if first is None or second is None or third is None:
        return {"points": [], "variance": [0, 0, 0], "benchmarks": []}

    total_variance = sum(covariance[index][index] for index in range(dimension))
    variance = [
        round(100 * value / total_variance, 1) if total_variance > 0 else 0
        for value in (first_value, second_value, third_value)
    ]
    points = []
    for (model, _), row in zip(rows, standardized):
        summary = _model_summary(model)
        points.append({
            "id": summary["id"],
            "name": summary["name"],
            "rank": summary["rank"],
            "score": summary["score"],
            "x": round(sum(row[index] * first[index] for index in range(dimension)), 5),
            "y": round(sum(row[index] * second[index] for index in range(dimension)), 5),
            "z": round(sum(row[index] * third[index] for index in range(dimension)), 5),
        })

    return {
        "points": points,
        "variance": variance,
        "benchmarks": [label for _, label in PCA_BENCHMARKS],
    }


def _update_kind(item):
    text = item.get("text", "").lower()
    if "benchmark" in text:
        return "Benchmark"
    if text.startswith("blog:"):
        return "Story"
    if "compare" in text or "leaderboard" in text or "released" in text:
        return "Platform"
    return "Update"


def landing_context():
    updates = []
    for item in load_news()[:4]:
        updates.append({**item, "kind": _update_kind(item)})

    context = {
        "comparison_data": "[]",
        "news_items": updates,
        "recent_models": [],
        "leaderboard_models": [],
        "benchmark_space": {"points": [], "variance": [0, 0, 0], "benchmarks": []},
        "public_model_count": None,
        "benchmark_count": None,
    }
    cached_data = None
    try:
        cached_data = cache.get("landing_dashboard_data_v2")
    except Exception as exc:
        _logger.warning("Could not read cached landing dashboard data: %s", exc)
    if cached_data:
        context.update(cached_data)
        return context

    try:
        top_models = list(
            FinalModelContext.objects.filter(domain="vision", public=True)
            .order_by("rank")[:80]
        )
        recent_models = list(
            FinalModelContext.objects.filter(
                domain="vision", public=True, timestamp__isnull=False
            ).order_by("-timestamp")[:4]
        )
        dashboard_data = {
            "recent_models": [_model_summary(model) for model in recent_models],
            "leaderboard_models": [_model_summary(model) for model in top_models[:5]],
            "benchmark_space": build_benchmark_space(top_models),
            "public_model_count": FinalModelContext.objects.filter(
                domain="vision", public=True
            ).count(),
            "benchmark_count": FinalBenchmarkContext.objects.filter(
                domain="vision", visible=True
            ).count(),
        }
        context.update(dashboard_data)
        try:
            cache.set("landing_dashboard_data_v2", dashboard_data, 15 * 60)
        except Exception as exc:
            _logger.warning("Could not cache landing dashboard data: %s", exc)
    except DatabaseError as exc:
        _logger.warning("Could not build landing dashboard data: %s", exc)
    return context


class LandingPage(View):
    def get(self, request):
        return render(request, "benchmarks/landing_page.html", landing_context())
