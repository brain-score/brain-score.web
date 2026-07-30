"""Historical score / rank trend analysis for the model card and compare pages."""
import logging
import threading
import time
from datetime import date

import numpy as np
import pandas as pd

from ..models import Model, ModelMonthlyAggregate, MonthBenchmarkEdge, Score

_logger = logging.getLogger(__name__)


# Keyed on (kind, domain, max-month) so a new month naturally invalidates.
_TREND_CACHE = {}
_TREND_CACHE_LOCK = threading.Lock()

# Hover list cap for new-leaf / coverage-completion bullets on the model card.
_COVERAGE_BULLET_CAP = 12

# The max-month lookup runs on every cache access; memoize it briefly so a
# single page render (which touches several loaders) hits the DB once, not once
# per loader. A new month is picked up within the TTL; recompute clears it.
_MAX_MONTH_TTL_SECONDS = 60
_max_month_memo = {}  # domain -> (max_month, expires_at)


def _trend_cache_key(domain):
    now = time.time()
    hit = _max_month_memo.get(domain)
    if hit is not None and hit[1] > now:
        return hit[0]
    max_month = (ModelMonthlyAggregate.objects
                 .filter(domain=domain)
                 .order_by('-month')
                 .values_list('month', flat=True)
                 .first())
    _max_month_memo[domain] = (max_month, now + _MAX_MONTH_TTL_SECONDS)
    return max_month


def _trend_cache_get(kind, domain):
    max_month = _trend_cache_key(domain)
    return _TREND_CACHE.get((kind, domain, max_month)), max_month


def _trend_cache_put(kind, domain, max_month, value):
    with _TREND_CACHE_LOCK:
        for k in list(_TREND_CACHE):
            if k[0] == kind and k[1] == domain:
                del _TREND_CACHE[k]
        _TREND_CACHE[(kind, domain, max_month)] = value


def clear_trend_cache():
    """Per-process bust. Same-month recomputes don't change ``max(month)`` so
    natural invalidation doesn't fire; multi-worker deploys need a cross-worker
    strategy (cache-version row, Redis pub/sub)."""
    with _TREND_CACHE_LOCK:
        _TREND_CACHE.clear()
    _max_month_memo.clear()


def _load_month_benchmark_edges(domain='vision'):
    """Maps ``'YYYY-MM|YYYY-MM' -> [leaf_ids]`` newly eligible between the pair."""
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
    cached, max_month = _trend_cache_get('all_months', domain)
    if cached is not None:
        return cached
    months = sorted({m for m in ModelMonthlyAggregate.objects
                     .filter(domain=domain)
                     .values_list('month', flat=True).distinct()})
    _trend_cache_put('all_months', domain, max_month, months)
    return months


def _load_public_wide_scores(domain):
    """``model_id`` column + one ``YYYY-MM`` column per month, public models only."""
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


def _load_public_rank_df(domain):
    """Cached public-only rank frame (same index as ``_load_public_wide_scores``).
    Recomputed only when a new month lands; the model card would otherwise rebuild
    the full model x month rank matrix on every page load."""
    cached, max_month = _trend_cache_get('public_rank', domain)
    if cached is not None:
        return cached.copy(), max_month
    public_wide, _ = _load_public_wide_scores(domain)
    month_cols = [c for c in public_wide.columns if c != 'model_id']
    if not month_cols:
        rank_df = public_wide[['model_id']].copy()
    else:
        _, rank_df = wide_scores_and_rank_df(public_wide, month_cols)
    _trend_cache_put('public_rank', domain, max_month, rank_df)
    return rank_df.copy(), max_month


def _load_model_names(domain):
    """``{model_id: name}`` for all models in the domain."""
    cached, max_month = _trend_cache_get('names', domain)
    if cached is not None:
        return cached, max_month
    names = dict(Model.objects.filter(domain=domain).values_list('id', 'name'))
    _trend_cache_put('names', domain, max_month, names)
    return names, max_month


def _load_focal_coverage_deltas(model_id, domain):
    """``{'YYYY-MM': [leaf_ids]}`` of leaves the focal model newly scored on
    each month. Populated by ``recompute_score_trends``."""
    kind = f'focal_coverage:{model_id}'
    cached, max_month = _trend_cache_get(kind, domain)
    if cached is not None:
        return cached
    rows = (ModelMonthlyAggregate.objects
            .filter(model_id=model_id, domain=domain)
            .values_list('month', 'coverage_leaves_added_vs_prev'))
    result = {m: (leaves or []) for m, leaves in rows}
    _trend_cache_put(kind, domain, max_month, result)
    return result


def _month_end_utc_ts(month_str):
    """UTC ``pd.Timestamp`` for the last instant of ``YYYY-MM``. Used as the
    ``end_timestamp`` upper bound when asking whether a model was scored on
    a given benchmark by month M."""
    ts = pd.Timestamp(str(month_str) + '-01') + pd.offsets.MonthEnd(0)
    return ts.tz_localize('UTC')


def _load_focal_scored_new_leaves(model_id, domain, edges_map):
    """per-model, per-month cache of "of the leaves newly counted in the
    aggregate this month, which ones did this model actually get a nonzero
    non-NaN score on by month-end?"""
    kind = f'focal_scored_new:{model_id}'
    cached, max_month = _trend_cache_get(kind, domain)
    if cached is not None:
        return cached
    result = {}
    all_added = sorted({leaf for added in edges_map.values() for leaf in (added or [])}) if edges_map else []
    if all_added:
        # One query for every relevant leaf, then bucket per month in Python
        # (avoids one Score query per month-edge). ``score_ceiled__gt=0`` also
        # matches NaN in Postgres ordering, so the NaN guard stays.
        earliest = {}
        rows = (Score.objects
                .filter(model_id=model_id, benchmark__benchmark_type__identifier__in=all_added,
                        end_timestamp__isnull=False, score_ceiled__isnull=False, score_ceiled__gt=0)
                .values_list('benchmark__benchmark_type__identifier', 'score_ceiled', 'end_timestamp'))
        for ident, sc, ts in rows:
            if sc is None or (isinstance(sc, float) and np.isnan(sc)):
                continue
            if ident not in earliest or ts < earliest[ident]:
                earliest[ident] = ts
        for edge_key, added in edges_map.items():
            if not added:
                continue
            _prev, curr = edge_key.split('|', 1)
            month_end = _month_end_utc_ts(curr)
            scored = sorted({ident for ident in added
                             if ident in earliest and earliest[ident] <= month_end})
            if scored:
                result[curr] = scored
    _trend_cache_put(kind, domain, max_month, result)
    return result # -> {'YYYY-MM': [leaf_ids]}


