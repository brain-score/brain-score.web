"""Recompute monthly score-trend aggregates and benchmark edges.

The vectorized ``_aggregate_for_month_fast`` below is algorithmically
equivalent to the per-row notebook helpers in
``analytics/per-model_wayback/aggregate_scores.ipynb`` (filter -> build
expected -> initialize -> aggregate), reorganized into pandas matrix ops so
it scales past a few thousand models. The DB loaders below replace the
notebook's CSV inputs with live queries; visibility is applied at the
loader so private benchmarks/scores never enter the aggregation.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from benchmarks.models import (
    BenchmarkType, ModelMonthlyAggregate, MonthBenchmarkEdge, Score,
)

logger = logging.getLogger(__name__)


def build_parent_child_map(tree_df):
    parent_child_map = defaultdict(list)
    for _, row in tree_df.iterrows():
        parent_id = row['parent_id'] if pd.notna(row['parent_id']) else None
        if parent_id:
            parent_child_map[parent_id].append(row['identifier'])
    return parent_child_map

def _load_tree_df(domain):
    types = list(BenchmarkType.objects.filter(domain=domain, visible=True))
    parent_of = {bt.identifier: bt.parent_id for bt in types}
    depth = {}

    def _depth(ident):
        if ident in depth:
            return depth[ident]
        p = parent_of.get(ident)
        if p is None or p not in parent_of:
            depth[ident] = 0
        else:
            depth[ident] = _depth(p) + 1
        return depth[ident]

    for ident in parent_of:
        _depth(ident)
    rows = [{'identifier': i, 'parent_id': parent_of[i], 'depth': depth[i]} for i in parent_of]
    return pd.DataFrame(rows)


def _load_score_long(domain):
    """Long-format Score rows: one row per measurement. Multiple rows per
    ``(model_id, benchmark)`` are kept so ``_aggregate_for_month_fast`` can
    pick the latest score with ``end_timestamp <= month_end`` -- a benchmark
    re-scored after a past month's end must still surface its earlier value
    in that month."""
    qs = (Score.objects
          .filter(benchmark__benchmark_type__domain=domain,
                  benchmark__benchmark_type__visible=True,
                  end_timestamp__isnull=False,
                  score_ceiled__isnull=False)
          .values('model_id',
                  'benchmark__benchmark_type__identifier',
                  'score_ceiled',
                  'end_timestamp'))
    df = pd.DataFrame(list(qs))
    if df.empty:
        return df
    df.rename(columns={'benchmark__benchmark_type__identifier': 'benchmark'}, inplace=True)
    df['end_timestamp'] = pd.to_datetime(df['end_timestamp'], errors='coerce', utc=True)
    return df.dropna(subset=['end_timestamp'])


# ---------------------------------------------------------------------
# Month list resolution
# ---------------------------------------------------------------------

def _month_floor(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_end_utc(month_str):
    return (pd.Timestamp(month_str + '-01', tz='UTC') + pd.offsets.MonthEnd(0)).to_pydatetime()


def _month_iter(start_ym, end_ym):
    cur = pd.Timestamp(start_ym + '-01')
    end = pd.Timestamp(end_ym + '-01')
    out = []
    while cur <= end:
        out.append(cur.strftime('%Y-%m'))
        cur = cur + pd.offsets.MonthBegin(1)
    return out


def _resolve_months(mode, since, domain):
    today = datetime.now(timezone.utc)
    curr_ym = today.strftime('%Y-%m')
    prev_dt = _month_floor(today) - timedelta(days=1)
    prev_ym = prev_dt.strftime('%Y-%m')
    if mode == 'latest':
        return [prev_ym, curr_ym] if prev_ym != curr_ym else [curr_ym]
    if since:
        return _month_iter(since, curr_ym)
    first = (Score.objects
             .filter(benchmark__benchmark_type__domain=domain,
                     benchmark__benchmark_type__visible=True,
                     end_timestamp__isnull=False)
             .order_by('end_timestamp')
             .values_list('end_timestamp', flat=True)
             .first())
    if not first:
        return []
    return _month_iter(first.strftime('%Y-%m'), curr_ym)


def _depth_groups(tree_df):
    return tree_df.groupby('depth')['identifier'].apply(list).to_dict()


def _aggregate_for_month_fast(
    long_df, all_model_ids, parent_child_map,
    depth_groups, max_depth, month_end, agg_root,
):
    """Returns ``({model_id: agg_root_score}, leaf_set, per_model_coverage)`` for
    the month ending at ``month_end``. Missing models in either dict are filled
    with ``0.0`` / ``frozenset()`` so downstream callers see consistent keys."""
    empty_scores = {mid: 0.0 for mid in all_model_ids}
    empty_cov = {mid: frozenset() for mid in all_model_ids}
    if long_df is None or long_df.empty:
        return empty_scores, set(), empty_cov

    sub = long_df[long_df['end_timestamp'] <= pd.Timestamp(month_end)]
    if sub.empty:
        return empty_scores, set(), empty_cov

    sub = sub.sort_values('end_timestamp').drop_duplicates(['model_id', 'benchmark'], keep='last')
    score_df = sub.pivot(index='model_id', columns='benchmark', values='score_ceiled')
    benchmark_cols = list(score_df.columns)

    leaves_present = score_df.notna().any(axis=0)
    existing = {col for col in benchmark_cols if bool(leaves_present.get(col, False))}
    for depth in range(max_depth, -1, -1):
        for ident in depth_groups.get(depth, []):
            if ident in existing:
                continue
            for child in parent_child_map.get(ident, []):
                if child in existing:
                    existing.add(ident)
                    break

    leaf_existing = [c for c in benchmark_cols if c in existing]
    if leaf_existing:
        agg_df = score_df[leaf_existing].copy()
        leaf_mask = score_df[leaf_existing].notna()
        per_model_coverage = {
            mid: frozenset(leaf_mask.columns[leaf_mask.loc[mid].to_numpy()])
            for mid in leaf_mask.index
        }
    else:
        agg_df = pd.DataFrame(index=score_df.index)
        per_model_coverage = {mid: frozenset() for mid in score_df.index}

    for depth in range(max_depth, -1, -1):
        for ident in depth_groups.get(depth, []):
            if ident not in existing or ident in benchmark_cols:
                continue
            children = [c for c in parent_child_map.get(ident, []) if c in existing]
            children = [c for c in children if c in agg_df.columns]
            if not children:
                continue
            agg_df[ident] = agg_df[children].fillna(0).mean(axis=1)

    leaf_set = {b for b in existing if b in benchmark_cols}
    out_scores = dict(empty_scores)
    out_coverage = dict(empty_cov)
    if agg_root in agg_df.columns:
        for mid, val in agg_df[agg_root].fillna(0.0).items():
            out_scores[mid] = float(val)
    for mid, cov in per_model_coverage.items():
        out_coverage[mid] = cov
    return out_scores, leaf_set, out_coverage


# ---------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------

class Command(BaseCommand):
    help = "Recompute monthly score-trend aggregates and benchmark edges."

    def add_arguments(self, parser):
        parser.add_argument('--domain', default='vision')
        parser.add_argument('--mode', choices=['latest', 'backfill'], default='latest')
        parser.add_argument('--since', default=None,
                            help='YYYY-MM. With mode=backfill, recompute from this month forward.')

    def handle(self, *args, domain, mode, since, **opts):
        months = _resolve_months(mode, since, domain)
        if not months:
            self.stdout.write(self.style.WARNING(f'No scores for domain={domain}, nothing to do.'))
            return
        self.stdout.write(
            f'Recomputing score trends domain={domain} mode={mode} '
            f'months={months[0]}..{months[-1]} (n={len(months)})'
        )
        logger.info(
            'Recomputing score trends domain=%s mode=%s months=%s..%s (n=%d)',
            domain, mode, months[0], months[-1], len(months),
        )

        self.stdout.write('Loading tree and scores from DB...', ending=' ')
        self.stdout.flush()
        tree_df = _load_tree_df(domain)
        long_df = _load_score_long(domain)
        if long_df.empty:
            self.stdout.write(self.style.WARNING(f'\nNo scores for domain={domain}.'))
            return
        all_model_ids = sorted(long_df['model_id'].unique().tolist())
        parent_child_map = build_parent_child_map(tree_df)
        depth_groups = _depth_groups(tree_df)
        max_depth = int(tree_df['depth'].max())
        agg_root = f'average_{domain}'
        self.stdout.write(
            f'loaded ({len(all_model_ids)} models, {long_df["benchmark"].nunique()} leaf benchmarks, '
            f'{len(long_df)} score rows, tree depth={max_depth}).'
        )

        leaf_set_by_month = {}
        coverage_by_month = {}

        # Pre-compute the boundary month (one before months[0]) so the very
        # first iteration has a prior-month coverage + global leaf set to diff
        # against. Without this, mode='latest' would always emit empty deltas.
        boundary = (pd.Timestamp(months[0] + '-01') - pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        _, b_leaves, b_coverage = _aggregate_for_month_fast(
            long_df, all_model_ids, parent_child_map,
            depth_groups, max_depth, _month_end_utc(boundary), agg_root,
        )
        leaf_set_by_month[boundary] = b_leaves
        coverage_by_month[boundary] = b_coverage
        prev_month_for_coverage = boundary

        for idx, month_str in enumerate(months, start=1):
            t0 = datetime.now(timezone.utc)
            month_end = _month_end_utc(month_str)
            scores_by_model, leaf_set, coverage = _aggregate_for_month_fast(
                long_df, all_model_ids, parent_child_map,
                depth_groups, max_depth, month_end, agg_root,
            )
            leaf_set_by_month[month_str] = leaf_set
            coverage_by_month[month_str] = coverage

            prev_coverage = coverage_by_month.get(prev_month_for_coverage, {})
            prev_global_leaves = leaf_set_by_month.get(prev_month_for_coverage, set())

            with transaction.atomic():
                ModelMonthlyAggregate.objects.filter(domain=domain, month=month_str).delete()
                rows = []
                for mid, val in scores_by_model.items():
                    delta = sorted(
                        (coverage.get(mid, frozenset()) - prev_coverage.get(mid, frozenset()))
                        & prev_global_leaves
                    )
                    rows.append(ModelMonthlyAggregate(
                        model_id=mid, domain=domain, month=month_str,
                        score=(0.0 if pd.isna(val) else float(val)),
                        coverage_leaves_added_vs_prev=delta,
                    ))
                ModelMonthlyAggregate.objects.bulk_create(rows, batch_size=2000)
            elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
            self.stdout.write(
                f'  [{idx}/{len(months)}] {month_str}: wrote {len(scores_by_model)} rows in {elapsed:.2f}s'
            )
            self.stdout.flush()
            logger.info('  month %s: wrote %d aggregate rows in %.2fs', month_str, len(scores_by_model), elapsed)
            prev_month_for_coverage = month_str

        ordered = [boundary] + months
        self.stdout.write(f'Writing {len(ordered) - 1} month-edge rows...', ending=' ')
        self.stdout.flush()
        with transaction.atomic():
            for i in range(1, len(ordered)):
                m_prev, m_curr = ordered[i - 1], ordered[i]
                added = sorted(leaf_set_by_month[m_curr] - leaf_set_by_month[m_prev])
                MonthBenchmarkEdge.objects.update_or_create(
                    domain=domain, month_prev=m_prev, month_curr=m_curr,
                    defaults={'leaf_benchmarks': added},
                )
        self.stdout.write('done.')

        # Same-month reruns don't change ``max(month)``, so the snapshot cache
        # wouldn't naturally invalidate without an explicit bust.
        from benchmarks.views.model_trends import clear_trend_cache
        clear_trend_cache()

        self.stdout.write(self.style.SUCCESS(
            f'Recompute complete for domain={domain}: {len(months)} month(s).'
        ))
