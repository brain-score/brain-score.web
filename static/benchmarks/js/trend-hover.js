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

    function renderAttributionList(ulEl, lines) {
        if (!ulEl) return;
        ulEl.innerHTML = '';
        (lines || []).forEach(function (line) {
            var li = document.createElement('li');
            li.textContent = line;
            ulEl.appendChild(li);
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

    window.BrainScoreTrendHover = {
        renderAttributionList: renderAttributionList,
        eventTouchesPlot: eventTouchesPlot,
        nearestIndexFromMouseX: nearestIndexFromMouseX,
        bindPlotlyHover: bindPlotlyHover,
        ensureHoldBar: ensureHoldBar,
    };
})();
