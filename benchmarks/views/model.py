import logging
import threading
from datetime import date
import numpy as np
import pandas as pd
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.template.defaulttags import register

from .index import get_context, display_model, display_submitter, get_visibility
from .leaderboard import get_ag_grid_context
from ..models import FinalModelContext, BenchmarkMeta, ModelMonthlyAggregate, MonthBenchmarkEdge, Model
from time import time
_logger = logging.getLogger(__name__)

# Thread-local storage for benchmark lookup (used by template filters)
_thread_locals = threading.local()

# Precomputed color arrays matching JavaScript client-side logic
REDGREEN_COLORS = [
    '#ff0000', '#ff0000', '#ff0000', '#ff0000', '#fe0600', '#fe0600', '#fd0d01', '#fd0d01', '#fc1301', '#fb1901',
    '#fb1901', '#fa1f02', '#f92502', '#f92502', '#f82b02', '#f73103', '#f73103', '#f63703', '#f53d03', '#f44204',
    '#f44204', '#f44804', '#f34d04', '#f25305', '#f15805', '#f15805', '#f05e05', '#ef6306', '#ee6806', '#ed6e06',
    '#ec7307', '#eb7807', '#ea7d07', '#e98208', '#e88708', '#e88708', '#e78c08', '#e69109', '#e69509', '#e59a09',
    '#e49f0a', '#e3a30a', '#e2a80a', '#e1ac0a', '#e0b10b', '#dfb50b', '#deb90b', '#ddbe0c', '#dcc20c', '#dcc60c',
    '#dbca0d', '#d9d20d', '#d8d60d', '#d4d70e', '#cfd60e', '#c9d50e', '#c4d40f', '#bed40f', '#b9d30f', '#b4d20f',
    '#aed110', '#a4cf10', '#9fce10', '#9acd11', '#95cc11', '#90cc11', '#8bcb11', '#86ca12', '#7dc812', '#78c712',
    '#74c613', '#6fc613', '#6ac513', '#66c413', '#5dc214', '#59c114', '#55c014', '#51c015', '#48be15', '#44bd15',
    '#40bc16', '#3cbb16', '#38bb16', '#31b917', '#2db817', '#29b717', '#26b617', '#1eb518', '#1bb418', '#18b319',
    '#18b21c', '#19b124', '#19b028', '#19af2b', '#19ad32', '#1aad36', '#1aac39', '#1aaa40', '#1aa943', '#1ba947',
    '#1ba84a'
]

GRAY_COLORS = [
    '#f2f2f2', '#f2f2f2', '#f2f2f2', '#f2f2f2', '#f0f0f0', '#f0f0f0', '#eeeeee', '#eeeeee', '#ededed', '#ebebeb',
    '#ebebeb', '#e9e9e9', '#e7e7e7', '#e7e7e7', '#e6e6e6', '#e4e4e4', '#e4e4e4', '#e2e2e2', '#e0e0e0', '#dedede',
    '#dedede', '#dddddd', '#dbdbdb', '#d9d9d9', '#d7d7d7', '#d7d7d7', '#d6d6d6', '#d4d4d4', '#d2d2d2', '#d0d0d0',
    '#cecece', '#cdcdcd', '#cbcbcb', '#c9c9c9', '#c7c7c7', '#c7c7c7', '#c5c5c5', '#c4c4c4', '#c2c2c2', '#c0c0c0',
    '#bebebe', '#bdbdbd', '#bbbbbb', '#b9b9b9', '#b7b7b7', '#b5b5b5', '#b4b4b4', '#b2b2b2', '#b0b0b0', '#aeaeae',
    '#adadad', '#a9a9a9', '#a7a7a7', '#a5a5a5', '#a4a4a4', '#a2a2a2', '#a0a0a0', '#9e9e9e', '#9d9d9d', '#9b9b9b',
    '#999999', '#959595', '#949494', '#929292', '#909090', '#8e8e8e', '#8d8d8d', '#8b8b8b', '#878787', '#858585',
    '#848484', '#828282', '#808080', '#7e7e7e', '#7b7b7b', '#797979', '#777777', '#757575', '#727272', '#707070',
    '#6e6e6e', '#6c6c6c', '#6b6b6b', '#676767', '#656565', '#646464', '#626262', '#5e5e5e', '#5c5c5c', '#5b5b5b',
    '#595959', '#555555', '#545454', '#525252', '#4e4e4e', '#4c4c4c', '#4b4b4b', '#474747', '#454545', '#444444',
    '#424242'
]

COLOR_NONE = '#e0e1e2'
GAMMA = 0.5

# Module-level snapshot caches. Keyed on (domain, max-month) so a recompute that
# moves the latest month forward causes natural cache misses across workers.
_TREND_CACHE = {}
_TREND_CACHE_LOCK = threading.Lock()


def _trend_cache_key(domain):
    """Latest month present in ``ModelMonthlyAggregate`` for the domain (cache key seed)."""
    return (ModelMonthlyAggregate.objects
            .filter(domain=domain)
            .order_by('-month')
            .values_list('month', flat=True)
            .first())


def _trend_cache_get(kind, domain):
    max_month = _trend_cache_key(domain)
    return _TREND_CACHE.get((kind, domain, max_month)), max_month


def _trend_cache_put(kind, domain, max_month, value):
    with _TREND_CACHE_LOCK:
        # Drop any prior entries for this (kind, domain) so the dict stays bounded.
        for k in list(_TREND_CACHE):
            if k[0] == kind and k[1] == domain:
                del _TREND_CACHE[k]
        _TREND_CACHE[(kind, domain, max_month)] = value


def clear_trend_cache():
    """Drop the in-process trend snapshot cache. Call after ``recompute_score_trends``
    so the next request in this worker reloads fresh aggregates instead of serving
    a snapshot keyed on an unchanged ``max(month)``. Per-process only -- multi-worker
    deployments still need a cross-worker bust (e.g. cache-version row or Redis pub/sub)."""
    with _TREND_CACHE_LOCK:
        _TREND_CACHE.clear()


def _load_month_benchmark_edges(domain='vision'):
    """Maps 'YYYY-MM|YYYY-MM' -> list of leaf benchmark ids newly eligible."""
    cached, max_month = _trend_cache_get('edges', domain)
    if cached is not None:
        return cached
    rows = MonthBenchmarkEdge.objects.filter(domain=domain).values(
        'month_prev', 'month_curr', 'leaf_benchmarks',
    )
    edges = {f"{r['month_prev']}|{r['month_curr']}": list(r['leaf_benchmarks'] or []) for r in rows}
    _trend_cache_put('edges', domain, max_month, edges)
    return edges


def _load_all_months(domain):
    """All months that exist in ModelMonthlyAggregate for the domain, ordered ascending."""
    return sorted({m for m in ModelMonthlyAggregate.objects
                   .filter(domain=domain)
                   .values_list('month', flat=True).distinct()})


def _load_public_wide_scores(domain):
    """Wide scores frame (model_id col + one column per 'YYYY-MM' month) for *public* models only."""
    cached, max_month = _trend_cache_get('public_wide', domain)
    if cached is not None:
        return cached.copy(), max_month
    qs = (ModelMonthlyAggregate.objects
          .filter(domain=domain, model__public=True)
          .values('model_id', 'month', 'score'))
    df = pd.DataFrame(list(qs))
    if df.empty:
        wide = pd.DataFrame(columns=['model_id'])
    else:
        wide = df.pivot(index='model_id', columns='month', values='score').reset_index()
        wide.columns.name = None
    _trend_cache_put('public_wide', domain, max_month, wide)
    return wide.copy(), max_month


