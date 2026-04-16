#!/usr/bin/env python3
"""
Precompute which leaf benchmarks newly enter the aggregate between consecutive
months (same logic as notebooks/score_trends.ipynb). Writes:
  benchmarks/views/month_benchmark_edges.json

Run from repo root: python3 scripts/generate_month_benchmark_edges.py
Requires notebooks/score_df.csv, notebooks/timestamp_df.csv, and
notebooks/data_files/mv_benchmark_tree.csv.
"""
import json
import os
from collections import defaultdict

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_tree_vision():
    path = os.path.join(ROOT, 'notebooks', 'data_files', 'mv_benchmark_tree.csv')
    df = pd.read_csv(path)
    df = df[df['domain'] == 'vision']
    parent_child_map = defaultdict(list)
    identifier_to_depth = {}
    for _, row in df.iterrows():
        bid = row['identifier']
        identifier_to_depth[bid] = int(row['depth'])
        pid = row['parent_id']
        if pd.notna(pid) and str(pid).strip():
            parent_child_map[str(pid)].append(bid)
    max_depth = max(identifier_to_depth.values()) if identifier_to_depth else 0
    return parent_child_map, identifier_to_depth, max_depth


def build_expected_benchmarks(
    benchmark_cols, timestamp_df, month_end,
    parent_child_map, identifier_to_depth, max_depth,
):
    existing_benchmarks = set()
    for benchmark in benchmark_cols:
        if benchmark not in timestamp_df.columns:
            continue
        col = timestamp_df[benchmark]
        if ((col.notna()) & (col <= month_end)).any():
            existing_benchmarks.add(benchmark)
    for depth in range(max_depth, -1, -1):
        benchmarks_at_depth = [
            identifier for identifier, d in identifier_to_depth.items()
            if d == depth and identifier not in existing_benchmarks
        ]
        for benchmark in benchmarks_at_depth:
            children = parent_child_map.get(benchmark, [])
            if any(child in existing_benchmarks for child in children):
                existing_benchmarks.add(benchmark)
    return existing_benchmarks


def main():
    scores_path = os.path.join(ROOT, 'notebooks', 'score_df.csv')
    ts_path = os.path.join(ROOT, 'notebooks', 'timestamp_df.csv')
    agg_path = os.path.join(ROOT, 'benchmarks', 'views', 'all_aggregated_scores.csv')

    score_df = pd.read_csv(scores_path, index_col=0)
    timestamp_df = pd.read_csv(ts_path, index_col=0)
    timestamp_df = timestamp_df.apply(pd.to_datetime, errors='coerce')
    benchmark_cols = [c for c in score_df.columns if c in timestamp_df.columns]

    parent_child_map, identifier_to_depth, max_depth = load_tree_vision()

    header = pd.read_csv(agg_path, nrows=0)
    month_cols = [c for c in header.columns if c != 'model_id']

    edges = {}
    for i in range(1, len(month_cols)):
        m_prev = month_cols[i - 1]
        m_curr = month_cols[i]
        prev_end = pd.Timestamp(m_prev + '-01') + pd.offsets.MonthEnd(0)
        curr_end = pd.Timestamp(m_curr + '-01') + pd.offsets.MonthEnd(0)
        prev_set = build_expected_benchmarks(
            benchmark_cols, timestamp_df, prev_end,
            parent_child_map, identifier_to_depth, max_depth,
        )
        curr_set = build_expected_benchmarks(
            benchmark_cols, timestamp_df, curr_end,
            parent_child_map, identifier_to_depth, max_depth,
        )
        added_all = curr_set - prev_set
        added_leaves = sorted(b for b in added_all if b in benchmark_cols)
        edges[f'{m_prev}|{m_curr}'] = added_leaves

    out_path = os.path.join(ROOT, 'benchmarks', 'views', 'month_benchmark_edges.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'edges': edges}, f, indent=2)
    print(f'Wrote {len(edges)} month transitions to {out_path}')


if __name__ == '__main__':
    main()
