"""Structural invariants for the AG-Grid leaderboard payload builder.

These exercise ``get_ag_grid_context`` against the shared ``web_tests`` DB (see
``BaseTestCase``) and assert shape/ordering guarantees the frontend relies on,
rather than exact data values (which drift as the DB changes).
"""
import json

from benchmarks.views.leaderboard import get_ag_grid_context
from .test_views import BaseTestCase

PRIORITY_PREFIXES = ["average", "neural", "behavior", "engineering"]


class TestAgGridContext(BaseTestCase):
    def _ctx(self, domain="vision"):
        return get_ag_grid_context(user=None, domain=domain, show_public=True)

    def test_required_keys_present_and_comparison_data_absent(self):
        ctx = self._ctx()
        for key in ["row_data", "column_defs", "benchmark_tree", "filter_options",
                    "benchmark_metadata", "benchmark_ids", "benchmark_bibtex_map",
                    "model_metadata_map", "domain"]:
            self.assertIn(key, ctx)
        # comparison_data belongs to the compare page, not the leaderboard payload
        self.assertNotIn("comparison_data", ctx)

    def test_row_data_parses_and_is_non_empty(self):
        rows = json.loads(self._ctx()["row_data"])
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)
        first = rows[0]
        self.assertIn("model", first)
        self.assertIn("name", first["model"])

    def test_column_defs_pinned_and_priority_sorted(self):
        cols = json.loads(self._ctx()["column_defs"])
        by_field = {c["field"]: c for c in cols}
        # rank and model are pinned left (AG-Grid pins them regardless of array order)
        self.assertEqual(by_field["rank"]["pinned"], "left")
        self.assertEqual(by_field["model"]["pinned"], "left")

        def priority(field):
            prefix = field.split("_")[0] if isinstance(field, str) else ""
            return PRIORITY_PREFIXES.index(prefix) if prefix in PRIORITY_PREFIXES else 999

        # column_defs is sorted by category priority (average < neural < behavior < engineering < rest)
        priorities = [priority(c.get("field")) for c in cols]
        self.assertEqual(priorities, sorted(priorities))

    def test_benchmark_tree_is_domain_aware(self):
        for domain in ["vision", "language"]:
            tree = json.loads(self._ctx(domain)["benchmark_tree"])
            root_ids = [node["id"] for node in tree]
            # the domain average is stripped so its children become the roots
            self.assertNotIn(f"average_{domain}_v0", root_ids)
            self.assertTrue(all(f"average_{domain}" not in rid for rid in root_ids))

    def test_filter_options_shape(self):
        opts = json.loads(self._ctx()["filter_options"])
        for key in ["architectures", "model_families", "parameter_ranges",
                    "layer_ranges", "size_ranges", "ceiling_ranges"]:
            self.assertIn(key, opts)
        self.assertEqual(opts["parameter_ranges"]["min"], 0)
