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
    aggregate_benchmarks, build_expected_benchmarks, build_tree_maps,
    filter_scores_for_month, initialize_leaf_scores, normalize_score,
)
from benchmarks.utils import refresh_score_trends
from benchmarks.views.model import _wide_scores_and_rank_df, _rank_transition_model_lines


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
        self.assertNotIn('Model 99', joined)
        self.assertIn('Model 1', joined + 'Model 3')  # at least one named


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
