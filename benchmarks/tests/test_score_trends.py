"""Unit tests for the score-trend recompute pipeline and view helpers.

The web_tests Postgres DB is shared and read-mostly (see ``BaseTestCase``),
so these tests stick to pure-function tests and mocked-endpoint tests --
no schema mutations.
"""
import json
from unittest.mock import patch

import pandas as pd
from django.conf import settings
from django.test import RequestFactory

from .test_views import BaseTestCase
from benchmarks.management.commands.recompute_score_trends import (
    _aggregate_for_month_fast, _depth_groups, _load_score_and_timestamp_dfs,
    aggregate_benchmarks, build_expected_benchmarks, build_tree_maps,
    filter_scores_for_month, initialize_leaf_scores, normalize_score,
)
from benchmarks.utils import refresh_score_trends
from benchmarks.views import model as model_views
from benchmarks.views.model import (
    _rank_transition_model_lines, _wide_scores_and_rank_df, clear_trend_cache,
)


def _toy_tree():
    """Two leaves under one parent, parent under root.

       average_vision (depth 0)
            |-- group_a (depth 1)
                  |-- leaf_x (depth 2)
                  |-- leaf_y (depth 2)
    """
    return pd.DataFrame([
        {'identifier': 'average_vision', 'parent_id': None, 'depth': 0},
        {'identifier': 'group_a', 'parent_id': 'average_vision', 'depth': 1},
        {'identifier': 'leaf_x', 'parent_id': 'group_a', 'depth': 2},
        {'identifier': 'leaf_y', 'parent_id': 'group_a', 'depth': 2},
    ])


def _toy_score_dfs():
    score_df = pd.DataFrame({
        'leaf_x': [0.4, 0.6],
        'leaf_y': [0.8, 0.2],
    }, index=pd.Index([1, 2], name='model_id'))
    timestamp_df = pd.DataFrame({
        'leaf_x': [pd.Timestamp('2024-01-15', tz='UTC'), pd.Timestamp('2024-03-20', tz='UTC')],
        'leaf_y': [pd.Timestamp('2024-02-15', tz='UTC'), pd.Timestamp('2024-03-20', tz='UTC')],
    }, index=pd.Index([1, 2], name='model_id'))
    return score_df, timestamp_df