def _load_new_models_by_month(domain):
    """``{'YYYY-MM': int}`` -> count of models entering the leaderboard each month
    (first non-zero MMA score lands in that month)."""
    cached, max_month = _trend_cache_get('new_models_by_month', domain)
    if cached is not None:
        return cached
    rows = list(ModelMonthlyAggregate.objects
                .filter(domain=domain, score__gt=0)
                .values_list('model_id', 'month'))
    if not rows:
        result = {}
    else:
        df = pd.DataFrame(rows, columns=['model_id', 'month'])
        first_month = df.groupby('model_id')['month'].min()
        result = {m: int(c) for m, c in first_month.value_counts().to_dict().items()}
    _trend_cache_put('new_models_by_month', domain, max_month, result)
    return result


def _edges_counts_by_curr_month(edges_map):
    return {key.split('|', 1)[1]: len(v or []) for key, v in edges_map.items()}


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


def _fmt_month(date_or_ym):
    """``'YYYY-MM'`` or a date string -> ``'Mon YYYY'`` (e.g. ``'Jan 2026'``)."""
    try:
        return pd.Timestamp(date_or_ym).strftime('%b %Y')
    except Exception:
        return _date_to_month_key(date_or_ym)


def _plural(n, noun):
    """``'1 model'`` / ``'2 models'`` (regular ``+s``)."""
    return f'{n} {noun}' if n == 1 else f'{n} {noun}s'


def _rank_move(prev_rank, curr_rank):
    """Human phrase for a rank change: ``'up 2'`` (improved) / ``'down 1'`` / ``'no change'``."""
    if curr_rank < prev_rank:
        return f'up {prev_rank - curr_rank}'
    if curr_rank > prev_rank:
        return f'down {curr_rank - prev_rank}'
    return 'no change'


def rank_transition_model_lines(model_id, ym_prev, ym_curr, rank1, rank2, rank_df):
    """One-line summary of *which models* drove a month-to-month rank move,
    counts only / third-person. Benchmark churn is shown separately (bullets),
    so it is intentionally not repeated here. Per-model enumeration was dropped
    because long model names widened the sidebar on narrow viewports."""
    if ym_prev not in rank_df.columns or ym_curr not in rank_df.columns:
        return []

    rank_change = rank2 - rank1
    focal = str(model_id)
    ranks_indexed = rank_df.set_index('model_id')
    ranks_t1 = ranks_indexed[ym_prev]
    ranks_t2 = ranks_indexed[ym_curr]

    moved_past = focal_past = new_above = 0
    for om in ranks_t1.index:
        if str(om) == focal:
            continue
        r1 = ranks_t1[om]
        r2 = ranks_t2.get(om, np.nan)
        if pd.isna(r1) or pd.isna(r2):
            continue
        or1, or2 = int(r1), int(r2)
        if rank_change > 0 and ((or1 > rank1 and or2 <= rank2) or (or1 >= rank1 and or2 < rank2)):
            moved_past += 1
        elif rank_change < 0 and ((or1 < rank1 and or2 >= rank2) or (or1 <= rank1 and or2 > rank2)):
            focal_past += 1
    for om in ranks_t2.index:
        if str(om) == focal:
            continue
        if pd.notna(ranks_t1.get(om, np.nan)) or pd.isna(ranks_t2[om]):
            continue
        if int(ranks_t2[om]) < rank2:
            new_above += 1

    bits = []
    if focal_past:
        bits.append(f'passed {_plural(focal_past, "model")}')
    if moved_past:
        bits.append(f'{_plural(moved_past, "model")} moved ahead')
    if new_above:
        bits.append(f'{_plural(new_above, "new model")} entered above')
    if not bits:
        return []
    s = '; '.join(bits) + '.'
    return [s[0].upper() + s[1:]]


def _overall_trend_lines(dates, values, kind):
    """Summary from first to last point (default sidebar + 'no change' branch)."""
    if not dates or not values:
        return ['No trend data.']
    n = len(dates)
    if kind == 'score':
        return [
            f'{_plural(n, "month")}, {values[0]:.3f} → {values[-1]:.3f} ({values[-1] - values[0]:+.3f} overall).',
            'Hover a point for month-by-month detail.',
        ]
    r0 = int(round(float(values[0])))
    r1 = int(round(float(values[-1])))
    return [
        f'{_plural(n, "month")}, rank {r0} → {r1} ({_rank_move(r0, r1)}).',
        'Hover a point for month-by-month detail.',
    ]


