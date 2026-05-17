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
    _aggregate_for_month_fast, _depth_groups, _load_score_long,
    aggregate_benchmarks, build_expected_benchmarks, build_tree_maps,
    filter_scores_for_month, initialize_leaf_scores, normalize_score,
)
from benchmarks.utils import refresh_score_trends
from benchmarks.views import model_trends as model_views
from benchmarks.views.model_trends import (
    clear_trend_cache, load_and_build_comparison_trend,
    rank_transition_model_lines, wide_scores_and_rank_df,
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
        """Trend ranking must mirror the leaderboard's two-pass HALF_UP rounding
        (3dp in the MV, then 2dp in ``_rank_models``). A one-shot 2dp on the raw
        float would disagree on .xx5 boundary values like 0.3849..."""
        df = pd.DataFrame({
            'model_id': [1, 2, 3, 4],
            '2026-05': [0.385, 0.395, 0.380, 0.3849052968509248],
        })
        wide, _rank = wide_scores_and_rank_df(df, ['2026-05'])
        # 0.3849... -> 3dp 0.385 -> 2dp 0.39 (matches MV); one-shot 2dp gives 0.38.
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 4, '2026-05'].iloc[0]), 0.39)
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 1, '2026-05'].iloc[0]), 0.39)
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 2, '2026-05'].iloc[0]), 0.40)
        self.assertAlmostEqual(float(wide.loc[wide.model_id == 3, '2026-05'].iloc[0]), 0.38)

    def test_load_score_long_drops_null_score_or_timestamp(self):
        fake_rows = [
            {'model_id': 1, 'benchmark__benchmark_type__identifier': 'leaf_x',
             'score_ceiled': None, 'end_timestamp': None},
            {'model_id': 1, 'benchmark__benchmark_type__identifier': 'leaf_x',
             'score_ceiled': 0.7899, 'end_timestamp': pd.Timestamp('2026-03-25', tz='UTC')},
            {'model_id': 1, 'benchmark__benchmark_type__identifier': 'leaf_x',
             'score_ceiled': None, 'end_timestamp': pd.Timestamp('2026-04-01', tz='UTC')},
        ]

        class _FakeQS:
            def filter(self, **_kw):
                # Mirror the real queryset's NOT-NULL guards so we exercise the same path.
                return _FakeQS()
            def values(self, *_args):
                return [r for r in fake_rows
                        if r['score_ceiled'] is not None and r['end_timestamp'] is not None]

        with patch('benchmarks.management.commands.recompute_score_trends.Score.objects', _FakeQS()):
            long_df = _load_score_long('vision')

        self.assertEqual(len(long_df), 1)
        self.assertAlmostEqual(float(long_df.iloc[0]['score_ceiled']), 0.7899)

    def test_per_model_coverage_tracks_scored_leaves_at_month_end(self):
        """``coverage`` must list exactly the leaves each model was scored on
        by ``month_end``; this feeds the per-model coverage-completion delta."""
        tree_df = _toy_tree()
        parent_child_map, _, _ = build_tree_maps(tree_df)
        depth_groups = _depth_groups(tree_df)
        long_df = pd.DataFrame([
            # By 2024-02-28 model 1 has been scored on leaf_x (Jan) and leaf_y (Feb);
            # model 2 has nothing yet (its timestamps are March).
            {'model_id': 1, 'benchmark': 'leaf_x', 'score_ceiled': 0.4,
             'end_timestamp': pd.Timestamp('2024-01-15', tz='UTC')},
            {'model_id': 1, 'benchmark': 'leaf_y', 'score_ceiled': 0.8,
             'end_timestamp': pd.Timestamp('2024-02-15', tz='UTC')},
            {'model_id': 2, 'benchmark': 'leaf_x', 'score_ceiled': 0.6,
             'end_timestamp': pd.Timestamp('2024-03-20', tz='UTC')},
            {'model_id': 2, 'benchmark': 'leaf_y', 'score_ceiled': 0.2,
             'end_timestamp': pd.Timestamp('2024-03-20', tz='UTC')},
        ])
        month_end = pd.Timestamp('2024-02-29', tz='UTC')
        _, leaf_set, coverage = _aggregate_for_month_fast(
            long_df, [1, 2], parent_child_map,
            depth_groups, max_depth=2, month_end=month_end, agg_root='average_vision',
        )
        self.assertEqual(coverage[1], frozenset({'leaf_x', 'leaf_y'}))
        self.assertEqual(coverage[2], frozenset())
        # leaf_set is the *global* set (anyone scored), so leaf_y is in it.
        self.assertEqual(leaf_set, {'leaf_x', 'leaf_y'})

    def test_per_month_picks_latest_score_within_window(self):
        """A benchmark re-scored after ``month_end`` must still surface its
        earlier value at that month; otherwise leaves silently drop out."""
        tree_df = _toy_tree()
        parent_child_map, _, _ = build_tree_maps(tree_df)
        depth_groups = _depth_groups(tree_df)
        long_df = pd.DataFrame([
            {'model_id': 1, 'benchmark': 'leaf_x', 'score_ceiled': 0.9,
             'end_timestamp': pd.Timestamp('2024-01-10', tz='UTC')},
            # Replacement AFTER the month_end we test -- must NOT win.
            {'model_id': 1, 'benchmark': 'leaf_x', 'score_ceiled': 0.2,
             'end_timestamp': pd.Timestamp('2024-04-10', tz='UTC')},
            {'model_id': 1, 'benchmark': 'leaf_y', 'score_ceiled': 0.5,
             'end_timestamp': pd.Timestamp('2024-01-15', tz='UTC')},
        ])
        month_end = pd.Timestamp('2024-02-29', tz='UTC')
        scores, leaf_set, coverage = _aggregate_for_month_fast(
            long_df, [1], parent_child_map,
            depth_groups, max_depth=2, month_end=month_end, agg_root='average_vision',
        )
        # average_vision should use leaf_x's January value 0.9, so (0.9 + 0.5)/2.
        self.assertEqual(coverage[1], frozenset({'leaf_x', 'leaf_y'}))
        self.assertEqual(leaf_set, {'leaf_x', 'leaf_y'})
        self.assertAlmostEqual(scores[1], 0.7)

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


