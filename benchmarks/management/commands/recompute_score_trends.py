"""Recompute monthly score-trend aggregates and benchmark edges.

Aggregation logic ported verbatim from
``analytics/per-model_wayback/aggregate_scores.ipynb``. Only the data loader
was rewritten to read from the database (Score / BenchmarkType) instead of
the notebook's CSV inputs.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from benchmarks.models import (
    BenchmarkType, ModelMonthlyAggregate, MonthBenchmarkEdge, Score,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Notebook-ported aggregation helpers (do not edit without updating the
# source notebook -- they are intentionally byte-identical).
# ---------------------------------------------------------------------

def normalize_score(val):
    if pd.isna(val) or str(val).strip().lower() in ['x', 'nan', '']:
        return 0.0
    try:
        score = float(val)
        return 0.0 if np.isnan(score) else score
    except (ValueError, TypeError):
        return 0.0


def build_tree_maps(tree_df):
    parent_child_map = defaultdict(list)
    child_parent_map = {}
    identifier_to_depth = {}
    for _, row in tree_df.iterrows():
        identifier = row['identifier']
        parent_id = row['parent_id'] if pd.notna(row['parent_id']) else None
        depth = row['depth']
        identifier_to_depth[identifier] = depth
        if parent_id:
            parent_child_map[parent_id].append(identifier)
            child_parent_map[identifier] = parent_id
    return parent_child_map, child_parent_map, identifier_to_depth


def filter_scores_for_month(score_df, timestamp_df, benchmark_cols, month_end):
    filtered_scores = {model_id: {} for model_id in score_df.index}
    filtered_timestamps = {model_id: {} for model_id in score_df.index}
    for model_id in score_df.index:
        for benchmark in benchmark_cols:
            if benchmark in timestamp_df.columns:
                timestamp = pd.to_datetime(timestamp_df.loc[model_id, benchmark], errors='coerce', utc=True)
                if pd.notna(timestamp) and timestamp <= month_end:
                    filtered_scores[model_id][benchmark] = score_df.loc[model_id, benchmark]
                    filtered_timestamps[model_id][benchmark] = timestamp
    return filtered_scores, filtered_timestamps


def build_expected_benchmarks(benchmark_cols, timestamp_df_full_indexed, tree_df,
                              parent_child_map, max_depth, month_end):
    existing_benchmarks = set()
    for benchmark in benchmark_cols:
        if benchmark in timestamp_df_full_indexed.columns:
            for model_id in timestamp_df_full_indexed.index:
                timestamp = pd.to_datetime(timestamp_df_full_indexed.loc[model_id, benchmark], errors='coerce', utc=True)
                if pd.notna(timestamp) and timestamp <= month_end:
                    existing_benchmarks.add(benchmark)
                    break
    for depth in range(max_depth, -1, -1):
        benchmarks_at_depth = [
            row['identifier'] for _, row in tree_df.iterrows()
            if row['depth'] == depth and row['identifier'] not in existing_benchmarks
        ]
        for benchmark in benchmarks_at_depth:
            children = parent_child_map.get(benchmark, [])
            if any(child in existing_benchmarks for child in children):
                existing_benchmarks.add(benchmark)
    return existing_benchmarks


def initialize_leaf_scores(score_df, benchmark_cols, filtered_scores):
    aggregated = {}
    for model_id in score_df.index:
        aggregated[model_id] = {}
        for benchmark in benchmark_cols:
            if benchmark in filtered_scores[model_id]:
                aggregated[model_id][benchmark] = normalize_score(filtered_scores[model_id][benchmark])
    return aggregated


def aggregate_benchmarks(score_df, benchmark_cols, tree_df, parent_child_map,
                         max_depth, existing_benchmarks, filtered_scores, aggregated):
    for depth in range(max_depth, -1, -1):
        benchmarks_at_depth = [
            row['identifier'] for _, row in tree_df.iterrows()
            if row['depth'] == depth and row['identifier'] in existing_benchmarks
        ]
        for benchmark in benchmarks_at_depth:
            if benchmark in benchmark_cols:
                continue
            children = parent_child_map.get(benchmark, [])
            expected_children = [c for c in children if c in existing_benchmarks]
            if not expected_children:
                continue
            for model_id in score_df.index:
                child_scores = []
                for child in expected_children:
                    model_agg = aggregated.get(model_id, {})
                    model_filtered = filtered_scores.get(model_id, {})
                    child_score = (model_agg.get(child) if child in model_agg
                                   else model_filtered.get(child) if child in model_filtered
                                   else 0.0)
                    child_scores.append(normalize_score(child_score))
                if model_id not in aggregated:
                    aggregated[model_id] = {}
                aggregated[model_id][benchmark] = sum(child_scores) / len(child_scores)
    return aggregated


# ---------------------------------------------------------------------
# DB loaders -- replace the notebook's CSV inputs with live DB queries.
# Visibility filter is applied here so private benchmarks/scores never
# enter the aggregation.
# ---------------------------------------------------------------------

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


def _load_score_and_timestamp_dfs(domain):
    qs = (Score.objects
          .filter(benchmark__benchmark_type__domain=domain,
                  benchmark__benchmark_type__visible=True)
          .values('model_id',
                  'benchmark__benchmark_type__identifier',
                  'score_ceiled',
                  'end_timestamp'))
    df = pd.DataFrame(list(qs))
    if df.empty:
        empty = pd.DataFrame().set_index(pd.Index([], name='model_id'))
        return empty, empty
    df.rename(columns={'benchmark__benchmark_type__identifier': 'benchmark'}, inplace=True)
    df = df.sort_values('end_timestamp').drop_duplicates(['model_id', 'benchmark'], keep='last')
    score_df = df.pivot(index='model_id', columns='benchmark', values='score_ceiled')
    timestamp_df = df.pivot(index='model_id', columns='benchmark', values='end_timestamp')
    for col in timestamp_df.columns:
        timestamp_df[col] = pd.to_datetime(timestamp_df[col], errors='coerce', utc=True)
    return score_df, timestamp_df


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


# ---------------------------------------------------------------------
# Vectorized per-month aggregation. Algorithmically equivalent to the
# notebook helpers above (filter -> build_expected -> initialize ->
# aggregate); reorganized into pandas matrix ops so it scales past a few
# thousand models. The notebook helpers remain the algorithmic reference.
# ---------------------------------------------------------------------

def _depth_groups(tree_df):
    return tree_df.groupby('depth')['identifier'].apply(list).to_dict()


def _aggregate_for_month_fast(
    score_df, timestamp_df, benchmark_cols, parent_child_map,
    depth_groups, max_depth, month_end, agg_root,
):
    """Returns ({model_id: agg_root_score}, leaf_set_present_at_month)."""
    cols = [c for c in benchmark_cols if c in timestamp_df.columns]
    if not cols:
        return {mid: 0.0 for mid in score_df.index}, set()

    valid_mask = timestamp_df[cols].le(month_end)  # NaT comparisons are False -- safe
    leaves_present = valid_mask.any(axis=0)
    existing = {col for col in cols if bool(leaves_present.get(col, False))}
    for depth in range(max_depth, -1, -1):
        for ident in depth_groups.get(depth, []):
            if ident in existing:
                continue
            for child in parent_child_map.get(ident, []):
                if child in existing:
                    existing.add(ident)
                    break

    leaf_existing = [c for c in cols if c in existing]
    if leaf_existing:
        agg_df = score_df[leaf_existing].where(valid_mask[leaf_existing]).copy()
    else:
        agg_df = pd.DataFrame(index=score_df.index)

    for depth in range(max_depth, -1, -1):
        for ident in depth_groups.get(depth, []):
            if ident not in existing or ident in cols:
                continue
            children = [c for c in parent_child_map.get(ident, []) if c in existing]
            children = [c for c in children if c in agg_df.columns]
            if not children:
                continue
            agg_df[ident] = agg_df[children].fillna(0).mean(axis=1)

    leaf_set = {b for b in existing if b in cols}
    if agg_root in agg_df.columns:
        return agg_df[agg_root].fillna(0.0).to_dict(), leaf_set
    return {mid: 0.0 for mid in score_df.index}, leaf_set


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
        score_df, timestamp_df = _load_score_and_timestamp_dfs(domain)
        if score_df.empty:
            self.stdout.write(self.style.WARNING(f'\nNo scores for domain={domain}.'))
            return
        benchmark_cols = score_df.columns.tolist()
        parent_child_map, _child_parent_map, _identifier_to_depth = build_tree_maps(tree_df)
        depth_groups = _depth_groups(tree_df)
        max_depth = int(tree_df['depth'].max())
        agg_root = f'average_{domain}'
        self.stdout.write(
            f'loaded ({len(score_df)} models, {len(benchmark_cols)} leaf benchmarks, '
            f'tree depth={max_depth}).'
        )

        leaf_set_by_month = {}

        for idx, month_str in enumerate(months, start=1):
            t0 = datetime.now(timezone.utc)
            month_end = _month_end_utc(month_str)
            scores_by_model, leaf_set = _aggregate_for_month_fast(
                score_df, timestamp_df, benchmark_cols, parent_child_map,
                depth_groups, max_depth, month_end, agg_root,
            )
            leaf_set_by_month[month_str] = leaf_set

            with transaction.atomic():
                ModelMonthlyAggregate.objects.filter(domain=domain, month=month_str).delete()
                ModelMonthlyAggregate.objects.bulk_create([
                    ModelMonthlyAggregate(
                        model_id=mid, domain=domain, month=month_str,
                        score=(0.0 if pd.isna(val) else float(val)),
                    )
                    for mid, val in scores_by_model.items()
                ], batch_size=2000)
            elapsed = (datetime.now(timezone.utc) - t0).total_seconds()
            self.stdout.write(
                f'  [{idx}/{len(months)}] {month_str}: wrote {len(scores_by_model)} rows in {elapsed:.2f}s'
            )
            self.stdout.flush()
            logger.info('  month %s: wrote %d aggregate rows in %.2fs', month_str, len(scores_by_model), elapsed)

        # Edges: include the boundary one month before `months[0]` so the
        # first transition isn't lost.
        first = months[0]
        boundary = (pd.Timestamp(first + '-01') - pd.offsets.MonthBegin(1)).strftime('%Y-%m')
        if boundary not in leaf_set_by_month:
            _, boundary_leaf_set = _aggregate_for_month_fast(
                score_df, timestamp_df, benchmark_cols, parent_child_map,
                depth_groups, max_depth, _month_end_utc(boundary), agg_root,
            )
            leaf_set_by_month[boundary] = boundary_leaf_set

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

        self.stdout.write(self.style.SUCCESS(
            f'Recompute complete for domain={domain}: {len(months)} month(s).'
        ))