def _point_attribution_lines(i, dates, values, kind, edges_map, overall_lines, rank_explain=None):
    """Narrative for hover at index i vs previous point; uses benchmark-edge map when value changes."""
    if i == 0:
        if kind == 'score':
            head = [f'{_fmt_month(dates[0])}: {values[0]:.3f} (first month shown).']
        else:
            head = [f'{_fmt_month(dates[0])}: rank {int(round(float(values[0])))} (first month shown).']
        return head + overall_lines

    ym_prev = _date_to_month_key(dates[i - 1])
    ym_curr = _date_to_month_key(dates[i])
    edge_key = f'{ym_prev}|{ym_curr}'
    added = edges_map.get(edge_key, [])
    coverage_added = ((rank_explain or {}).get('coverage_deltas') or {}).get(ym_curr, []) or []
    scored_of_added = set(((rank_explain or {}).get('scored_new_deltas') or {}).get(ym_curr, []) or [])
    scored_of_added &= set(added)
    scored_of_added_count = len(scored_of_added)

    if kind == 'score':
        prev_v, curr_v = values[i - 1], values[i]
        delta = curr_v - prev_v
        unchanged = abs(delta) < 1e-9
        head = [f'{_fmt_month(ym_curr)}: {curr_v:.3f}, {delta:+.3f} vs {_fmt_month(ym_prev)}.']
    else:
        prev_v = int(round(float(values[i - 1])))
        curr_v = int(round(float(values[i])))
        delta = curr_v - prev_v
        unchanged = delta == 0
        head = [f'{_fmt_month(ym_curr)}: rank {curr_v}, {_rank_move(prev_v, curr_v)} from {_fmt_month(ym_prev)}.']

    if unchanged:
        if kind == 'score':
            return [f'{_fmt_month(ym_curr)}: {curr_v:.3f} (no change from {_fmt_month(ym_prev)}).'] + overall_lines
        return [f'{_fmt_month(ym_curr)}: rank {curr_v} (no change from {_fmt_month(ym_prev)}).'] + overall_lines

    out = list(head)
    model_lines = []
    if kind == 'rank' and rank_explain is not None:
        rdf = rank_explain.get('rank_df')
        mid_model = rank_explain.get('model_id')
        if rdf is not None and mid_model is not None and ym_prev in rdf.columns and ym_curr in rdf.columns:
            model_lines = rank_transition_model_lines(mid_model, ym_prev, ym_curr, prev_v, curr_v, rdf)
    out.extend(model_lines)

    cap = _COVERAGE_BULLET_CAP
    if coverage_added:
        if len(coverage_added) <= 3:
            out.append(f'Newly scored on {_plural(len(coverage_added), "benchmark")}: ' + ', '.join(coverage_added) + '.')
        else:
            out.append(f'Newly scored on {_plural(len(coverage_added), "benchmark")}:')
            for b in coverage_added[:cap]:
                out.append(f'- {b}')
            if len(coverage_added) > cap:
                out.append(f'... and {len(coverage_added) - cap} more.')

    if added:
        out.append(f'{_plural(len(added), "new benchmark")} added, scored on {scored_of_added_count} of {len(added)} (unscored count as 0):')
        for b in added[:cap]:
            out.append(f'- {b} ({"scored" if b in scored_of_added else "not run"})')
        if len(added) > cap:
            out.append(f'... and {len(added) - cap} more.')
    elif not coverage_added:
        if kind == 'score' or not model_lines:
            out.append('No new benchmarks this month; the change is from updated scores or other models in the pool.')
        else:
            out.append('No new benchmarks this month; the change is from score updates.')
    return out


def _build_trend_meta(dates, values, kind, edges_map, extra_default_lines=None, rank_explain=None):
    """``trendMeta`` payload consumed by ``model-score-trend.js``:
    ``defaultLines`` on idle, ``points[i].lines`` on hover."""
    base_overall = _overall_trend_lines(dates, values, kind)
    default_lines = base_overall + list(extra_default_lines or [])
    points = []
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


# Shared Plotly layout pieces so the single-model and compare charts stay in
# sync (same axes, grid handling, and modebar) with only their distinct bits
# -- height, margin, legend, trace -- set per builder.
def _trend_grid_template():
    # Plotly 3's default template re-enables grids unless explicitly disabled.
    return {'layout': {
        'xaxis': {'showgrid': False, 'zeroline': False, 'minor': {'showgrid': False}},
        'yaxis': {'showgrid': False, 'zeroline': False, 'minor': {'showgrid': False}},
    }}


def _trend_xaxis(range_start, range_end):
    return {
        'title': {'text': 'Date', 'font': {'size': 12}},
        'type': 'date', 'tickformat': '%b %Y',
        'fixedrange': True, 'autorange': False,
        'range': [range_start, range_end],
        'showgrid': False, 'zeroline': False,
        'gridcolor': 'rgba(0,0,0,0)', 'minor': {'showgrid': False},
        'showline': True, 'linecolor': '#dbdbdb', 'mirror': False,
    }


def _trend_yaxis(title, y_range):
    return {
        'title': {'text': title, 'font': {'size': 12}},
        'fixedrange': True, 'autorange': False,
        'range': y_range,
        'showgrid': False, 'zeroline': False,
        'gridcolor': 'rgba(0,0,0,0)', 'minor': {'showgrid': False},
        'showline': True, 'linecolor': '#dbdbdb',
    }


def _trend_plot_config():
    return {
        'responsive': True, 'displayModeBar': True, 'scrollZoom': False,
        'modeBarButtonsToRemove': ['zoomIn2d', 'zoomOut2d', 'zoom2d', 'pan2d', 'select2d', 'lasso2d', 'autoScale2d'],
    }