def _load_model_names(domain):
    """Map ``{model_id: name}`` for all models in the domain. Cached per latest month."""
    cached, max_month = _trend_cache_get('names', domain)
    if cached is not None:
        return cached, max_month
    names = dict(Model.objects.filter(domain=domain).values_list('id', 'name'))
    _trend_cache_put('names', domain, max_month, names)
    return names, max_month


def _load_focal_coverage_deltas(model_id, domain):
    """Map ``{'YYYY-MM': [leaf_ids,...]}`` of leaves the focal model newly scored on each month.

    Populated by ``recompute_score_trends``; drives the "you newly scored on
    existing benchmarks this month" branch of the trend hover narrative.
    """
    rows = (ModelMonthlyAggregate.objects
            .filter(model_id=model_id, domain=domain)
            .values_list('month', 'coverage_leaves_added_vs_prev'))
    return {m: (leaves or []) for m, leaves in rows}


def _date_to_month_key(date_str):
    try:
        return pd.Timestamp(date_str).strftime('%Y-%m')
    except Exception:
        s = str(date_str)
        return s[:7] if len(s) >= 7 else s


def _fmt_model_id(mid):
    try:
        f = float(mid)
        if f == int(f):
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return str(mid)


def _rank_transition_model_lines(model_id, ym_prev, ym_curr, rank1, rank2,
                                 rank_df, wide_scores, names=None, added_count=0,
                                 coverage_added_count=0):
    """
    Sidebar lines naming other models involved in a month-to-month rank change.
    Identical-movement rows are grouped on one bullet; ``names`` resolves ids to
    display names (falling back to ``#id``). A one-line ``Why this changed:``
    headline is prepended summarising movement and benchmark drivers.
    """
    if ym_prev not in rank_df.columns or ym_curr not in rank_df.columns:
        return []

    rank_change = rank2 - rank1
    focal = str(model_id)
    names = names or {}
    ranks_t1 = rank_df.set_index('model_id')[ym_prev]
    ranks_t2 = rank_df.set_index('model_id')[ym_curr]
    sc1 = wide_scores.set_index('model_id')[ym_prev]
    sc2 = wide_scores.set_index('model_id')[ym_curr]

    def _name(mid):
        try:
            key = int(mid)
        except (TypeError, ValueError):
            key = mid
        return names.get(key) or f'#{_fmt_model_id(mid)}'

    def _emit(rows, header, fmt):
        if not rows:
            return []
        grouped = {}
        for _, g_key, name in sorted(rows, key=lambda r: r[0]):
            grouped.setdefault(g_key, []).append(name)
        out = [f'{header} ({len(rows)}):']
        cap, n = 10, 0
        for g_key, g_names in grouped.items():
            if n >= cap:
                out.append(f'… and {len(rows) - n} more.')
                return out
            out.append(fmt(g_key, g_names))
            n += len(g_names)
        return out

    moved_past, focal_past, new_above, exited = [], [], [], []
    for om in ranks_t1.index:
        if str(om) == focal:
            continue
        r1 = ranks_t1[om]
        r2 = ranks_t2.get(om, np.nan)
        if pd.isna(r1):
            continue
        if pd.isna(r2):
            or1 = int(r1)
            if or1 > rank1:
                exited.append((or1, ('exited', or1), _name(om)))
            continue
        or1, or2 = int(r1), int(r2)
        s1, s2 = sc1.get(om), sc2.get(om)
        s1f = float(s1) if pd.notna(s1) else None
        s2f = float(s2) if pd.notna(s2) else None
        key = ('move', or1, or2, s1f, s2f)
        if rank_change > 0 and ((or1 > rank1 and or2 <= rank2) or (or1 >= rank1 and or2 < rank2)):
            moved_past.append((or2, key, _name(om)))
        elif rank_change < 0 and ((or1 < rank1 and or2 >= rank2) or (or1 <= rank1 and or2 > rank2)):
            focal_past.append((or2, key, _name(om)))
    for om in ranks_t2.index:
        if str(om) == focal:
            continue
        if pd.notna(ranks_t1.get(om, np.nan)) or pd.isna(ranks_t2[om]):
            continue
        or2 = int(ranks_t2[om])
        if or2 >= rank2:
            continue
        s2 = sc2.get(om)
        s2f = float(s2) if pd.notna(s2) else None
        new_above.append((or2, ('new', or2, s2f), _name(om)))

    def _fmt_move(g, n):
        _, or1, or2, s1, s2 = g
        sp = f', aggregate score {s1:.4f} → {s2:.4f}' if s1 is not None and s2 is not None else ''
        return f'• {", ".join(n)}: rank {or1} → {or2}{sp}'

    def _fmt_new(g, n):
        _, or2, s2 = g
        sp = f', score {s2:.4f}' if s2 is not None else ''
        return f'• {", ".join(n)}: rank {or2}{sp}'

    def _fmt_exited(g, n):
        return f'• {", ".join(n)}: was rank {g[1]}'

    lines = []
    lines += _emit(moved_past, 'Models that moved ahead of this model', _fmt_move)
    lines += _emit(focal_past, 'Models you moved past', _fmt_move)
    lines += _emit(new_above, 'New entries ranked above you', _fmt_new)
    lines += _emit(exited, 'Models that left the pool (previously ranked below you)', _fmt_exited)

    bits = []
    if moved_past:
        bits.append(f'{len(moved_past)} existing model(s) moved past you')
    if focal_past:
        bits.append(f'you moved past {len(focal_past)} model(s)')
    if new_above:
        bits.append(f'{len(new_above)} new model(s) entered above you')
    if added_count:
        bits.append(f'{added_count} new leaf benchmark(s) were counted')
    if coverage_added_count:
        bits.append(f'you newly scored on {coverage_added_count} existing benchmark(s) this month')
    if bits:
        lines.insert(0, 'Why this changed: ' + '; '.join(bits) + '.')
    return lines


def _overall_trend_lines(dates, values, kind):
    """Summary from first to last point (default sidebar + 'no change' branch)."""
    if not dates or not values:
        return ['No trend data.']
    n = len(dates)
    if kind == 'score':
        return [
            f'Whole series: {n} point(s), {values[0]:.4f} → {values[-1]:.4f}.',
            f'Net change (first → last): {(values[-1] - values[0]):+.4f}.',
            'Hover a point to compare it to the previous month.',
        ]
    r0 = int(round(float(values[0])))
    r1 = int(round(float(values[-1])))
    return [
        f'Whole series: {n} point(s), rank {r0} → {r1}.',
        f'Net movement (first → last): {r0 - r1:+d} (positive means improved).',
        'Hover a point to compare it to the previous month.',
    ]