class TestAggregationHelpers(BaseTestCase):
    """Stand-alone unit tests for the notebook-ported aggregation logic."""

    def test_normalize_score_handles_garbage(self):
        self.assertEqual(normalize_score('X'), 0.0)
        self.assertEqual(normalize_score('nan'), 0.0)
        self.assertEqual(normalize_score(None), 0.0)
        self.assertEqual(normalize_score(0.42), 0.42)

    def test_aggregate_walks_tree_bottom_up(self):
        tree_df = _toy_tree()
        score_df, timestamp_df = _toy_score_dfs()
        parent_child_map, _, _ = build_tree_maps(tree_df)
        cutoff = pd.Timestamp('2024-04-01', tz='UTC')

        filtered, _ = filter_scores_for_month(score_df, timestamp_df, ['leaf_x', 'leaf_y'], cutoff)
        existing = build_expected_benchmarks(
            ['leaf_x', 'leaf_y'], timestamp_df, tree_df,
            parent_child_map, max_depth=2, month_end=cutoff,
        )
        agg = initialize_leaf_scores(score_df, ['leaf_x', 'leaf_y'], filtered)
        agg = aggregate_benchmarks(
            score_df, ['leaf_x', 'leaf_y'], tree_df, parent_child_map,
            max_depth=2, existing_benchmarks=existing,
            filtered_scores=filtered, aggregated=agg,
        )
        # mean(0.4, 0.8) and mean(0.6, 0.2)
        self.assertAlmostEqual(agg[1]['group_a'], 0.6)
        self.assertAlmostEqual(agg[1]['average_vision'], 0.6)
        self.assertAlmostEqual(agg[2]['group_a'], 0.4)
        self.assertAlmostEqual(agg[2]['average_vision'], 0.4)

    def test_filter_scores_excludes_future_timestamps(self):
        tree_df = _toy_tree()
        score_df, timestamp_df = _toy_score_dfs()
        parent_child_map, _, _ = build_tree_maps(tree_df)
        cutoff = pd.Timestamp('2024-02-01', tz='UTC')  # before leaf_y for model 1
        filtered, _ = filter_scores_for_month(score_df, timestamp_df, ['leaf_x', 'leaf_y'], cutoff)
        # model 1 only has leaf_x by Feb; model 2 has nothing yet
        self.assertEqual(set(filtered[1]), {'leaf_x'})
        self.assertEqual(set(filtered[2]), set())

    def test_wide_scores_matches_leaderboard_double_rounding(self):
        """Trend-plot ranking must mirror the leaderboard's *double-rounding*:
        the MV pre-rounds every score to 3dp (mv.sql:1076), then
        ``_rank_models`` rounds to 2dp HALF_UP. A single 2dp HALF_UP on the
        raw float disagrees on values like 0.3849... (lifted to 0.385 by the
        MV's 3dp step, then to 0.39 by the leaderboard's 2dp step -- but
        rounded directly to 0.38 by a one-shot 2dp). Regression: an earlier
        single-pass HALF_UP caused the trend plot to rank effnetb1 at 38
        while the leaderboard had it at 40."""
        df = pd.DataFrame({
            'model_id': [1, 2, 3, 4],
            # raw MMA floats; 0.3849 is the boundary case that desynced ranks
            '2026-05': [0.385, 0.395, 0.380, 0.3849052968509248],
        })
        wide, _rank = _wide_scores_and_rank_df(df, ['2026-05'])
        # 0.3849... -> 3dp 0.385 -> 2dp 0.39  (matches MV path)
        # A one-shot 2dp HALF_UP would have left it at 0.38.
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 4, '2026-05'].iloc[0]), 0.39)
        # Sanity: clean boundary values still round as expected.
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 1, '2026-05'].iloc[0]), 0.39)
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 2, '2026-05'].iloc[0]), 0.40)
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 3, '2026-05'].iloc[0]), 0.38)

    def test_load_score_dfs_drops_null_timestamp_placeholders(self):
        """Multiple Score rows per (model, benchmark_type) can exist (different
        BenchmarkInstance versions); older runs leave NULL-score, NULL-timestamp
        placeholders alongside the real scored row. Regression: a prior
        ``sort_values + keep='last'`` was picking the placeholder over the real
        score and silently dropping it from the aggregate (this caused trend-plot
        scores to diverge from the leaderboard MV for affected models)."""
        fake_rows = [
            # Two NULL placeholders + one real score for (model 1, benchmark X).
            {'model_id': 1, 'benchmark__benchmark_type__identifier': 'leaf_x',
             'score_ceiled': None, 'end_timestamp': None},
            {'model_id': 1, 'benchmark__benchmark_type__identifier': 'leaf_x',
             'score_ceiled': 0.7899, 'end_timestamp': pd.Timestamp('2026-03-25', tz='UTC')},
            {'model_id': 1, 'benchmark__benchmark_type__identifier': 'leaf_x',
             'score_ceiled': None, 'end_timestamp': None},
        ]

        class _FakeQS:
            def filter(self, **_kw):
                return self
            def values(self, *_args):
                return fake_rows

        with patch('benchmarks.management.commands.recompute_score_trends.Score.objects', _FakeQS()):
            score_df, ts_df = _load_score_and_timestamp_dfs('vision')

        self.assertAlmostEqual(float(score_df.loc[1, 'leaf_x']), 0.7899)
        self.assertEqual(ts_df.loc[1, 'leaf_x'], pd.Timestamp('2026-03-25', tz='UTC'))

    def test_per_model_coverage_tracks_scored_leaves_at_month_end(self):
        """``_aggregate_for_month_fast`` must return the exact leaves each model
        was scored on by ``month_end``; this is the input to the per-model
        coverage-completion delta written into ``ModelMonthlyAggregate``."""
        tree_df = _toy_tree()
        score_df, timestamp_df = _toy_score_dfs()
        parent_child_map, _, _ = build_tree_maps(tree_df)
        depth_groups = _depth_groups(tree_df)
        # By 2024-02-28 model 1 has been scored on leaf_x (Jan) and leaf_y (Feb);
        # model 2 has nothing yet (its timestamps are March).
        month_end = pd.Timestamp('2024-02-29', tz='UTC')
        _, leaf_set, coverage = _aggregate_for_month_fast(
            score_df, timestamp_df, ['leaf_x', 'leaf_y'], parent_child_map,
            depth_groups, max_depth=2, month_end=month_end, agg_root='average_vision',
        )
        self.assertEqual(coverage[1], frozenset({'leaf_x', 'leaf_y'}))
        self.assertEqual(coverage[2], frozenset())
        # leaf_set is the *global* set (anyone scored), so leaf_y is in it.
        self.assertEqual(leaf_set, {'leaf_x', 'leaf_y'})

    def test_build_expected_propagates_leaves_to_root(self):
        tree_df = _toy_tree()
        _, timestamp_df = _toy_score_dfs()
        parent_child_map, _, _ = build_tree_maps(tree_df)
        cutoff = pd.Timestamp('2024-04-01', tz='UTC')
        existing = build_expected_benchmarks(
            ['leaf_x', 'leaf_y'], timestamp_df, tree_df,
            parent_child_map, max_depth=2, month_end=cutoff,
        )
        self.assertIn('leaf_x', existing)
        self.assertIn('group_a', existing)
        self.assertIn('average_vision', existing)