def _build_trend_plot_json(dates, ys, kind, range_start, range_end, shade_region=None):
    """Plotly JSON for a single-model trend. ``kind`` is ``'score'`` or ``'rank'``;
    rank reverses the y-axis so rank 1 sits at the top."""
    if kind == 'score':
        y_min, y_max = min(ys), max(ys)
        padding = max(0.05, (y_max - y_min) * 0.1) if y_max > y_min else 0.05
        # No upper clamp: ceiling-near scores must not sit flush against the top edge.
        y_range = [max(0, y_min - padding), y_max + padding]
        y_range_dp = 6
        y_title = 'Score'
        trace_name = 'average_vision'
        hover_fmt = 'Score: %{y:.4f}'
    else:
        valid = [r for r in ys if r is not None and (not isinstance(r, float) or not np.isnan(r))]
        if not valid:
            valid = [1]
        rank_max, rank_min = max(valid), min(valid)
        padding = max(1, (rank_max - rank_min) * 0.1) if rank_max > rank_min else 1
        # Reversed so rank 1 is at the top; no clamp at 1 keeps the top line off the edge.
        y_range = [rank_max + padding, rank_min - padding]
        y_range_dp = 2
        y_title = 'Rank (1 = best)'
        trace_name = 'rank'
        hover_fmt = 'Rank: %{y:.0f}'

    range_start, range_end = _pad_date_range(range_start, range_end)
    shapes = []
    if shade_region and len(shade_region) == 2:
        x0, x1 = shade_region
        shapes.append({
            'type': 'rect', 'xref': 'x', 'yref': 'paper',
            'x0': x0, 'x1': x1, 'y0': 0, 'y1': 1,
            'fillcolor': 'rgba(50, 115, 220, 0.06)',
            'line': {'width': 0}, 'layer': 'below',
        })
    shapes.append({
        'type': 'line', 'xref': 'x', 'yref': 'paper',
        'x0': dates[-1], 'x1': dates[-1], 'y0': 0, 'y1': 1,
        'line': {'color': 'rgba(72, 72, 72, 0.35)', 'width': 1, 'dash': 'dot'},
        'layer': 'below',
    })
    annotations = [{
        'x': dates[-1], 'y': ys[-1], 'text': 'Latest',
        'showarrow': True, 'arrowhead': 2, 'arrowsize': 0.6, 'arrowwidth': 1,
        'arrowcolor': '#3273dc', 'ax': 0, 'ay': -36,
        'bgcolor': 'rgba(255, 255, 255, 0.92)',
        'bordercolor': '#3273dc', 'borderwidth': 1,
        'font': {'size': 11, 'color': '#363636'},
    }]
    if len(dates) > 1:
        annotations.append({
            'x': dates[0], 'y': ys[0], 'text': 'Start',
            'showarrow': True, 'arrowhead': 2, 'arrowsize': 0.5, 'arrowwidth': 1,
            'arrowcolor': '#7a7a7a', 'ax': 0, 'ay': 32,
            'bgcolor': 'rgba(255, 255, 255, 0.9)',
            'bordercolor': '#dbdbdb', 'borderwidth': 1,
            'font': {'size': 10, 'color': '#4a4a4a'},
        })
    customdata = [[i] for i in range(len(dates))]
    return {
        'data': [{
            'x': dates, 'y': ys, 'type': 'scatter', 'mode': 'lines',
            'hoveron': 'points', 'name': trace_name, 'customdata': customdata,
            'line': {'color': '#3273dc', 'width': 2.5, 'shape': 'spline', 'smoothing': 1.3},
            'hovertemplate': '<b>%{x|%d %b %Y}</b><br>' + hover_fmt + '<extra></extra>',
        }],
        'layout': {
            'height': 400, 'autosize': True,
            'paper_bgcolor': '#ffffff', 'plot_bgcolor': '#ffffff',
            'margin': {'t': 8, 'r': 8, 'b': 44, 'l': 48},
            'shapes': shapes, 'annotations': annotations, 'hovermode': 'closest',
            'template': _trend_grid_template(),
            'xaxis': _trend_xaxis(range_start, range_end),
            'yaxis': _trend_yaxis(y_title, [round(y_range[0], y_range_dp), round(y_range[1], y_range_dp)]),
            'showlegend': False,
        },
        'config': _trend_plot_config(),
    }


