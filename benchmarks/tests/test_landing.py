import math
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from benchmarks.views.landing import PCA_BENCHMARKS, build_benchmark_space


def _model(model_id, values, rank=None):
    scores = [
        {"benchmark_type_id": identifier, "score_ceiled": value}
        for (identifier, _), value in zip(PCA_BENCHMARKS, values)
    ]
    scores.append({"benchmark_type_id": "average_vision", "score_ceiled": sum(values) / len(values)})
    return SimpleNamespace(
        model_id=model_id,
        name=f"model-{model_id}",
        rank=rank or model_id,
        scores=scores,
        submitter={"display_name": "Test Researcher"},
        timestamp=None,
    )


class BenchmarkSpaceTests(SimpleTestCase):
    def test_projects_complete_models_onto_two_components(self):
        models = [
            _model(1, [0.20, 0.24, 0.30, 0.35, 0.40]),
            _model(2, [0.23, 0.28, 0.31, 0.39, 0.42]),
            _model(3, [0.31, 0.25, 0.38, 0.44, 0.36]),
            _model(4, [0.37, 0.34, 0.45, 0.48, 0.50]),
            _model(5, [0.42, 0.39, 0.40, 0.52, 0.47]),
            _model(6, [0.48, 0.45, 0.54, 0.58, 0.56]),
        ]

        projection = build_benchmark_space(models)

        self.assertEqual(len(projection["points"]), len(models))
        self.assertEqual(projection["benchmarks"], ["V1", "V2", "V4", "IT", "Behavior"])
        self.assertTrue(all(math.isfinite(point["x"]) for point in projection["points"]))
        self.assertTrue(all(math.isfinite(point["y"]) for point in projection["points"]))
        self.assertGreater(projection["variance"][0], 0)
        self.assertGreaterEqual(projection["variance"][0], projection["variance"][1])

    def test_excludes_models_without_complete_nonzero_branch_scores(self):
        complete = _model(1, [0.20, 0.24, 0.30, 0.35, 0.40])
        second = _model(2, [0.25, 0.29, 0.36, 0.41, 0.46])
        third = _model(3, [0.32, 0.37, 0.42, 0.48, 0.52])
        incomplete = _model(4, [0.35, 0.39, 0, 0.50, 0.55])

        projection = build_benchmark_space([complete, second, third, incomplete])

        self.assertEqual([point["id"] for point in projection["points"]], [1, 2, 3])


class LandingPageTests(SimpleTestCase):
    @patch("benchmarks.views.landing.landing_context")
    def test_homepage_exposes_dashboard_entry_points(self, context):
        context.return_value = {
            "comparison_data": "[]",
            "news_items": [],
            "recent_models": [],
            "leaderboard_models": [],
            "benchmark_space": {"points": [], "variance": [0, 0], "benchmarks": []},
            "public_model_count": None,
            "benchmark_count": None,
        }

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Latest updates")
        self.assertContains(response, "The benchmark space")
        self.assertContains(response, "Compare benchmarks")
        self.assertContains(response, "Compare models")
        self.assertContains(response, "Run locally")