class TestRankNarrative(BaseTestCase):
    """Count-only, third-person rank narrative."""

    @staticmethod
    def _rank_df(rows, cols):
        _, rank_df = wide_scores_and_rank_df(pd.DataFrame(rows), cols)
        return rank_df

    def test_rank_lines_summarise_counts_without_naming_models(self):
        rank_df = self._rank_df(
            {'model_id': [1, 2, 3], '2024-01': [0.5, 0.6, 0.4], '2024-02': [0.5, 0.4, 0.6]},
            ['2024-01', '2024-02'],
        )
        # Focal model 2 went rank 1 -> 3; 2 other models beat it.
        lines = rank_transition_model_lines(
            model_id=2, ym_prev='2024-01', ym_curr='2024-02',
            rank1=1, rank2=3, rank_df=rank_df,
        )
        joined = '\n'.join(lines)
        for needle in ('#1', '#3', '#99'):
            self.assertNotIn(needle, joined)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('Why this changed:'), lines[0])
        self.assertIn('2 model(s) beat this model', lines[0])
        self.assertNotIn(' you ', ' ' + lines[0].lower() + ' ')

    def test_rank_lines_third_person_when_focal_improved(self):
        rank_df = self._rank_df(
            {'model_id': [1, 2, 3], '2024-01': [0.5, 0.4, 0.6], '2024-02': [0.4, 0.6, 0.5]},
            ['2024-01', '2024-02'],
        )
        lines = rank_transition_model_lines(
            model_id=2, ym_prev='2024-01', ym_curr='2024-02',
            rank1=3, rank2=1, rank_df=rank_df,
        )
        self.assertTrue(lines and 'this model passed' in lines[0], lines)

    def test_clear_trend_cache_drops_all_entries(self):
        model_views._TREND_CACHE[('public_wide', 'vision', '2026-05')] = 'sentinel'
        model_views._TREND_CACHE[('names', 'vision', '2026-05')] = 'sentinel'
        clear_trend_cache()
        self.assertEqual(model_views._TREND_CACHE, {})

    def test_headline_includes_coverage_completion_bit(self):
        rank_df = self._rank_df(
            {'model_id': [1, 2, 3], '2024-01': [0.5, 0.6, 0.4], '2024-02': [0.5, 0.4, 0.6]},
            ['2024-01', '2024-02'],
        )
        lines = rank_transition_model_lines(
            model_id=2, ym_prev='2024-01', ym_curr='2024-02',
            rank1=1, rank2=3, rank_df=rank_df,
            coverage_added_count=2,
        )
        headline = lines[0] if lines else ''
        self.assertTrue(headline.startswith('Why this changed:'), headline)
        self.assertIn('this model newly scored on 2 existing benchmark(s)', headline)


