/* Shared hover / pin / pointer-to-index helpers for the single-model trend
 * (model-score-trend.js) and the compare-page two-line trend (compare-trend.js).
 *
 * Both consume the same trendMeta payload (defaultLines + per-point lines
 * indexed by customdata[0]) and need the same Plotly 3 quirks handled:
 * - plotly_hover may arrive only via DOM or only via gd.on() depending on build.
 * - Spline / line hover often omits pointNumber; the server emits the index in
 *   customdata so we read that first.
 * - Sliding off a marker but still over the plot must not clear the entry; the
 *   tab panel owns mouseleave clearing.
 *
 * Exposed on window.BrainScoreTrendHover.
 */
(function () {
    'use strict';

    /* Assign a presentation class per line so CSS can build a readable
       hierarchy: idx 0 is the headline; ``- `` lines are bullets (prefix
       stripped); a trailing ``:`` marks a section label; ``... and N more``
       is de-emphasised; everything else is a plain note. */
    /* "... and N more." followed by bullets becomes a <details> toggle holding
       them; with nothing after it, it stays the plain de-emphasised line. */
    function makeMoreToggle(summaryText) {
        var li = document.createElement('li');
        li.className = 'attr-more';
        var details = document.createElement('details');
        var summary = document.createElement('summary');
        summary.textContent = summaryText;
        var ul = document.createElement('ul');
        ul.className = 'attr-more-list';
        details.appendChild(summary);
        details.appendChild(ul);
        li.appendChild(details);
        return {li: li, list: ul};
    }

    function renderAttributionList(ulEl, lines) {
        if (!ulEl) return;
        ulEl.innerHTML = '';
        var sink = ulEl;  // bullets after a "... and N more." marker land in its <details>
        (lines || []).forEach(function (line, idx) {
            var li = document.createElement('li');
            var trimmed = (line || '').replace(/^\s+/, '');
            if (/^-\s/.test(trimmed)) {
                li.className = 'attr-item';
                li.textContent = trimmed.replace(/^-\s+/, '');
                sink.appendChild(li);
                return;
            }
            sink = ulEl;  // any non-bullet line closes the overflow group
            if (/^\.\.\.\s*and\b/.test(trimmed)) {
                var more = makeMoreToggle(trimmed);
                ulEl.appendChild(more.li);
                sink = more.list;
                return;
            }
            if (idx === 0) {
                li.className = 'attr-head';
                li.textContent = line;
            } else if (/:$/.test(trimmed)) {
                li.className = 'attr-label';
                li.textContent = line;
            } else {
                li.className = 'attr-note';
                li.textContent = line;
            }
            ulEl.appendChild(li);
        });
        // A marker with nothing after it (single-model panel, which still
        // truncates server-side) stays the plain line rather than an empty toggle.
        Array.prototype.forEach.call(ulEl.querySelectorAll('.attr-more details'), function (d) {
            if (d.querySelector('.attr-more-list').children.length) return;
            d.parentNode.textContent = d.querySelector('summary').textContent;
        });
    }

    function eventTouchesPlot(gd, e) {
        if (!gd || !e || !e.target) return false;
        if (typeof gd.contains === 'function' && gd.contains(e.target)) return true;
        if (typeof e.composedPath === 'function') {
            var path = e.composedPath();
            for (var i = 0; i < path.length; i++) {
                if (path[i] === gd) return true;
            }
        }
        return false;
    }

    /* Map pointer X to nearest data index using Plotly's internal axis when
       available, falling back to layout margins. */
    function nearestIndexFromMouseX(gd, spec, clientX) {
        var xs = spec && spec.data && spec.data[0] && spec.data[0].x;
        if (!xs || !xs.length || !gd) return -1;
        var fullLayout = gd._fullLayout;
        if (!fullLayout || !fullLayout.xaxis) return -1;
        var xa = fullLayout.xaxis;
        var bb = gd.getBoundingClientRect();
        var m = fullLayout.margin || {};
        var ml = typeof m.l === 'number' ? m.l : 80;
        var mr = typeof m.r === 'number' ? m.r : 80;

        var rel = NaN;
        if (typeof xa._offset === 'number' && typeof xa._length === 'number' && xa._length > 0) {
            rel = ((clientX - bb.left) - xa._offset) / xa._length;
        }
        if (!isFinite(rel)) {
            var plotW = Math.max(1, bb.width - ml - mr);
            rel = (clientX - bb.left - ml) / plotW;
        }
        rel = Math.max(0, Math.min(1, rel));

        var range = xa._rl || xa.range;
        if (!range || range.length < 2) return -1;
        var t0 = +new Date(range[0]);
        var t1 = +new Date(range[1]);
        if (isNaN(t0) || isNaN(t1)) return -1;
        if (t0 > t1) { var swap = t0; t0 = t1; t1 = swap; rel = 1 - rel; }
        var t = t0 + rel * (t1 - t0);

        var best = -1;
        var bestD = Infinity;
        for (var i = 0; i < xs.length; i++) {
            var xi = +new Date(xs[i]);
            if (isNaN(xi)) continue;
            var d = Math.abs(xi - t);
            if (d < bestD) { bestD = d; best = i; }
        }
        return best;
    }

    function bindPlotlyHover(gd, onHover, onUnhover) {
        if (!gd) return;
        gd.addEventListener('plotly_hover', function (e) {
            onHover(e.detail && e.detail.points ? e.detail : e);
        });
        gd.addEventListener('plotly_unhover', function (e) {
            onUnhover(e.detail && e.detail.points ? e.detail : e);
        });
        if (typeof gd.on === 'function') {
            gd.on('plotly_hover', onHover);
            gd.on('plotly_unhover', onUnhover);
        }
    }

    var HOLD_BAR_HTML = (
        '<div class="is-flex is-justify-content-space-between is-align-items-flex-start is-flex-wrap-wrap" style="gap:0.35rem">' +
        '<span class="is-size-7 has-text-weight-semibold" style="line-height:1.35">Reason hold</span>' +
        '<button type="button" class="button is-small is-light js-trend-reason-release">Release</button>' +
        '</div>' +
        '<p class="is-size-7 has-text-grey mb-0 mt-1">Pinned until Release is clicked or Esc is pressed -- hover does not change this text.</p>'
    );

    /* Insert (or refresh listeners on an existing) hold bar at the top of
       ``aside``. Always rewires the release button so a stale closure from a
       prior wire pass can't hold the wrong panel's state. */
    function ensureHoldBar(aside, onRelease) {
        if (!aside) return null;
        var bar = aside.querySelector('.trend-reason-hold');
        if (!bar) {
            bar = document.createElement('div');
            bar.className = 'trend-reason-hold';
            bar.setAttribute('role', 'status');
            bar.innerHTML = HOLD_BAR_HTML;
            aside.insertBefore(bar, aside.firstChild);
        }
        var oldBtn = bar.querySelector('.js-trend-reason-release');
        if (oldBtn) {
            var freshBtn = oldBtn.cloneNode(true);
            oldBtn.parentNode.replaceChild(freshBtn, oldBtn);
            freshBtn.addEventListener('click', function (e) {
                e.preventDefault();
                onRelease();
            });
        }
        return bar;
    }

    /* Draggable divider between the plot column and the attribution column.
       Writes a ``--plot-col`` percentage onto every ``.trend-split`` in the
       same scope so both tabs (Scores/Rankings) stay in sync; the CSS turns
       that into the column widths at desktop width. */
    var MIN_FRAC = 0.35, MAX_FRAC = 0.85;

    function wireColumnResizers() {
        document.querySelectorAll('.trend-resizer').forEach(function (handle) {
            if (handle.__trendResizeWired) return;
            handle.__trendResizeWired = true;
            var split = handle.closest('.trend-split');
            if (!split) return;
            var scope = handle.closest('[data-trend-resize-scope]') || split;

            function apply(frac) {
                frac = Math.max(MIN_FRAC, Math.min(MAX_FRAC, frac));
                var pct = (frac * 100).toFixed(1) + '%';
                scope.querySelectorAll('.trend-split').forEach(function (s) {
                    s.style.setProperty('--plot-col', pct);
                });
            }
            function fracFromX(clientX) {
                var rect = split.getBoundingClientRect();
                return rect.width ? (clientX - rect.left) / rect.width : null;
            }
            function resizePlots() {
                if (typeof Plotly === 'undefined') return;
                scope.querySelectorAll('.js-plotly-plot').forEach(function (gd) {
                    try { Plotly.Plots.resize(gd); } catch (e) { /* swallow */ }
                });
            }
            function currentFrac() {
                var col = split.querySelector('.trend-plot-col');
                var rect = split.getBoundingClientRect();
                if (!col || !rect.width) return 2 / 3;
                return col.getBoundingClientRect().width / rect.width;
            }

            var dragging = false;
            handle.addEventListener('pointerdown', function (e) {
                dragging = true;
                try { handle.setPointerCapture(e.pointerId); } catch (_) {}
                document.body.style.userSelect = 'none';
                e.preventDefault();
            });
            handle.addEventListener('pointermove', function (e) {
                if (!dragging) return;
                var f = fracFromX(e.clientX);
                if (f !== null) apply(f);
            });
            function endDrag(e) {
                if (!dragging) return;
                dragging = false;
                try { handle.releasePointerCapture(e.pointerId); } catch (_) {}
                document.body.style.userSelect = '';
                resizePlots();
            }
            handle.addEventListener('pointerup', endDrag);
            handle.addEventListener('pointercancel', endDrag);
            handle.addEventListener('keydown', function (e) {
                if (e.key === 'ArrowLeft') { apply(currentFrac() - 0.03); resizePlots(); e.preventDefault(); }
                else if (e.key === 'ArrowRight') { apply(currentFrac() + 0.03); resizePlots(); e.preventDefault(); }
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', wireColumnResizers);
    } else {
        wireColumnResizers();
    }

    /* Keep ``gd`` sized through window resizes AND container visibility flips
       (tab switches, column drags). A plot initialised while hidden caches a
       0-width layout and must be re-measured once visible. Idempotent so
       repeated wiring (e.g. compare dropdown changes) doesn't stack observers. */
    function wireResponsiveResize(gd) {
        if (!gd || gd.__trendResizeWired) return;
        gd.__trendResizeWired = true;
        var resize = function () {
            if (typeof Plotly === 'undefined') return;
            if (!gd.isConnected || gd.offsetParent === null || !gd.offsetWidth) return;
            try {
                // Plotly v3 sometimes ignores a bare Plots.resize; force a
                // re-measurement via relayout(autosize) first.
                Plotly.relayout(gd, {autosize: true});
                Plotly.Plots.resize(gd);
            } catch (e) { /* swallow */ }
        };
        window.addEventListener('resize', resize);
        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(resize).observe(gd);
        }
        requestAnimationFrame(resize);
    }

    /* Brain-Score watermark, sized and placed like the compare-page charts in
       compare_models.js (120x28 px, bottom-right of the plot area). */
    var LOGO_PX = {w: 120, h: 28};

    function applyLogo(plotEl, layout) {
        if (!layout || typeof logo_url === 'undefined' || !logo_url) return layout;
        var m = layout.margin || {};
        var width = (plotEl && plotEl.offsetWidth) || 800;
        var areaW = width - (m.l || 0) - (m.r || 0);
        var areaH = (layout.height || 400) - (m.t || 0) - (m.b || 0);
        if (areaW <= 0 || areaH <= 0) return layout;
        layout.images = [{
            source: logo_url,
            xref: 'paper', yref: 'paper',
            x: 0.98, y: 0.02,  // just clear of the x-axis
            sizex: LOGO_PX.w / areaW, sizey: LOGO_PX.h / areaH,
            xanchor: 'right', yanchor: 'bottom',
            layer: 'above',
        }];
        return layout;
    }

    window.BrainScoreTrendHover = {
        applyLogo: applyLogo,
        renderAttributionList: renderAttributionList,
        eventTouchesPlot: eventTouchesPlot,
        nearestIndexFromMouseX: nearestIndexFromMouseX,
        bindPlotlyHover: bindPlotlyHover,
        ensureHoldBar: ensureHoldBar,
        wireColumnResizers: wireColumnResizers,
        wireResponsiveResize: wireResponsiveResize,
    };
})();