class TestRankPrivacy(BaseTestCase):
    """``_rank_transition_model_lines`` must never reference IDs not in the
    supplied wide_scores frame -- which is how the view enforces public-only."""

    def test_rank_lines_only_reference_supplied_models(self):
        wide_scores = pd.DataFrame({
            'model_id': [1, 2, 3],
            '2024-01': [0.5, 0.6, 0.4],
            '2024-02': [0.5, 0.4, 0.6],  # model 2 dropped, model 3 climbed
        })
        _, rank_df = _wide_scores_and_rank_df(wide_scores, ['2024-01', '2024-02'])
        # focal model 1 went from rank 2 -> rank 2 (tie hands)
        # use focal model 2: rank 1 -> rank 3 (worsened)
        lines = _rank_transition_model_lines(
            model_id=2, ym_prev='2024-01', ym_curr='2024-02',
            rank1=1, rank2=3, rank_df=rank_df, wide_scores=wide_scores,
        )
        joined = '\n'.join(lines)
        # Must reference other supplied models only, never an ID outside the frame.
        self.assertNotIn('#99', joined)
        self.assertTrue('#1' in joined or '#3' in joined)  # at least one named

    def test_clear_trend_cache_drops_all_entries(self):
        """``recompute_score_trends`` relies on this to bust the in-process snapshot
        after a same-month rerun (e.g. May 17 score updates) -- regressing this
        means workers keep serving the pre-recompute plot until June begins."""
        model_views._TREND_CACHE[('public_wide', 'vision', '2026-05')] = 'sentinel'
        model_views._TREND_CACHE[('names', 'vision', '2026-05')] = 'sentinel'
        clear_trend_cache()
        self.assertEqual(model_views._TREND_CACHE, {})

    def test_headline_includes_coverage_completion_bit(self):
        """When ``coverage_added_count`` is supplied, the ``Why this changed:``
        headline must mention coverage completion -- this is the user-visible
        signal that the model's aggregate moved because it newly got scored on
        existing benchmarks (not because of new global benchmarks)."""
        wide_scores = pd.DataFrame({
            'model_id': [1, 2, 3],
            '2024-01': [0.5, 0.6, 0.4],
            '2024-02': [0.5, 0.4, 0.6],
        })
        _, rank_df = _wide_scores_and_rank_df(wide_scores, ['2024-01', '2024-02'])
        lines = _rank_transition_model_lines(
            model_id=2, ym_prev='2024-01', ym_curr='2024-02',
            rank1=1, rank2=3, rank_df=rank_df, wide_scores=wide_scores,
            coverage_added_count=2,
        )
        headline = lines[0] if lines else ''
        self.assertTrue(headline.startswith('Why this changed:'), headline)
        self.assertIn('newly scored on 2 existing benchmark(s)', headline)


class TestRefreshEndpoint(BaseTestCase):
    """Auth, mode parsing, and lock contention. ``call_command`` is patched so
    no real recompute runs."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        # Reset lock between tests in case a prior test left it acquired.
        from benchmarks import utils
        try:
            utils._score_trends_lock.release()
        except RuntimeError:
            pass

    def _post(self, **params):
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        return self.factory.post(f'/refresh_score_trends/vision/?{qs}')

    def test_rejects_invalid_token(self):
        resp = refresh_score_trends(self._post(token='wrong'), domain='vision')
        self.assertEqual(resp.status_code, 403)

    def test_rejects_invalid_mode(self):
        resp = refresh_score_trends(
            self._post(token=settings.CACHE_REFRESH_TOKEN, mode='nonsense'),
            domain='vision',
        )
        self.assertEqual(resp.status_code, 400)

    def test_starts_in_background_with_valid_token(self):
        with patch('django.core.management.call_command') as mock_cc:
            # Block the worker thread on the lock by holding it, so we can
            # observe the 202 response before the mock is invoked.
            resp = refresh_score_trends(
                self._post(token=settings.CACHE_REFRESH_TOKEN, mode='latest'),
                domain='vision',
            )
            self.assertEqual(resp.status_code, 202)
            body = json.loads(resp.content)
            self.assertEqual(body['status'], 'started')
            self.assertEqual(body['mode'], 'latest')
            # Wait for the daemon thread to finish.
            from benchmarks import utils
            with utils._score_trends_lock:  # blocks until worker releases
                pass
            mock_cc.assert_called_once()
            args, kwargs = mock_cc.call_args
            self.assertEqual(args[0], 'recompute_score_trends')
            self.assertEqual(kwargs.get('domain'), 'vision')
            self.assertEqual(kwargs.get('mode'), 'latest')

    def test_concurrent_trigger_returns_409(self):
        from benchmarks import utils
        utils._score_trends_lock.acquire()
        try:
            resp = refresh_score_trends(
                self._post(token=settings.CACHE_REFRESH_TOKEN, mode='latest'),
                domain='vision',
            )
            self.assertEqual(resp.status_code, 409)
        finally:
            utils._score_trends_lock.release()