class TestComparisonTrendNarrative(BaseTestCase):
    """Hover narrative + default headline for the compare-page two-line trend."""

    def _meta(self, kind, dates, va, vb, name_a='alpha', name_b='beta', **extras):
        from benchmarks.views.model_trends import _build_comparison_trend_meta
        return _build_comparison_trend_meta(dates, kind, va, vb, name_a, name_b, **extras)

    def test_score_leader_call_out(self):
        meta = self._meta('score', ['2026-04-30', '2026-05-31'],
                          [0.50, 0.55], [0.30, 0.40])
        lines = meta['points'][1]['lines']
        self.assertIn('alpha = 0.5500, beta = 0.4000.', lines[0])
        self.assertIn('alpha leads by 0.1500', lines[1])

    def test_score_tied_says_tied(self):
        meta = self._meta('score', ['2026-05-31'], [0.42], [0.42])
        lines = meta['points'][0]['lines']
        self.assertIn('alpha = 0.4200, beta = 0.4200.', lines[0])
        self.assertIn('tied at this month', lines[1])

    def test_handles_one_missing(self):
        meta = self._meta('score', ['2026-05-31'], [None], [0.42])
        lines = meta['points'][0]['lines']
        self.assertIn('alpha had no data', lines[0])
        self.assertIn('beta scored 0.4200', lines[0])

    def test_rank_smaller_is_better(self):
        meta = self._meta('rank', ['2026-05-31'], [3], [10])
        lines = meta['points'][0]['lines']
        self.assertIn('alpha = rank 3, beta = rank 10.', lines[0])
        self.assertIn('alpha is 7 position(s) ahead of beta', lines[1])

    def test_default_headline_summarises_endpoints(self):
        meta = self._meta('score', ['2026-04-30', '2026-05-31'],
                          [0.40, 0.50], [0.30, 0.45])
        defaults = meta['defaultLines']
        self.assertIn('alpha: 0.4000 → 0.5000 (+0.1000).', defaults)
        self.assertIn('beta: 0.3000 → 0.4500 (+0.1500).', defaults)

    def test_score_hover_lists_per_model_coverage(self):
        meta = self._meta(
            'score', ['2026-04-30', '2026-05-31'],
            [0.40, 0.50], [0.30, 0.45],
            coverage_a={'2026-05': ['Foo.IT', 'Foo.V1']},
            coverage_b={'2026-05': ['Bar.IT']},
        )
        lines = meta['points'][1]['lines']
        self.assertIn('alpha newly scored on 2 benchmark(s) this month:', lines)
        self.assertIn('  • Foo.IT', lines)
        self.assertIn('  • Foo.V1', lines)
        self.assertIn('beta newly scored on 1 benchmark(s) this month:', lines)
        self.assertIn('  • Bar.IT', lines)

    def test_score_hover_states_no_coverage_change_when_empty(self):
        meta = self._meta(
            'score', ['2026-05-31'], [0.40], [0.42],
            coverage_a={}, coverage_b={},
        )
        lines = meta['points'][0]['lines']
        self.assertIn('Neither model added new benchmark scores this month.', lines)

    def test_rank_hover_summarises_global_churn(self):
        meta = self._meta(
            'rank', ['2026-04-30', '2026-05-31'], [3, 5], [10, 4],
            new_leaf_counts={'2026-05': 7},
            new_model_counts={'2026-05': 12},
        )
        lines = meta['points'][1]['lines']
        churn_line = next((l for l in lines if l.startswith('This month:')), '')
        self.assertIn('7 new leaf benchmark(s) counted globally', churn_line)
        self.assertIn('12 new model(s) entered the leaderboard', churn_line)

    def test_rank_hover_says_no_churn_when_counts_zero(self):
        meta = self._meta(
            'rank', ['2026-05-31'], [3], [10],
            new_leaf_counts={}, new_model_counts={},
        )
        lines = meta['points'][0]['lines']
        self.assertIn('No new benchmarks or models added this month.', lines)


class TestComparisonTrendEndpoint(BaseTestCase):
    """``compare.trend_pair`` JSON endpoint."""

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def _get(self, **params):
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        return self.factory.get(f'/vision/compare/trend_pair/?{qs}')

    def test_rejects_non_integer_ids(self):
        from benchmarks.views.compare import trend_pair
        resp = trend_pair(self._get(mid_a='foo', mid_b='42'), domain='vision')
        self.assertEqual(resp.status_code, 400)

    def test_same_model_returns_null_pair_without_aggregator(self):
        from benchmarks.views.compare import trend_pair
        with patch('benchmarks.views.compare.load_and_build_comparison_trend') as agg:
            resp = trend_pair(self._get(mid_a='5', mid_b='5'), domain='vision')
            self.assertEqual(resp.status_code, 200)
            body = json.loads(resp.content)
            self.assertEqual(body, {'score': None, 'rank': None})
            agg.assert_not_called()


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