def _point_attribution_lines(i, dates, values, kind, edges_map, overall_lines, rank_explain=None):
    """Narrative for hover at index i vs previous point; uses benchmark-edge map when value changes."""
    if i == 0:
        if kind == 'score':
            head = [
                f'First point ({_date_to_month_key(dates[0])}): score {values[0]:.4f}.',
                'There is no prior month on this chart.',
            ]
        else:
            head = [
                f'First point ({_date_to_month_key(dates[0])}): rank {int(round(float(values[0])))}.',
                'There is no prior month on this chart.',
            ]
        return head + overall_lines

    ym_prev = _date_to_month_key(dates[i - 1])
    ym_curr = _date_to_month_key(dates[i])
    edge_key = f'{ym_prev}|{ym_curr}'
    added = edges_map.get(edge_key, [])
    coverage_added = ((rank_explain or {}).get('coverage_deltas') or {}).get(ym_curr, []) or []

    if kind == 'score':
        prev_v, curr_v = values[i - 1], values[i]
        delta = curr_v - prev_v
        unchanged = abs(delta) < 1e-9
        head = [
            f'vs prior month ({ym_prev}): {prev_v:.4f} → {ym_curr}: {curr_v:.4f}.',
        ]
    else:
        prev_v = int(round(float(values[i - 1])))
        curr_v = int(round(float(values[i])))
        delta = curr_v - prev_v
        unchanged = delta == 0
        head = [
            f'vs prior month ({ym_prev}): rank {prev_v} → {ym_curr}: rank {curr_v}.',
        ]

    if unchanged:
        return head + ['No change from the previous point. Overall movement:'] + overall_lines

    if kind == 'score':
        mid = [f'Change from previous point: {delta:+.4f}.']
    else:
        if delta < 0:
            mid = [f'Rank change vs prior month: {delta:+d} (negative = improved).']
        else:
            mid = [f'Rank change vs prior month: {delta:+d} (positive = moved down).']

    out = head + mid
    model_lines = []
    if kind == 'rank' and rank_explain is not None:
        ws = rank_explain.get('wide_scores')
        rdf = rank_explain.get('rank_df')
        mid_model = rank_explain.get('model_id')
        if ws is not None and rdf is not None and mid_model is not None:
            cols = [c for c in ws.columns if c != 'model_id']
            if ym_prev in cols and ym_curr in cols:
                model_lines = _rank_transition_model_lines(
                    mid_model, ym_prev, ym_curr, prev_v, curr_v, rdf, ws,
                    names=rank_explain.get('name_map'), added_count=len(added),
                    coverage_added_count=len(coverage_added),
                )
    if model_lines:
        out.extend(model_lines)
    elif kind == 'score':
        score_bits = []
        if added:
            score_bits.append(f'{len(added)} new leaf benchmark(s) were counted')
        if coverage_added:
            score_bits.append(f'you newly scored on {len(coverage_added)} existing benchmark(s) this month')
        if score_bits:
            out.append('Why this changed: ' + '; '.join(score_bits) + '.')

    if coverage_added:
        out.append(f'Existing benchmarks you newly got scored on ({len(coverage_added)}):')
        cap = 12
        for b in coverage_added[:cap]:
            out.append(f'• {b}')
        if len(coverage_added) > cap:
            out.append(f'… and {len(coverage_added) - cap} more.')

    if added:
        out.append('New leaf benchmarks counted in the aggregate this month (vs. prior month):')
        cap = 12
        for b in added[:cap]:
            out.append(f'• {b}')
        if len(added) > cap:
            out.append(f'… and {len(added) - cap} more.')
    elif not coverage_added:
        if kind == 'score' or not model_lines:
            out.append(
                'No new leaf benchmarks between these months; the shift is likely from updated scores, '
                're-aggregation, or other models in the public pool.'
            )
        else:
            out.append(
                'No new leaf benchmarks between these months; remaining movement is from aggregate score updates.'
            )
    return out


def _build_trend_meta(dates, values, kind, edges_map, extra_default_lines=None, rank_explain=None):
    """
    Client reads trendMeta: defaultLines when idle; points[i].lines on hover.
    kind: 'score' or 'rank'.
    """
    base_overall = _overall_trend_lines(dates, values, kind)
    default_lines = base_overall + list(extra_default_lines or [])
    points = []
    # rank-only fields (rank_df, wide_scores, name_map) are guarded inside
    # _point_attribution_lines; coverage_deltas applies to both kinds.
    for i in range(len(dates)):
        points.append({
            'lines': _point_attribution_lines(i, dates, values, kind, edges_map, base_overall, rank_explain=rank_explain),
        })
    list_el = 'model-score-attribution-list' if kind == 'score' else 'model-rank-attribution-list'
    return {
        'kind': kind,
        'attributionListId': list_el,
        'defaultLines': default_lines,
        'points': points,
    }