def _pad_date_range(range_start, range_end):
    """Extend a date range so endpoint markers don't sit flush against the chart
    edges. ~3% of the span, floored to 7 days. Returns input unchanged on parse failure."""
    try:
        ts0 = pd.Timestamp(range_start)
        ts1 = pd.Timestamp(range_end)
        span_days = max(1, (ts1 - ts0).days)
        pad = pd.Timedelta(days=max(7, span_days // 30))
        return (ts0 - pad).strftime('%Y-%m-%d'), (ts1 + pad).strftime('%Y-%m-%d')
    except Exception:
        return range_start, range_end


def _monthly_dates_until_today(last_date_str):
    """Month-end dates between ``last_date_str + 1mo`` and today, with today appended if later."""
    last_ts = pd.Timestamp(last_date_str)
    today_ts = pd.Timestamp(date.today())
    out = []
    cur = last_ts + pd.offsets.MonthBegin(1)
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


def wide_scores_and_rank_df(df, month_cols):
    """Wide ``model_id × month`` score frame + same-shape rank frame (1 = best,
    ties skip).

    Score rounding mirrors the leaderboard's two-pass HALF_UP exactly: the MV
    pre-rounds to 3dp via PostgreSQL ``ROUND(numeric, 3)`` ([mv.sql:1076]),
    then ``_rank_models`` rounds to 2dp HALF_UP. A one-shot 2dp on the raw
    float disagrees on values just under ``.xx5`` (e.g. ``0.3849...``)."""
    wide_scores = df[['model_id'] + month_cols].copy()
    for col in month_cols:
        s = wide_scores[col].replace(0.0, np.nan).astype(float)
        # floor(x*N + 0.5)/N = ROUND_HALF_UP for x >= 0; NaN propagates.
        s_3dp = np.floor(s * 1000 + 0.5) / 1000
        wide_scores[col] = np.floor(s_3dp * 100 + 0.5) / 100
    rank_df = wide_scores[['model_id']].copy()
    for col in month_cols:
        # method='min' is competition ranking (1, 2, 2, 4, ...), which already
        # matches the leaderboard's tie handling; no remap needed.
        rank_df[col] = wide_scores[col].rank(method='min', ascending=False, na_option='keep')
    return wide_scores, rank_df


def load_and_build_score_trend(model_id, domain):
    """Score-over-time trend; vision domain only for now."""
    if domain != 'vision':
        return None
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
        start_idx = next((i for i, v in enumerate(valid.values) if v > 0), 0)
        series = valid.iloc[start_idx:]
        if series.empty:
            return None
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
        # Carry the last known value forward to today so the line has monthly dots.
        today_str = date.today().strftime('%Y-%m-%d')
        shade_region = None
        if dates[-1] < today_str:
            extra_dates = _monthly_dates_until_today(dates[-1])
            if extra_dates:
                shade_region = (extra_dates[0], today_str)
                dates = list(dates) + extra_dates
                scores = list(scores) + [scores[-1]] * len(extra_dates)
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
        plot_json = _build_trend_plot_json(dates, scores, 'score', range_start, range_end, shade_region=shade_region)
        plot_json['trendMeta'] = _build_trend_meta(
            dates, scores, 'score', edges, extra_default_lines=extra_default,
            rank_explain={'coverage_deltas': _load_focal_coverage_deltas(model_id, domain),
                'scored_new_deltas': _load_focal_scored_new_leaves(model_id, domain, edges),
            },
        )
        return plot_json
    except Exception:
        _logger.exception('score trend build failed for model %s domain %s', model_id, domain)
        return None


def load_and_build_rank_trend(model_id, domain, focal_is_public=True):
    """Rank-over-time trend; vision domain only for now.

    Private focal models are spliced into the public-only frame so they get a
    rank against the public pool without ever appearing as named entries
    elsewhere -- the focal-exclusion in ``rank_transition_model_lines`` plus
    other private models simply not being in the frame keeps it safe."""
    if domain != 'vision':
        return None
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
        if focal_is_public:
            # df is public_wide unchanged -> reuse the cached rank frame.
            rank_df, _ = _load_public_rank_df(domain)
        else:
            _wide_scores, rank_df = wide_scores_and_rank_df(df, month_cols)
        model_idx = row.index[0]
        series = rank_df.loc[model_idx, month_cols]
        valid = series.dropna()
        if valid.empty:
            return None
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
        pairs = [(d, r) for d, r in zip(dates, ranks_out) if r is not None]
        if not pairs:
            return None
        dates, ranks_out = zip(*pairs)
        dates = list(dates)
        ranks_out = list(ranks_out)
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
        plot_json = _build_trend_plot_json(dates, ranks_out, 'rank', range_start, range_end, shade_region=shade_region)
        plot_json['trendMeta'] = _build_trend_meta(
            dates, ranks_out, 'rank', edges,
            extra_default_lines=extra_default,
            rank_explain={
                'model_id': model_id,
                'rank_df': rank_df,
                'coverage_deltas': _load_focal_coverage_deltas(model_id, domain),
                'scored_new_deltas': _load_focal_scored_new_leaves(model_id, domain, edges),
            },
        )
        return plot_json
    except Exception:
        _logger.exception('rank trend build failed for model %s domain %s', model_id, domain)
        return None


# Matches ``compare_models.js`` Chart 3 (split violin) so A/B stay color-coded
# consistently across all comparison charts on the page.
_COMPARE_COLOR_A = '#45C676'  # green -- Model A
_COMPARE_COLOR_B = '#47B7DE'  # cyan  -- Model B
# Truncated label for the in-chart legend; full names stay in the sidebar.
_COMPARE_LEGEND_NAME_MAX = 28
# Sidebar text cap: sidebar column is narrower than the legend space, and each
# hover line prepends the model name (twice, on rank/score lines). Long
# identifiers like ``fixres_resnext101_32x48d_wsl`` overflow past ~22 chars.
_COMPARE_SIDEBAR_NAME_MAX = 22
# Hover-list cap for compare-page coverage bullets; tighter than the model-card
# cap because two parallel lists already double the visual weight.
_COMPARE_COVERAGE_BULLET_CAP = 8


def _truncate_legend_name(name):
    if not name or len(name) <= _COMPARE_LEGEND_NAME_MAX:
        return name
    return name[: _COMPARE_LEGEND_NAME_MAX - 3] + '...'


def _truncate_sidebar_name(name):
    """Shorter than the legend cap: sidebar lines prepend the name on every
    row, so long identifiers reflow the narrow column."""
    if not name or len(name) <= _COMPARE_SIDEBAR_NAME_MAX:
        return name
    return name[: _COMPARE_SIDEBAR_NAME_MAX - 3] + '...'


def _load_comparison_rank_df(mid_a, mid_b, domain):
    """Build the rank table needed to explain why a model’s rank changed."""
    public_wide, _ = _load_public_wide_scores(domain)
    month_cols = [c for c in public_wide.columns if c != 'model_id']
    if not month_cols:
        return None
    df = public_wide
    for mid in (mid_a, mid_b):
        if (df['model_id'].astype(str) == str(mid)).any():
            continue
        focal_rows = dict(ModelMonthlyAggregate.objects
                          .filter(model_id=mid, domain=domain)
                          .values_list('month', 'score'))
        if not focal_rows:
            continue
        focal = {'model_id': mid}
        focal.update({m: focal_rows.get(m) for m in month_cols})
        df = pd.concat([df, pd.DataFrame([focal])], ignore_index=True)
    _, rank_df = wide_scores_and_rank_df(df, month_cols)
    return rank_df


def _compare_focal_change_lines(i, dates, values, kind, display_name, edges_map,
                                coverage_deltas, model_id=None, rank_df=None,
                                scored_new_deltas=None):
    """Explain one model’s month-over-month change. This is the compare-side mirror
    of _point_attribution_lines on the model card."""
    if i == 0 or values[i] is None or values[i - 1] is None:
        return []

    ym_prev = _date_to_month_key(dates[i - 1])
    ym_curr = _date_to_month_key(dates[i])
    edge_key = f'{ym_prev}|{ym_curr}'
    added = (edges_map or {}).get(edge_key, [])
    coverage_added = (coverage_deltas or {}).get(ym_curr, []) or []
    scored_of_added = set((scored_new_deltas or {}).get(ym_curr, []) or []) & set(added)

    if kind == 'score':
        prev_v, curr_v = values[i - 1], values[i]
        if abs(curr_v - prev_v) < 1e-9:
            return []
        delta = curr_v - prev_v
        lines = [f'{display_name} {_fmt_month(ym_curr)}: {curr_v:.3f}, {delta:+.3f} vs {_fmt_month(ym_prev)}.']
    else:
        prev_v = int(round(float(values[i - 1])))
        curr_v = int(round(float(values[i])))
        if prev_v == curr_v:
            return []
        lines = [f'{display_name} {_fmt_month(ym_curr)}: rank {curr_v}, {_rank_move(prev_v, curr_v)} from {_fmt_month(ym_prev)}.']

    model_lines = []
    if kind == 'rank' and rank_df is not None and model_id is not None:
        if ym_prev in rank_df.columns and ym_curr in rank_df.columns:
            model_lines = rank_transition_model_lines(model_id, ym_prev, ym_curr, prev_v, curr_v, rank_df)

    if model_lines:
        for ml in model_lines:
            lines.append(f'{display_name}: {ml}')
    elif kind == 'score' and added:
        lines.append(f'{display_name}: scored {len(scored_of_added)} of {_plural(len(added), "new benchmark")}.')

    cap = _COMPARE_COVERAGE_BULLET_CAP
    if coverage_added:
        if len(coverage_added) <= 3:
            lines.append(f'{display_name} newly scored: ' + ', '.join(coverage_added) + '.')
        else:
            lines.append(f'{display_name} newly scored on {_plural(len(coverage_added), "benchmark")}:')
            for b in coverage_added[:cap]:
                lines.append(f'  - {b}')
            if len(coverage_added) > cap:
                lines.append(f'  ... and {len(coverage_added) - cap} more.')
    elif not model_lines and not added:
        lines.append(f'{display_name}: no new benchmarks this month; change from score updates or other models.')

    return lines


def _comparison_point_lines(i, dates, kind, series_a, series_b, name_a, name_b,
                             coverage_a=None, coverage_b=None,
                             new_leaf_counts=None, new_model_counts=None,
                             edges_map=None, mid_a=None, mid_b=None, rank_df=None,
                             scored_new_a=None, scored_new_b=None):
    """Hover narrative at month index ``i`` comparing A and B at that point.
    When ``i > 0``, appends month-over-month change reasons per model (mirroring
    the single-model trend panel)."""
    ym = _date_to_month_key(dates[i])
    mlabel = _fmt_month(ym)
    name_a = _truncate_sidebar_name(name_a)
    name_b = _truncate_sidebar_name(name_b)
    va = series_a[i]
    vb = series_b[i]
    lines = []
    if va is None and vb is None:
        lines = [f'{mlabel}: no data for either model.']
    elif va is None:
        if kind == 'score':
            lines = [f'{mlabel}: {name_a} no data; {name_b} {vb:.3f}.']
        else:
            lines = [f'{mlabel}: {name_a} no data; {name_b} rank {int(round(vb))}.']
    elif vb is None:
        if kind == 'score':
            lines = [f'{mlabel}: {name_b} no data; {name_a} {va:.3f}.']
        else:
            lines = [f'{mlabel}: {name_b} no data; {name_a} rank {int(round(va))}.']
    elif kind == 'score':
        gap = va - vb
        leader, _follower, lead_gap = (name_a, name_b, gap) if gap >= 0 else (name_b, name_a, -gap)
        if abs(gap) < 1e-9:
            lines = [f'{mlabel}: {name_a} {va:.3f}, {name_b} {vb:.3f}.', 'Tied this month.']
        else:
            lines = [
                f'{mlabel}: {name_a} {va:.3f}, {name_b} {vb:.3f}.',
                f'{leader} leads by {lead_gap:.3f} ({lead_gap / max(va, vb) * 100:.0f}%).',
            ]
    else:  # rank kind: smaller is better
        ra = int(round(va))
        rb = int(round(vb))
        if ra == rb:
            lines = [f'{mlabel}: both rank {ra}.', 'Tied this month.']
        else:
            leader, follower, lead_gap = (name_a, name_b, rb - ra) if ra < rb else (name_b, name_a, ra - rb)
            lines = [
                f'{mlabel}: {name_a} rank {ra}, {name_b} rank {rb}.',
                f'{leader} leads by {_plural(lead_gap, "position")}.',
            ]

    if kind == 'score' and i > 0:
        ym_prev = _date_to_month_key(dates[i - 1])
        edge_key = f'{ym_prev}|{ym}'
        added = (edges_map or {}).get(edge_key, [])
        any_focal = False
        for name, series, cov, mid, scored in (
            (name_a, series_a, coverage_a, mid_a, scored_new_a),
            (name_b, series_b, coverage_b, mid_b, scored_new_b),
        ):
            focal = _compare_focal_change_lines(
                i, dates, series, kind, name, edges_map, cov,
                model_id=mid, rank_df=rank_df, scored_new_deltas=scored,
            )
            if focal:
                any_focal = True
                lines.extend(focal)
        if added:
            scored_a_set = set((scored_new_a or {}).get(ym, []) or []) & set(added)
            scored_b_set = set((scored_new_b or {}).get(ym, []) or []) & set(added)
            lines.append(f'{_plural(len(added), "new benchmark")} added this month (unscored count as 0):')
            cap = _COMPARE_COVERAGE_BULLET_CAP
            for b in added[:cap]:
                who = []
                if b in scored_a_set: who.append(name_a)
                if b in scored_b_set: who.append(name_b)
                lines.append(f'- {b} ({" + ".join(who) if who else "neither"})')
            if len(added) > cap:
                lines.append(f'... and {len(added) - cap} more.')
        elif not any_focal:
            cov_a = (coverage_a or {}).get(ym, []) or []
            cov_b = (coverage_b or {}).get(ym, []) or []
            if not cov_a and not cov_b:
                lines.append('Neither model changed score vs the prior month.')
    elif kind == 'score':
        cov_a = (coverage_a or {}).get(ym, []) or []
        cov_b = (coverage_b or {}).get(ym, []) or []

        def _emit_coverage(name, cov):
            if not cov:
                return
            if len(cov) <= 3:
                lines.append(f'{name} newly scored: ' + ', '.join(cov) + '.')
                return
            lines.append(f'{name} newly scored on {_plural(len(cov), "benchmark")}:')
            cap = _COMPARE_COVERAGE_BULLET_CAP
            for b in cov[:cap]:
                lines.append(f'  - {b}')
            if len(cov) > cap:
                lines.append(f'  ... and {len(cov) - cap} more.')

        _emit_coverage(name_a, cov_a)
        _emit_coverage(name_b, cov_b)
        if not cov_a and not cov_b:
            lines.append('No new benchmark scores for either model this month.')
    elif kind == 'rank' and i > 0:
        for name, series, cov, mid, scored in (
            (name_a, series_a, coverage_a, mid_a, scored_new_a),
            (name_b, series_b, coverage_b, mid_b, scored_new_b),
        ):
            lines.extend(_compare_focal_change_lines(
                i, dates, series, kind, name, edges_map, cov,
                model_id=mid, rank_df=rank_df, scored_new_deltas=scored,
            ))

    if kind == 'rank':
        nl = (new_leaf_counts or {}).get(ym, 0)
        nm = (new_model_counts or {}).get(ym, 0)
        bits = []
        if nl:
            bits.append(f'{_plural(nl, "new benchmark")} counted')
        if nm:
            bits.append(f'{_plural(nm, "new model")} entered')
        if bits:
            lines.append('This month: ' + '; '.join(bits) + '.')
        elif i == 0:
            lines.append('No new benchmarks or models this month.')
    return lines


def _build_comparison_trend_meta(dates, kind, series_a, series_b, name_a, name_b,
                                  coverage_a=None, coverage_b=None,
                                  new_leaf_counts=None, new_model_counts=None,
                                  edges_map=None, mid_a=None, mid_b=None, rank_df=None,
                                  scored_new_a=None, scored_new_b=None):
    # Truncate the display copy only, so callers keep their full identifiers.
    name_a_disp = _truncate_sidebar_name(name_a)
    name_b_disp = _truncate_sidebar_name(name_b)
    valid_a = [v for v in series_a if v is not None]
    valid_b = [v for v in series_b if v is not None]
    if valid_a and valid_b:
        if kind == 'score':
            overall = [
                f'{name_a_disp}: {valid_a[0]:.3f} → {valid_a[-1]:.3f} ({valid_a[-1] - valid_a[0]:+.3f}).',
                f'{name_b_disp}: {valid_b[0]:.3f} → {valid_b[-1]:.3f} ({valid_b[-1] - valid_b[0]:+.3f}).',
                'Hover to compare by month; click to pin, Esc to release.',
            ]
        else:
            ra0, ra1 = int(round(valid_a[0])), int(round(valid_a[-1]))
            rb0, rb1 = int(round(valid_b[0])), int(round(valid_b[-1]))
            overall = [
                f'{name_a_disp}: rank {ra0} → {ra1} ({_rank_move(ra0, ra1)}).',
                f'{name_b_disp}: rank {rb0} → {rb1} ({_rank_move(rb0, rb1)}).',
                'Hover to compare by month; click to pin, Esc to release.',
            ]
    else:
        overall = ['No overlapping trend data for these two models.']
    points = [{
        'lines': _comparison_point_lines(
            i, dates, kind, series_a, series_b, name_a, name_b,
            coverage_a=coverage_a, coverage_b=coverage_b,
            new_leaf_counts=new_leaf_counts, new_model_counts=new_model_counts,
            edges_map=edges_map, mid_a=mid_a, mid_b=mid_b, rank_df=rank_df,
            scored_new_a=scored_new_a, scored_new_b=scored_new_b,
        ),
    } for i in range(len(dates))]
    list_el = ('compare-score-attribution-list' if kind == 'score'
               else 'compare-rank-attribution-list')
    return {
        'kind': kind,
        'attributionListId': list_el,
        'defaultLines': overall,
        'points': points,
    }


def _build_comparison_plot_json(dates, kind, series_a, series_b, name_a, name_b,
                                range_start, range_end):
    """Plotly JSON for the compare page: A and B overlaid on one chart."""
    flat = [v for v in (series_a + series_b) if v is not None]
    if not flat:
        return None
    y_min, y_max = min(flat), max(flat)
    if kind == 'score':
        pad = max(0.05, (y_max - y_min) * 0.1) if y_max > y_min else 0.05
        # No clamp at 1: top-of-range lines must not sit flush against the edge.
        y_range = [max(0, y_min - pad), y_max + pad]
        y_title = 'Score'
        hover_fmt = 'Score: %{y:.4f}'
    else:
        pad = max(1, (y_max - y_min) * 0.1) if y_max > y_min else 1
        y_range = [y_max + pad, y_min - pad]  # reversed: rank 1 at top
        y_title = 'Rank (1 = best)'
        hover_fmt = 'Rank: %{y:.0f}'
    range_start, range_end = _pad_date_range(range_start, range_end)
    customdata = [[i] for i in range(len(dates))]

    def _trace(name, color, ys):
        short = _truncate_legend_name(name)
        return {
            'x': dates,
            'y': ys,
            'type': 'scatter',
            'mode': 'lines',
            'hoveron': 'points',
            'name': short,
            'customdata': customdata,
            'connectgaps': False,
            'line': {'color': color, 'width': 2.5, 'shape': 'spline', 'smoothing': 1.3},
            'hovertemplate': '<b>%{x|%d %b %Y}</b><br>' + hover_fmt + '<extra>' + short + '</extra>',
        }

    # Compare is taller than the model-card chart so two series + an external
    # legend still leave a usable plot area. Legend sits above the axes so it
    # does not cover early-month points.
    return {
        'data': [_trace(name_a, _COMPARE_COLOR_A, series_a),
                 _trace(name_b, _COMPARE_COLOR_B, series_b)],
        'layout': {
            'height': 480,
            'autosize': True,
            'paper_bgcolor': '#ffffff',
            'plot_bgcolor': '#ffffff',
            'margin': {'t': 52, 'r': 12, 'b': 44, 'l': 48},
            'hovermode': 'closest',
            'template': _trend_grid_template(),
            'xaxis': _trend_xaxis(range_start, range_end),
            'yaxis': _trend_yaxis(y_title, [round(y_range[0], 6), round(y_range[1], 6)]),
            'showlegend': True,
            'legend': {
                'orientation': 'h',
                'yanchor': 'bottom', 'y': 1.08,
                'xanchor': 'left', 'x': 0,
                'bgcolor': 'rgba(255, 255, 255, 0)',
                'borderwidth': 0,
                'font': {'size': 11},
            },
        },
        'config': _trend_plot_config(),
    }


def _aligned_pair_series(mid_a, mid_b, domain, kind):
    """``(dates, series_a, series_b, name_a, name_b)`` aligned on the union of
    months either model has data for. ``series_*`` carries ``None`` for missing
    months so the Plotly trace can break the line via ``connectgaps=False``."""
    if kind == 'score':
        rows_a = dict(ModelMonthlyAggregate.objects
                      .filter(model_id=mid_a, domain=domain)
                      .values_list('month', 'score'))
        rows_b = dict(ModelMonthlyAggregate.objects
                      .filter(model_id=mid_b, domain=domain)
                      .values_list('month', 'score'))
        # Don't merge the dicts: dict-merge has a 0-wins-on-conflict footgun.
        months = sorted({m for m in (set(rows_a) | set(rows_b))
                         if (rows_a.get(m) or 0) > 0 or (rows_b.get(m) or 0) > 0})
        if not months:
            return None
        series_a = [float(rows_a[m]) if (rows_a.get(m) or 0) > 0 else None for m in months]
        series_b = [float(rows_b[m]) if (rows_b.get(m) or 0) > 0 else None for m in months]
    else:
        public_wide, _ = _load_public_wide_scores(domain)
        month_cols = [c for c in public_wide.columns if c != 'model_id']
        if not month_cols:
            return None
        df = public_wide
        for mid in (mid_a, mid_b):
            if not (df['model_id'].astype(str) == str(mid)).any():
                focal_rows = dict(ModelMonthlyAggregate.objects
                                  .filter(model_id=mid, domain=domain)
                                  .values_list('month', 'score'))
                if not focal_rows:
                    continue
                focal = {'model_id': mid}
                focal.update({m: focal_rows.get(m) for m in month_cols})
                df = pd.concat([df, pd.DataFrame([focal])], ignore_index=True)
        _, rank_df = wide_scores_and_rank_df(df, month_cols)
        rank_idx = rank_df.set_index('model_id')
        if mid_a not in rank_idx.index or mid_b not in rank_idx.index:
            return None
        ra = rank_idx.loc[mid_a, month_cols]
        rb = rank_idx.loc[mid_b, month_cols]
        months = [m for m in month_cols if pd.notna(ra[m]) or pd.notna(rb[m])]
        if not months:
            return None
        series_a = [int(ra[m]) if pd.notna(ra[m]) else None for m in months]
        series_b = [int(rb[m]) if pd.notna(rb[m]) else None for m in months]

    name_map, _ = _load_model_names(domain)
    name_a = name_map.get(mid_a) or f'#{_fmt_model_id(mid_a)}'
    name_b = name_map.get(mid_b) or f'#{_fmt_model_id(mid_b)}'

    dates = []
    for m in months:
        try:
            ts = pd.Timestamp(str(m) + '-01') + pd.offsets.MonthEnd(0)
            dates.append(ts.strftime('%Y-%m-%d'))
        except Exception:
            dates.append(str(m))
    return dates, series_a, series_b, name_a, name_b


def load_and_build_comparison_trend(mid_a, mid_b, domain):
    """Two-model overlaid trend (score + rank) for the compare page. Returns
    ``{'score': <plot_json|None>, 'rank': <plot_json|None>}``."""
    out = {'score': None, 'rank': None}
    try:
        if domain != 'vision':
            return out
        coverage_a = _load_focal_coverage_deltas(mid_a, domain)
        coverage_b = _load_focal_coverage_deltas(mid_b, domain)
        edges = _load_month_benchmark_edges(domain)
        new_leaf_counts = _edges_counts_by_curr_month(edges)
        new_model_counts = _load_new_models_by_month(domain)
        rank_df = _load_comparison_rank_df(mid_a, mid_b, domain)
        scored_new_a = _load_focal_scored_new_leaves(mid_a, domain, edges)
        scored_new_b = _load_focal_scored_new_leaves(mid_b, domain, edges)

        for kind in ('score', 'rank'):
            pair = _aligned_pair_series(mid_a, mid_b, domain, kind)
            if pair is None:
                continue
            dates, series_a, series_b, name_a, name_b = pair
            today_str = date.today().strftime('%Y-%m-%d')
            range_start = dates[0] if dates else today_str
            range_end = today_str
            plot_json = _build_comparison_plot_json(
                dates, kind, series_a, series_b, name_a, name_b, range_start, range_end,
            )
            if plot_json is None:
                continue
            plot_json['trendMeta'] = _build_comparison_trend_meta(
                dates, kind, series_a, series_b, name_a, name_b,
                coverage_a=coverage_a, coverage_b=coverage_b,
                new_leaf_counts=new_leaf_counts, new_model_counts=new_model_counts,
                edges_map=edges, mid_a=mid_a, mid_b=mid_b, rank_df=rank_df,
                scored_new_a=scored_new_a, scored_new_b=scored_new_b,
            )
            out[kind] = plot_json
        return out
    except Exception:
        _logger.exception('comparison trend build failed for models %s vs %s', mid_a, mid_b)
        return out
