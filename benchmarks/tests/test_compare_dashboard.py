import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from benchmarks.views.compare_models import (
    _build_benchmark_domain_map,
    _build_compare_dashboard_payload,
    _build_model_metadata,
)


class TestCompareDashboardPayload(SimpleTestCase):
    def _benchmark(self, type_id, version=0, parent=None, children=0):
        return SimpleNamespace(
            benchmark_type_id=type_id,
            identifier=f"{type_id}_v{version}",
            version=version,
            parent={"identifier": parent} if parent else None,
            number_of_all_children=children,
            short_name=type_id,
            root_parent="average_vision",
            benchmark_id=1,
        )

    def _model(self, model_id, name, scores):
        return SimpleNamespace(
            model_id=model_id,
            name=name,
            rank=model_id,
            timestamp=None,
            scores=scores,
            user={"display_name": "Researcher"},
        )

    def test_normalizes_version_windows_and_model_score_timelines(self):
        benchmarks = [
            self._benchmark("average_vision", children=1),
            self._benchmark("neural_vision", parent="average_vision", children=1),
            self._benchmark("Example.V1-pls", version=2, parent="neural_vision"),
        ]
        models = [self._model(7, "example", [{
            "benchmark_type_id": "Example.V1-pls",
            "versioned_benchmark_identifier": "Example.V1-pls_v2",
            "score_ceiled": ".700",
            "error": 0.01,
            "end_timestamp": "2024-02-01T00:00:00Z",
            "version_valid_from": "2024-01-01T00:00:00Z",
            "version_valid_to": None,
            "historical_versions": {
                "1": {
                    "version": 1,
                    "value": 0.6,
                    "timestamp": "2023-02-01T00:00:00Z",
                    "version_valid_from": "2023-01-01T00:00:00Z",
                    "version_valid_to": "2024-01-01T00:00:00Z",
                }
            },
        }])]

        result = _build_compare_dashboard_payload(
            benchmarks,
            models,
            "vision",
            {"min_unix": 1, "max_unix": 2},
        )

        leaf = next(item for item in result["benchmarks"] if item["type_id"] == "Example.V1-pls")
        self.assertEqual([version["version"] for version in leaf["versions"]], [1, 2])
        self.assertEqual(leaf["parent_id"], "neural_vision_v0")
        self.assertFalse(leaf["is_engineering"])
        self.assertEqual(
            [version["value"] for version in result["models"][0]["scores"]["Example.V1-pls"]],
            [0.6, ".700"],
        )

    def test_model_metadata_uses_ids_when_names_collide(self):
        models = [
            self._model(1, "same-name", []),
            self._model(2, "same-name", []),
        ]
        metadata = _build_model_metadata(models, "vision")
        self.assertEqual(set(metadata), {"1", "2"})
        self.assertEqual(metadata["1"]["name"], "same-name")
        self.assertEqual(metadata["2"]["name"], "same-name")

    def test_language_benchmarks_use_language_domain_groups(self):
        benchmarks = [
            self._benchmark("average_language", children=2),
            self._benchmark(
                "neural_language", parent="average_language", children=1
            ),
            self._benchmark("ExampleLanguage", parent="neural_language"),
            self._benchmark("engineering_language", children=1),
            self._benchmark("SyntaxGym", parent="engineering_language"),
        ]

        mapping = _build_benchmark_domain_map(benchmarks)

        self.assertEqual(mapping["ExampleLanguage_v0"], "Neural")
        self.assertEqual(mapping["SyntaxGym_v0"], "Engineering")

    @patch("benchmarks.views.compare.render")
    @patch("benchmarks.views.compare.get_context")
    def test_compare_view_references_dashboard_data_endpoint(self, get_context, render):
        benchmarks = [self._benchmark("average_vision")]
        models = [self._model(7, "example", [])]
        get_context.return_value = {
            "benchmarks": benchmarks,
            "models": models,
            "comparison_data": "[]",
        }
        sentinel = object()
        render.return_value = sentinel

        from benchmarks.views.compare import view

        response = view(SimpleNamespace(), "vision")

        self.assertIs(response, sentinel)
        context = render.call_args.args[2]
        metadata = json.loads(context["model_metadata"])
        self.assertEqual(context["compare_dashboard_data_url"], "/vision/compare/data/")
        self.assertEqual(context["comparison_data"], "[]")
        self.assertEqual(metadata["7"]["name"], "example")

    @patch("benchmarks.views.compare.get_datetime_range")
    @patch("benchmarks.views.compare.get_context")
    def test_dashboard_data_endpoint_returns_payload(self, get_context, get_datetime_range):
        benchmarks = [self._benchmark("average_vision")]
        models = [self._model(7, "example", [])]
        get_context.return_value = {
            "benchmarks": benchmarks,
            "models": models,
            "comparison_data": "[]",
        }
        get_datetime_range.return_value = {
            "min": "2020-08-27T00:00:00+00:00",
            "max": "2026-08-02T00:00:00+00:00",
        }

        from benchmarks.views.compare import dashboard_data

        response = dashboard_data(SimpleNamespace(method="GET"), "vision")
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["models"][0]["id"], 7)
        self.assertEqual(payload["domain"], "vision")