def _build_score_trend_plot_json(dates, scores, range_start, range_end, shade_region=None):
    """Build Plotly JSON for score trend. Fixed range, no pan/zoom. Optional shaded band for forward-filled months."""
    y_min = min(scores)
    y_max = max(scores)
    padding = max(0.05, (y_max - y_min) * 0.1) if y_max > y_min else 0.05
    y_range = [max(0, y_min - padding), min(1, y_max + padding)]
    shapes = []
    if shade_region and len(shade_region) == 2:
        x0, x1 = shade_region
        shapes.append({
            'type': 'rect',
            'xref': 'x',
            'yref': 'paper',
            'x0': x0,
            'x1': x1,
            'y0': 0,
            'y1': 1,
            'fillcolor': 'rgba(50, 115, 220, 0.06)',
            'line': {'width': 0},
            'layer': 'below',
        })
    shapes.append({
        'type': 'line',
        'xref': 'x',
        'yref': 'paper',
        'x0': dates[-1],
        'x1': dates[-1],
        'y0': 0,
        'y1': 1,
        'line': {'color': 'rgba(72, 72, 72, 0.35)', 'width': 1, 'dash': 'dot'},
        'layer': 'below',
    })
    annotations = [
        {
            'x': dates[-1],
            'y': scores[-1],
            'text': 'Latest',
            'showarrow': True,
            'arrowhead': 2,
            'arrowsize': 0.6,
            'arrowwidth': 1,
            'arrowcolor': '#3273dc',
            'ax': 0,
            'ay': -36,
            'bgcolor': 'rgba(255, 255, 255, 0.92)',
            'bordercolor': '#3273dc',
            'borderwidth': 1,
            'font': {'size': 11, 'color': '#363636'},
        },
    ]
    if len(dates) > 1:
        annotations.append({
            'x': dates[0],
            'y': scores[0],
            'text': 'Start',
            'showarrow': True,
            'arrowhead': 2,
            'arrowsize': 0.5,
            'arrowwidth': 1,
            'arrowcolor': '#7a7a7a',
            'ax': 0,
            'ay': 32,
            'bgcolor': 'rgba(255, 255, 255, 0.9)',
            'bordercolor': '#dbdbdb',
            'borderwidth': 1,
            'font': {'size': 10, 'color': '#4a4a4a'},
        })
    score_cd = [[i] for i in range(len(dates))]
    return {
        'data': [{
            'x': dates,
            'y': scores,
            'type': 'scatter',
            'mode': 'lines',
            'hoveron': 'points',
            'name': 'average_vision',
            'customdata': score_cd,
            'line': {
                'color': '#3273dc',
                'width': 2.5,
                'shape': 'spline',
                'smoothing': 1.3,
            },
            'hovertemplate': '<b>%{x|%d %b %Y}</b><br>Score: %{y:.4f}<extra></extra>',
        }],
        'layout': {
            'height': 400,
            'autosize': True,
            'paper_bgcolor': '#ffffff',
            'plot_bgcolor': '#fafafa',
            'margin': {'t': 24, 'r': 16, 'b': 48, 'l': 56},
            'shapes': shapes,
            'annotations': annotations,
            'hovermode': 'closest',
            # Plotly 3 default template can re-enable grids; turn off explicitly.
            'template': {
                'layout': {
                    'xaxis': {
                        'showgrid': False,
                        'zeroline': False,
                        'minor': {'showgrid': False},
                    },
                    'yaxis': {
                        'showgrid': False,
                        'zeroline': False,
                        'minor': {'showgrid': False},
                    },
                },
            },
            'xaxis': {
                'title': {'text': 'Date', 'font': {'size': 12}},
                'type': 'date',
                'tickformat': '%b %Y',
                'fixedrange': True,
                'autorange': False,
                'range': [range_start, range_end],
                'showgrid': False,
                'zeroline': False,
                'gridcolor': 'rgba(0,0,0,0)',
                'minor': {'showgrid': False},
                'showline': True,
                'linecolor': '#dbdbdb',
                'mirror': False,
            },
            'yaxis': {
                'title': {'text': 'Score', 'font': {'size': 12}},
                'fixedrange': True,
                'autorange': False,
                'range': [round(y_range[0], 6), round(y_range[1], 6)],
                'showgrid': False,
                'zeroline': False,
                'gridcolor': 'rgba(0,0,0,0)',
                'minor': {'showgrid': False},
                'showline': True,
                'linecolor': '#dbdbdb',
            },
            'showlegend': False,
        },
        'config': {
            'responsive': True,
            'displayModeBar': True,
            'scrollZoom': False,
            'modeBarButtonsToRemove': ['zoomIn2d', 'zoomOut2d', 'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'autoScale2d'],
        },
    }


def _build_rank_trend_plot_json(dates, ranks, range_start, range_end, shade_region=None):
    """Build Plotly JSON for rank trend. Rank 1 = best (shown at top via reversed Y)."""
    valid = [r for r in ranks if r is not None and (not isinstance(r, float) or not np.isnan(r))]
    if not valid:
        valid = [1]
    rank_max = max(valid)
    rank_min = min(valid)
    padding = max(1, (rank_max - rank_min) * 0.1) if rank_max > rank_min else 1
    y_range = [rank_max + padding, max(1, rank_min - padding)]
    shapes = []
    if shade_region and len(shade_region) == 2:
        x0, x1 = shade_region
        shapes.append({
            'type': 'rect',
            'xref': 'x',
            'yref': 'paper',
            'x0': x0,
            'x1': x1,
            'y0': 0,
            'y1': 1,
            'fillcolor': 'rgba(50, 115, 220, 0.06)',
            'line': {'width': 0},
            'layer': 'below',
        })
    shapes.append({
        'type': 'line',
        'xref': 'x',
        'yref': 'paper',
        'x0': dates[-1],
        'x1': dates[-1],
        'y0': 0,
        'y1': 1,
        'line': {'color': 'rgba(72, 72, 72, 0.35)', 'width': 1, 'dash': 'dot'},
        'layer': 'below',
    })
    annotations = [
        {
            'x': dates[-1],
            'y': ranks[-1],
            'text': 'Latest',
            'showarrow': True,
            'arrowhead': 2,
            'arrowsize': 0.6,
            'arrowwidth': 1,
            'arrowcolor': '#3273dc',
            'ax': 0,
            'ay': -36,
            'bgcolor': 'rgba(255, 255, 255, 0.92)',
            'bordercolor': '#3273dc',
            'borderwidth': 1,
            'font': {'size': 11, 'color': '#363636'},
        },
    ]
    if len(dates) > 1:
        annotations.append({
            'x': dates[0],
            'y': ranks[0],
            'text': 'Start',
            'showarrow': True,
            'arrowhead': 2,
            'arrowsize': 0.5,
            'arrowwidth': 1,
            'arrowcolor': '#7a7a7a',
            'ax': 0,
            'ay': 32,
            'bgcolor': 'rgba(255, 255, 255, 0.9)',
            'bordercolor': '#dbdbdb',
            'borderwidth': 1,
            'font': {'size': 10, 'color': '#4a4a4a'},
        })
    rank_custom = [[i] for i in range(len(dates))]
    return {
        'data': [{
            'x': dates,
            'y': ranks,
            'type': 'scatter',
            'mode': 'lines',
            'hoveron': 'points',
            'name': 'rank',
            'customdata': rank_custom,
            'line': {
                'color': '#3273dc',
                'width': 2.5,
                'shape': 'spline',
                'smoothing': 1.3,
            },
            'hovertemplate': '<b>%{x|%d %b %Y}</b><br>Rank: %{y:.0f}<extra></extra>',
        }],
        'layout': {
            'height': 400,
            'autosize': True,
            'paper_bgcolor': '#ffffff',
            'plot_bgcolor': '#fafafa',
            'margin': {'t': 24, 'r': 16, 'b': 48, 'l': 56},
            'shapes': shapes,
            'annotations': annotations,
            'hovermode': 'closest',
            'template': {
                'layout': {
                    'xaxis': {
                        'showgrid': False,
                        'zeroline': False,
                        'minor': {'showgrid': False},
                    },
                    'yaxis': {
                        'showgrid': False,
                        'zeroline': False,
                        'minor': {'showgrid': False},
                    },
                },
            },
            'xaxis': {
                'title': {'text': 'Date', 'font': {'size': 12}},
                'type': 'date',
                'tickformat': '%b %Y',
                'fixedrange': True,
                'autorange': False,
                'range': [range_start, range_end],
                'showgrid': False,
                'zeroline': False,
                'gridcolor': 'rgba(0,0,0,0)',
                'minor': {'showgrid': False},
                'showline': True,
                'linecolor': '#dbdbdb',
            },
            'yaxis': {
                'title': {'text': 'Rank (1 = best)', 'font': {'size': 12}},
                'fixedrange': True,
                'autorange': False,
                'range': [round(y_range[0], 2), round(y_range[1], 2)],
                'showgrid': False,
                'zeroline': False,
                'gridcolor': 'rgba(0,0,0,0)',
                'minor': {'showgrid': False},
                'showline': True,
                'linecolor': '#dbdbdb',
            },
            'showlegend': False,
        },
        'config': {
            'responsive': True,
            'displayModeBar': True,
            'scrollZoom': False,
            'modeBarButtonsToRemove': ['zoomIn2d', 'zoomOut2d', 'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'autoScale2d'],
        },
    }


def _monthly_dates_until_today(last_date_str):
    """Yield month-end date strings from the month after last_date_str through current month, then today if later."""
    last_ts = pd.Timestamp(last_date_str)
    today_ts = pd.Timestamp(date.today())
    out = []
    cur = last_ts + pd.offsets.MonthBegin(1)  # first day of next month
    while cur <= today_ts:
        month_end_ts = cur + pd.offsets.MonthEnd(0)
        if month_end_ts > today_ts:
            out.append(today_ts.strftime('%Y-%m-%d'))
            break
        out.append(month_end_ts.strftime('%Y-%m-%d'))
        cur = cur + pd.offsets.MonthBegin(1)
    if not out and last_ts < today_ts:
        out.append(today_ts.strftime('%Y-%m-%d'))
    return out


def _wide_scores_and_rank_df(df, month_cols):
    """Replace 0 with NaN, round scores; compute public rank per month (1 = best, ties skip)."""
    wide_scores = df[['model_id'] + month_cols].copy()
    for col in month_cols:
        wide_scores[col] = wide_scores[col].replace(0.0, np.nan).round(2)
    rank_df = wide_scores[['model_id']].copy()
    for col in month_cols:
        scores = wide_scores[col]
        ranks = scores.rank(method='min', ascending=False, na_option='keep')
        unique_ranks = sorted(ranks.dropna().unique())
        rank_mapping = {}
        current_rank = 1
        for rank_val in unique_ranks:
            num_tied = (ranks == rank_val).sum()
            rank_mapping[rank_val] = current_rank
            current_rank += num_tied
        rank_df[col] = ranks.map(rank_mapping)
    return wide_scores, rank_df


def _load_score_trend_from_db(model_id, domain):
    """Build score trend for one model from ``ModelMonthlyAggregate``. Returns plot JSON or None."""
    try:
        rows = list(ModelMonthlyAggregate.objects
                    .filter(model_id=model_id, domain=domain)
                    .order_by('month')
                    .values('month', 'score'))
        if not rows:
            return None
        month_cols = _load_all_months(domain)
        if not month_cols:
            return None
        series = pd.Series(
            {r['month']: r['score'] for r in rows},
            dtype='float64',
        )
        valid = series.dropna()
        if valid.empty:
            return None
        # Skip leading zeros (same as the previous CSV-backed logic).
        start_idx = next((i for i, v in enumerate(valid.values) if v > 0), 0)
        series = valid.iloc[start_idx:]
        if series.empty:
            return None
        # Column names are YYYY-MM -> use month-end for date axis
        dates = []
        for col in series.index:
            try:
                ts = pd.Timestamp(str(col) + '-01') + pd.offsets.MonthEnd(0)
                dates.append(ts.strftime('%Y-%m-%d'))
            except Exception:
                dates.append(str(col))
        scores = [round(float(v), 6) for v in series.values]
        if not dates or not scores:
            return None
        # Extend with monthly dots to current day (one point per month so the line has monthly dots)
        today_str = date.today().strftime('%Y-%m-%d')
        shade_region = None
        if dates[-1] < today_str:
            extra_dates = _monthly_dates_until_today(dates[-1])
            if extra_dates:
                shade_region = (extra_dates[0], today_str)
                dates = list(dates) + extra_dates
                scores = list(scores) + [scores[-1]] * len(extra_dates)
        # X-axis: start from first month in CSV, end at current day
        try:
            first_ts = pd.Timestamp(str(month_cols[0]) + '-01') + pd.offsets.MonthEnd(0)
            range_start = first_ts.strftime('%Y-%m-%d')
            range_end = today_str
        except Exception:
            range_start = dates[0]
            range_end = today_str
        extra_default = []
        if shade_region:
            extra_default.append(
                'Shaded band: months extended to today using the last known aggregate (flat carry-forward).'
            )
        edges = _load_month_benchmark_edges(domain)
        plot_json = _build_score_trend_plot_json(dates, scores, range_start, range_end, shade_region=shade_region)
        plot_json['trendMeta'] = _build_trend_meta(
            dates, scores, 'score', edges, extra_default_lines=extra_default,
            rank_explain={'coverage_deltas': _load_focal_coverage_deltas(model_id, domain)},
        )
        return plot_json
    except Exception:
        _logger.exception('score trend build failed for model %s domain %s', model_id, domain)
        return None


def _load_and_build_score_trend(model_id, benchmarks, models, domain):
    """Build model's average_<domain> score trend from ``ModelMonthlyAggregate``."""
    try:
        if domain != 'vision':
            return None
        return _load_score_trend_from_db(model_id, domain)
    except Exception:
        _logger.exception('score trend wrapper failed for model %s domain %s', model_id, domain)
        return None


def _load_rank_trend_from_db(model_id, domain, focal_is_public):
    """Compute per-month ranks against the public model pool.

    Private focal models are temporarily added to the public-only frame so they get a
    rank against the public pool, but never appear as named entries in another model's
    rank-transition sidebar (the focal-exclusion in ``_rank_transition_model_lines``
    handles that, and other private models are simply not in the frame).
    """
    try:
        public_wide, _max_month = _load_public_wide_scores(domain)
        month_cols = [c for c in public_wide.columns if c != 'model_id']
        if not month_cols:
            return None
        df = public_wide
        if not focal_is_public:
            focal_rows = list(ModelMonthlyAggregate.objects
                              .filter(model_id=model_id, domain=domain)
                              .values('month', 'score'))
            if not focal_rows:
                return None
            focal = {'model_id': model_id}
            focal.update({m: None for m in month_cols})
            for r in focal_rows:
                if r['month'] in focal:
                    focal[r['month']] = r['score']
            df = pd.concat([public_wide, pd.DataFrame([focal])], ignore_index=True)
        row = df.loc[df['model_id'].astype(str) == str(model_id)]
        if row.empty:
            return None
        wide_scores, rank_df = _wide_scores_and_rank_df(df, month_cols)
        model_idx = row.index[0]
        series = rank_df.loc[model_idx, month_cols]
        valid = series.dropna()
        if valid.empty:
            return None
        # Only include months where we have a rank (same idea as score: skip leading invalid if desired; here we have ranks)
        dates = []
        ranks_out = []
        for col in valid.index:
            try:
                ts = pd.Timestamp(str(col) + '-01') + pd.offsets.MonthEnd(0)
                dates.append(ts.strftime('%Y-%m-%d'))
            except Exception:
                dates.append(str(col))
            r = valid[col]
            ranks_out.append(int(r) if pd.notna(r) and not (isinstance(r, float) and np.isnan(r)) else None)
        # Filter out None if any
        pairs = [(d, r) for d, r in zip(dates, ranks_out) if r is not None]
        if not pairs:
            return None
        dates, ranks_out = zip(*pairs)
        dates = list(dates)
        ranks_out = list(ranks_out)
        # Extend with monthly dots to current day (one point per month, same as scores)
        today_str = date.today().strftime('%Y-%m-%d')
        shade_region = None
        if dates[-1] < today_str:
            extra_dates = _monthly_dates_until_today(dates[-1])
            if extra_dates:
                shade_region = (extra_dates[0], today_str)
                dates = dates + extra_dates
                ranks_out = ranks_out + [ranks_out[-1]] * len(extra_dates)
        try:
            first_ts = pd.Timestamp(str(month_cols[0]) + '-01') + pd.offsets.MonthEnd(0)
            range_start = first_ts.strftime('%Y-%m-%d')
            range_end = today_str
        except Exception:
            range_start = dates[0]
            range_end = today_str
        extra_default = []
        if shade_region:
            extra_default.append(
                'Shaded band: months extended to today using the last known rank (flat carry-forward).'
            )
        edges = _load_month_benchmark_edges(domain)
        plot_json = _build_rank_trend_plot_json(dates, ranks_out, range_start, range_end, shade_region=shade_region)
        plot_json['trendMeta'] = _build_trend_meta(
            dates,
            ranks_out,
            'rank',
            edges,
            extra_default_lines=extra_default,
            rank_explain={
                'model_id': model_id,
                'rank_df': rank_df,
                'wide_scores': wide_scores,
                'name_map': _load_model_names(domain)[0],
                'coverage_deltas': _load_focal_coverage_deltas(model_id, domain),
            },
        )
        return plot_json
    except Exception:
        _logger.exception('rank trend build failed for model %s domain %s', model_id, domain)
        return None

def _load_and_build_rank_trend(model_id, domain, focal_is_public=True):
    """Build rank-over-time trend from ``ModelMonthlyAggregate``. Plot JSON includes trendMeta."""
    try:
        if domain != 'vision':
            return None
        return _load_rank_trend_from_db(model_id, domain, focal_is_public)
    except Exception:
        _logger.exception('rank trend wrapper failed for model %s domain %s', model_id, domain)
        return None

def enrich_model_scores_with_benchmarks(model, benchmarks):
    """
    Enrich model scores with full benchmark metadata.

    After optimization, the materialized view only stores benchmark_type_id in scores.
    This function adds back the full benchmark object with metadata for the model detail page.

    Args:
        model: Model object with scores
        benchmarks: List of FinalBenchmarkContext objects from get_context
    """
    if not hasattr(model, 'scores') or not model.scores:
        return

    # Create benchmark lookup by benchmark_type_id
    benchmark_lookup = {bench.benchmark_type_id: bench for bench in benchmarks}

    # Query all BenchmarkMeta objects we'll need
    meta_ids = [bench.meta_id for bench in benchmarks if bench.meta_id is not None]
    meta_lookup = {}
    if meta_ids:
        metas = BenchmarkMeta.objects.filter(id__in=meta_ids)
        meta_lookup = {meta.id: meta for meta in metas}

    # Enrich each score with full benchmark object
    for score in model.scores:
        if not isinstance(score, dict):
            continue

        benchmark_type_id = score.get('benchmark_type_id')
        if not benchmark_type_id or benchmark_type_id not in benchmark_lookup:
            continue

        bench = benchmark_lookup[benchmark_type_id]

        # Create benchmark dict with all fields needed by template
        benchmark_dict = {
            'benchmark_type_id': bench.benchmark_type_id,
            'identifier': bench.identifier,
            'short_name': bench.short_name,
            'version': bench.version,
            'depth': bench.depth,
            'parent': bench.parent,
            'children': bench.children,
            'root_parent': bench.root_parent,
            'ceiling': bench.ceiling,
            'ceiling_error': bench.ceiling_error,
            'url': bench.benchmark_url,
            'bibtex': bench.benchmark_bibtex,
            'number_of_all_children': bench.number_of_all_children,
        }

        # Add meta if available
        if bench.meta_id and bench.meta_id in meta_lookup:
            meta = meta_lookup[bench.meta_id]
            benchmark_dict['meta'] = {
                'number_of_stimuli': meta.number_of_stimuli,
                'number_of_recording_sites': meta.number_of_recording_sites,
                'recording_sites': meta.recording_sites,
                'behavioral_task': meta.behavioral_task,
            }
        else:
            benchmark_dict['meta'] = None

        # Add benchmark object to score
        score['benchmark'] = benchmark_dict


def compute_score_statistics(model, public_models):
    """
    Compute color, best, and median statistics for model scores.

    These fields were removed from the materialized view during optimization
    but are needed for the model detail page visualizations.

    Replicates JavaScript client-side logic from color-utils.js

    Args:
        model: Model object with enriched scores
        public_models: List of all public models to compute statistics against
    """
    if not hasattr(model, 'scores') or not model.scores:
        return

    # Collect scores by benchmark for computing best/median/min/max
    benchmark_scores = {}
    for other_model in public_models:
        if not hasattr(other_model, 'scores') or not other_model.scores:
            continue
        for other_score in other_model.scores:
            if not isinstance(other_score, dict):
                continue
            benchmark_id = other_score.get('benchmark_type_id')
            if not benchmark_id:
                continue
            score_value = other_score.get('score_ceiled')
            if score_value in ('', 'X', None):
                continue
            try:
                score_float = float(score_value)
                if benchmark_id not in benchmark_scores:
                    benchmark_scores[benchmark_id] = []
                benchmark_scores[benchmark_id].append(score_float)
            except (ValueError, TypeError):
                continue

    # Compute statistics for each score
    for score in model.scores:
        if not isinstance(score, dict):
            continue

        benchmark_id = score.get('benchmark_type_id')
        if not benchmark_id:
            continue

        score_value = score.get('score_ceiled')

        # Compute color using same logic as JavaScript client-side
        if score_value not in ('', 'X', None):
            try:
                score_float = float(score_value)
                all_scores = benchmark_scores.get(benchmark_id, [])
                if all_scores:
                    min_score = min(all_scores)
                    max_score = max(all_scores)

                    # Determine if this is an engineering benchmark
                    root_parent = score.get('benchmark', {}).get('root_parent', '')
                    is_engineering = 'engineering' in root_parent.lower() if root_parent else False

                    # Calculate color using JavaScript logic (returns rgba string)
                    color_rgba = calculate_representative_color(
                        score_float, min_score, max_score, is_engineering
                    )
                    score['color'] = f'background-color: {color_rgba}'
                else:
                    score['color'] = f'background-color: {COLOR_NONE}'
            except (ValueError, TypeError):
                score['color'] = f'background-color: {COLOR_NONE}'
        else:
            score['color'] = f'background-color: {COLOR_NONE}'

        # Compute best and median from all public model scores
        all_scores = benchmark_scores.get(benchmark_id, [])
        if all_scores:
            score['best'] = max(all_scores)
            score['median'] = np.median(all_scores)
        else:
            score['best'] = 0
            score['median'] = 0


def calculate_representative_color(value, min_value, max_value, is_engineering):
    """
    Calculate representative color for a score value.
    Replicates the JavaScript calculateRepresentativeColor function.

    Args:
        value: The score value
        min_value: Minimum value in the distribution
        max_value: Maximum value in the distribution
        is_engineering: Whether this is an engineering benchmark (uses grayscale)

    Returns:
        CSS color string with RGBA (e.g., 'rgba(255, 0, 0, 0.85)')
    """
    # Normalize the input value between 0 and 1
    if max_value - min_value == 0:
        normalized_value = 0.5
    else:
        normalized_value = (value - min_value) / (max_value - min_value)
    normalized_value = max(0.0, min(1.0, normalized_value))

    # Apply gamma correction to emphasize differences at the top-end
    normalized_value = normalized_value ** (1.0 / GAMMA)

    # Scale down the normalized value (0.8 factor)
    normalized_value = 0.8 * normalized_value
    normalized_value = max(0.0, min(1.0, normalized_value))

    # Get color array index (0-100)
    idx = int(100 * normalized_value)
    if idx > 100:
        idx = 100

    # Determine color palette based on benchmark type
    color_hex = GRAY_COLORS[idx] if is_engineering else REDGREEN_COLORS[idx]

    # Extract RGB values from hex color
    r = int(color_hex[1:3], 16)
    g = int(color_hex[3:5], 16)
    b = int(color_hex[5:7], 16)

    # Calculate alpha based on value position
    # Linear interpolation: alpha ranges from 0.1 (at min) to 1.0 (at max)
    if max_value - min_value == 0:
        alpha = 1.0
    else:
        slope = -0.9 / (min_value - max_value)
        intercept = 0.1 - slope * min_value
        alpha = slope * value + intercept
    alpha = max(0.0, min(1.0, alpha))

    # Return RGBA color string
    return f'rgba({r}, {g}, {b}, {alpha:.2f})'


def view(request, id: int, domain: str):
    start_time = time()
    # Check if user is logged in
    user = request.user if request.user.is_authenticated else None

    # Try to get model object
    try:
        model_obj = FinalModelContext.objects.get(model_id=id, domain=domain)
        # Check if user has permission to view this model
        if not model_obj.public:
            if not user:
                # Anonymous users can see private models with redacted info
                pass
            elif not user.is_superuser:
                # Regular users can see private models if they own them
                model_owner_id = model_obj.user.get('id') if isinstance(model_obj.user, dict) else getattr(model_obj.user, 'id', None)
                if model_owner_id != user.id:
                    # User is not the owner, but can still see with redacted info
                    pass

        # Get context for model cards - always use global public context for consistent ranking
        context = get_context(user=None, domain=domain, show_public=True)
        # The public models are now cached within the user context
        public_models = context.get('public_models', context['models']) if user else context['models']
        # Determine if submission details should be visible (in most/possible all cases, owner == submitter, and therefore, this can be condensed)
        is_owner = False
        if user and model_obj.user:
            if isinstance(model_obj.user, dict):
                is_owner = user.id == model_obj.user.get('id')
            else:
                is_owner = user.id == model_obj.user.id
        is_submitter = False
        if user and model_obj.submitter:
            if isinstance(model_obj.submitter, dict):
                is_submitter = user.id == model_obj.submitter.get('id')
            else:
                is_submitter = user.id == model_obj.submitter.id
        submission_details_visible = user and (user.is_superuser or is_owner or is_submitter)
        # Get the visibility level for this model
        visibility = get_visibility(model_obj, user)
        # Try to find the model in the context
        filtered_models = [model for model in context['models'] if model.model_id == id]

        # The below is used to make use of get_context caching and provides a fallback in case returned cache is missing data
        if filtered_models:
            # Found in context, use this for complete data
            model = filtered_models[0]
        else:
            # Not found in context, use the database object
            model = model_obj

        # Enrich scores with full benchmark metadata for model detail page
        # (Materialized view optimization removed benchmark objects from scores)
        enrich_model_scores_with_benchmarks(model, context['benchmarks'])

        # Include current model in statistics calculation for consistency with leaderboard
        # (Ensures min/max values match what's shown in leaderboard grid)
        models_for_stats = public_models if model in public_models else public_models + [model]

        # Compute statistics (color, best, median) for visualization
        compute_score_statistics(model, models_for_stats)

        # Add per-benchmark ranking information using public models
        if hasattr(model, 'scores') and model.scores:
            try:
                add_benchmark_rankings(model, {'models': models_for_stats})
            except ValueError:
                pass

        # Build benchmark lookup map for template filters (keyed by versioned identifier)
        benchmark_lookup = {}
        for bench in context.get('benchmarks', []):
            # Get parent identifier if parent exists
            parent_id = None
            if hasattr(bench, 'parent') and bench.parent:
                if isinstance(bench.parent, dict):
                    parent_id = bench.parent.get('identifier')
                else:
                    parent_id = getattr(bench.parent, 'identifier', None)

            # Build combined meta from the three meta fields
            meta = {}
            data_meta = getattr(bench, 'benchmark_data_meta', None) or {}
            stimuli_meta = getattr(bench, 'benchmark_stimuli_meta', None) or {}
            if isinstance(data_meta, dict):
                if data_meta.get('num_recording_sites'):
                    meta['number_of_recording_sites'] = data_meta['num_recording_sites']
                if data_meta.get('region'):
                    meta['recording_sites'] = data_meta['region']
                if data_meta.get('task'):
                    meta['behavioral_task'] = data_meta['task']
            if isinstance(stimuli_meta, dict):
                if stimuli_meta.get('num_stimuli'):
                    meta['number_of_stimuli'] = stimuli_meta['num_stimuli']

            benchmark_lookup[bench.identifier] = {
                'short_name': bench.short_name,
                'version': bench.version,
                'url': getattr(bench, 'benchmark_url', None),
                'bibtex': getattr(bench, 'benchmark_bibtex', None),
                'depth': bench.depth,
                'number_of_all_children': bench.number_of_all_children,
                'benchmark_type_id': bench.benchmark_type_id,
                'parent_identifier': parent_id,
                'meta': meta if meta else None,
            }
        # Score / rank trend plots (trendMeta for sidebar lives inside plot JSON)
        score_trend_plot_json = _load_and_build_score_trend(
            model.model_id, context['benchmarks'], context['models'], domain
        )
        rank_trend_plot_json = _load_and_build_rank_trend(
            model.model_id, domain, focal_is_public=bool(getattr(model_obj, 'public', False)),
        )
        _score_tm = (score_trend_plot_json or {}).get('trendMeta') or {}
        _rank_tm = (rank_trend_plot_json or {}).get('trendMeta') or {}
        score_trend_sidebar_lines = _score_tm.get('defaultLines') or []
        rank_trend_sidebar_lines = _rank_tm.get('defaultLines') or []

        # Prepare the context for the template
        model_context = {
            'model': model,
            'benchmark_parents': context['benchmark_parents'],
            'uniform_parents': context['uniform_parents'],
            'not_shown_set': context['not_shown_set'],
            'BASE_DEPTH': context['BASE_DEPTH'],
            'domain': domain,
            'submission_details_visible': submission_details_visible,
            'has_user': user is not None,
            'user': user,
            'visibility': visibility,
            'model_name': display_model(model_obj, user),
            'submitter_name': display_submitter(model_obj, user),
            'visual_degrees': model.visual_degrees,
            'layers': getattr(model, 'layers', None),
            'benchmark_lookup': benchmark_lookup,
            'score_trend_plot_json': score_trend_plot_json,
            'rank_trend_plot_json': rank_trend_plot_json,
            'score_trend_sidebar_lines': score_trend_sidebar_lines,
            'rank_trend_sidebar_lines': rank_trend_sidebar_lines,
        }
        # Set thread-local benchmark lookup for template filters
        _thread_locals.benchmark_lookup = benchmark_lookup

        _logger.debug("model context build time: %.3fs", time() - start_time)
        return render(request, 'benchmarks/model.html', model_context)
    except FinalModelContext.DoesNotExist:
        raise Http404("Model not found")

# Generate per-benchmark rankings for a model
# This should be moved to database materialized view in future
def add_benchmark_rankings(model, reference_context):
    """
    Add per-benchmark ranking information to each score in the model.
    For both public and private models: compute rank against public models + self
    """
    # Get all public models for comparison
    public_models = [m for m in reference_context['models'] if getattr(m, 'public', True)]
    # Pre-compute scores for each benchmark to avoid repeated lookups
    benchmark_scores = {}
    for other_model in public_models + [model]:
        if getattr(other_model, 'model_id', None) == getattr(model, 'model_id', None):
            continue
        for other_score in getattr(other_model, 'scores', []) or []:
            if not isinstance(other_score, dict):
                continue
            versioned_id = other_score.get('versioned_benchmark_identifier')
            if not versioned_id:
                continue
            score_value = other_score.get('score_ceiled')
            if score_value in ('', 'X', None):
                continue
            try:
                score_float = float(score_value)
                if versioned_id not in benchmark_scores:
                    benchmark_scores[versioned_id] = []
                benchmark_scores[versioned_id].append(score_float)
            except (ValueError, TypeError):
                continue
    # Process scores
    for score in model.scores:
        if not isinstance(score, dict):
            continue
        versioned_benchmark_id = score.get('versioned_benchmark_identifier')
        if not versioned_benchmark_id:
            continue
        # If score is invalid, set rank to be same as invalid score
        # i.e., if score is empty, rank is empty. If score is "X", rank is "X", if score is nan, rank is nan
        # Allows us to preserve invalid state in the rank and avoid casting invalid score to float
        score_ceiled = score.get('score_ceiled')
        if score_ceiled in ('', 'X', None):
            score['rank'] = score_ceiled
            continue
        try:
            score_value = float(score_ceiled)
            all_scores = benchmark_scores.get(versioned_benchmark_id, [])
            # Sort scores in descending order and find the rank
            sorted_scores = sorted(all_scores, reverse=True)
            # Find the position of the current score (1-indexed)
            # If there are ties, all tied scores get the same rank
            rank = 1
            for i, s in enumerate(sorted_scores):
                if s > score_value:
                    rank = i + 2  # +2 because we want 1-indexed and we're looking for the next position
                elif s == score_value:
                    rank = i + 1  # +1 for 1-indexed
                    break
            score['rank'] = rank
        except (ValueError, TypeError):
            score['rank'] = 'N/A'


def simplify_score(score):
    try:
        return float(score)
    except ValueError:  # score is '', 'X', or nan
        return 0


@register.filter
def score_style(score_ceiled):
    if not score_ceiled or score_ceiled == '' or score_ceiled == 'X':
        return score_ceiled
    try:
        return 100 * float(score_ceiled)
    except (ValueError, TypeError):
        return score_ceiled


def _get_benchmark_data(score_row, field, default=None):
    """
    Helper to get benchmark field from score_row.
    First tries score_row['benchmark'][field] (embedded data).
    Falls back to thread-local benchmark_lookup using versioned_benchmark_identifier.
    """
    if isinstance(score_row, dict):
        # Try embedded benchmark data first
        benchmark = score_row.get('benchmark', {})
        if field in benchmark and benchmark[field] is not None:
            return benchmark[field]

        # Fall back to thread-local lookup
        versioned_id = score_row.get('versioned_benchmark_identifier')
        if versioned_id:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(versioned_id, {})
            return benchmark_data.get(field, default)

    # Handle namedtuple/object case
    if hasattr(score_row, 'benchmark'):
        return getattr(score_row.benchmark, field, default)

    return default


@register.filter
def is_parent(score_row_or_benchmark):
    """Check if benchmark has children. Accepts score_row or benchmark dict."""
    if isinstance(score_row_or_benchmark, dict):
        # If it's a score_row dict, get the children count via lookup
        versioned_id = score_row_or_benchmark.get('versioned_benchmark_identifier')
        if versioned_id:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(versioned_id, {})
            return benchmark_data.get('number_of_all_children', 0) > 0

        # If it's a benchmark dict directly, check embedded children
        children = score_row_or_benchmark.get('children')
        if children is not None:
            return len(children) > 0

        # Fall back to lookup using identifier
        identifier = score_row_or_benchmark.get('identifier')
        if identifier:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(identifier, {})
            return benchmark_data.get('number_of_all_children', 0) > 0
        return False
    return hasattr(score_row_or_benchmark, 'children') and len(score_row_or_benchmark.children) > 0


@register.filter
def should_hide(score_row_or_benchmark):
    """Check if benchmark should be hidden based on depth and identifier. Accepts score_row or benchmark dict."""
    if isinstance(score_row_or_benchmark, dict):
        # If it's a score_row dict, get depth and type via lookup
        versioned_id = score_row_or_benchmark.get('versioned_benchmark_identifier')
        if versioned_id:
            lookup = getattr(_thread_locals, 'benchmark_lookup', {})
            benchmark_data = lookup.get(versioned_id, {})
            depth = benchmark_data.get('depth', 0)
            benchmark_type_id = benchmark_data.get('benchmark_type_id', '')
            return depth >= 1 or benchmark_type_id.startswith('engineering')

        # If it's a benchmark dict directly
        depth = score_row_or_benchmark.get('depth')
        benchmark_type_id = score_row_or_benchmark.get('benchmark_type_id', '')

        # Fall back to lookup if not embedded
        if depth is None:
            identifier = score_row_or_benchmark.get('identifier')
            if identifier:
                lookup = getattr(_thread_locals, 'benchmark_lookup', {})
                benchmark_data = lookup.get(identifier, {})
                depth = benchmark_data.get('depth', 0)
                benchmark_type_id = benchmark_data.get('benchmark_type_id', '')
            else:
                depth = 0

        return depth >= 1 or benchmark_type_id.startswith('engineering')
    return score_row_or_benchmark.depth >= 1 or score_row_or_benchmark.benchmark_type_id.startswith('engineering')


@register.filter
def get_benchmark_short_name(score_row):
    """Get benchmark short name from score row dictionary"""
    return _get_benchmark_data(score_row, 'short_name', '')


@register.filter
def get_benchmark_version(score_row):
    """Get benchmark version from score row dictionary"""
    return _get_benchmark_data(score_row, 'version')


@register.filter
def get_benchmark_url(score_row):
    """Get benchmark URL from score row dictionary"""
    return _get_benchmark_data(score_row, 'url')


@register.filter
def get_benchmark_type_id(score_row):
    """Get benchmark type ID from score row dictionary"""
    return _get_benchmark_data(score_row, 'benchmark_type_id')


@register.filter
def get_benchmark_children_count(score_row):
    """Get number of children from score row dictionary"""
    return _get_benchmark_data(score_row, 'number_of_all_children', 0)


@register.filter
def scores_bibtex(scores):
    """Get unique bibtex entries from scores, using thread-local benchmark lookup."""
    bibtexs = []
    lookup = getattr(_thread_locals, 'benchmark_lookup', {})

    for score_row in scores:
        if isinstance(score_row, dict):
            if not score_row.get('score_ceiled'):
                continue

            # Try embedded bibtex first
            bibtex = score_row.get('benchmark', {}).get('bibtex')

            # Fall back to lookup
            if not bibtex:
                versioned_id = score_row.get('versioned_benchmark_identifier')
                if versioned_id:
                    benchmark_data = lookup.get(versioned_id, {})
                    bibtex = benchmark_data.get('bibtex')

            if bibtex:
                bibtexs.append(bibtex.strip())
        else:  # namedtuple
            if hasattr(score_row, 'score_ceiled') and score_row.score_ceiled and \
               hasattr(score_row, 'benchmark') and hasattr(score_row.benchmark, 'benchmark_type') and \
               score_row.benchmark.benchmark_type.reference:
                bibtex = score_row.benchmark.benchmark_type.reference.bibtex
                bibtex = bibtex.strip().strip('﻿')
                bibtexs.append(bibtex)

    # filter unique, maintain order
    if bibtexs:
        _, idx = np.unique(bibtexs, return_index=True)
        bibtexs = np.array(bibtexs)[np.sort(idx)]
    return bibtexs


@register.filter
def get_benchmark_depth(score_row):
    """Get benchmark depth from score row dictionary"""
    return _get_benchmark_data(score_row, 'depth', 0)


@register.filter
def get_score_color(score_row):
    """Get color style from score row dictionary"""
    return score_row.get('color', '')


@register.filter
def get_score_ceiled(score_row):
    """Get ceiled score from score row dictionary"""
    return score_row.get('score_ceiled', '')


@register.filter
def cap_score(value):
    """
    Cap a score value between 0 and 1 inclusive.
    Handles string values like '.415' or '1.1' as well as floats.
    Non-numeric values (like 'X' or '') are returned unchanged.
    """
    if value in ('', 'X', None):
        return value
    try:
        num = float(value)
        capped = max(0.0, min(1.0, num))
        # Preserve the original formatting style (leading dot for < 1)
        if capped < 1:
            # Format to 3 decimal places, strip leading zero
            return f'{capped:.3f}'.lstrip('0') or '0'
        else:
            return '1.0'
    except (ValueError, TypeError):
        return value


@register.filter
def get_score_best(score_row):
    """Get best score from score row dictionary"""
    try:
        return float(score_row.get('best', 0)) * 100  # Convert to percentage
    except (ValueError, TypeError):
        return 0

@register.filter
def get_score_median(score_row):
    """Get median score from score row dictionary"""
    try:
        return float(score_row.get('median', 0)) * 100  # Convert to percentage
    except (ValueError, TypeError):
        return 0

# Database returns layers in alphabetical order, so reorder them in specific sequence
@register.filter
def order_layers(layers_dict):
    """Order layers in the specific sequence: V1, V2, V4, IT"""
    if not layers_dict:
        return []
    # Define the desired order
    desired_order = ['V1', 'V2', 'V4', 'IT']
    # Create a list to store ordered items
    ordered_items = []
    # First add items in the desired order
    for key in desired_order:
        if key in layers_dict:
            ordered_items.append((key, layers_dict[key]))
    # Then add any remaining items that weren't in the desired order
    for key, value in layers_dict.items():
        if key not in desired_order:
            ordered_items.append((key, value))
    return ordered_items

@register.filter
def has_valid_score(score_row):
    """Check if the score row has a valid score (not X or empty)"""
    score = score_row.get('score_ceiled', '')
    return score and score != "X"


@register.filter
def get_benchmark_parent_identifier(score_row):
    """Get parent benchmark identifier from score row dictionary"""
    return _get_benchmark_data(score_row, 'parent_identifier')


@register.filter
def get_benchmark_meta(score_row):
    """Get benchmark meta dict from score row dictionary"""
    return _get_benchmark_data(score_row, 'meta')


@register.filter
def get_benchmark_meta_field(score_row, field):
    """Get specific field from benchmark meta"""
    meta = _get_benchmark_data(score_row, 'meta')
    if meta and isinstance(meta, dict):
        return meta.get(field)
    return None
