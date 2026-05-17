(function () {
    var H = window.BrainScoreTrendHover;
    var renderAttributionList = H.renderAttributionList;
    var eventTouchesPlot = H.eventTouchesPlot;
    var nearestIndexFromMouseX = H.nearestIndexFromMouseX;
    var bindPlotlyHover = H.bindPlotlyHover;
    var ensureHoldBar = H.ensureHoldBar;

    /** Set in initPlots when rank chart exists; used to wire hover after plot + tab are ready. */
    window.__brainScoreRankTrendSpec = null;
    window.__brainScoreRankPlotReady = null;
    window.__brainScoreRankHoverWired = false;

    /** Server sets data-defer-rank-hover="true" when both Scores and Rankings plots exist (rank panel starts hidden). */
    function shouldDeferRankHoverFromServer() {
        var panel = document.getElementById('trend-tab-rankings');
        return panel && panel.getAttribute('data-defer-rank-hover') === 'true';
    }

    function initTrendTabs() {
        var panelScores = document.getElementById('trend-tab-scores');
        var panelRankings = document.getElementById('trend-tab-rankings');
        if (!panelScores || !panelRankings) return;

        var tabLinks = document.querySelectorAll('.js-trend-tab');
        tabLinks.forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                var tab = this.getAttribute('data-tab');
                if (!tab) return;
                var li = this.closest('li');
                var tabsContainer = document.getElementById('trend-tabs');
                if (tabsContainer) {
                    var allLis = tabsContainer.querySelectorAll('li[data-tab]');
                    allLis.forEach(function (t) { t.classList.remove('is-active'); });
                }
                if (li) li.classList.add('is-active');
                if (tab === 'scores') {
                    panelScores.style.display = '';
                    panelRankings.style.display = 'none';
                } else {
                    panelScores.style.display = 'none';
                    panelRankings.style.display = '';
                    /**
                     * Rank plot may still be initializing; always wait for rankPlotReady then wire once.
                     * Covers: (1) user switches to Rankings before newPlot().then ran, (2) hidden-at-init defer.
                     */
                    function tryWireRankHover() {
                        if (window.__brainScoreRankHoverWired) {
                            if (typeof Plotly !== 'undefined' && document.getElementById('model-rank-trend-plot')) {
                                Plotly.Plots.resize('model-rank-trend-plot');
                            }
                            return;
                        }
                        var spec = window.__brainScoreRankTrendSpec;
                        var gd = document.getElementById('model-rank-trend-plot');
                        if (!spec || !gd) return;
                        if (typeof Plotly !== 'undefined') {
                            Plotly.Plots.resize(gd);
                        }
                        function bindAfterPaint() {
                            var bound = wireTrendMeta(gd, spec);
                            if (bound) {
                                window.__brainScoreRankHoverWired = true;
                            }
                        }
                        requestAnimationFrame(function () {
                            requestAnimationFrame(bindAfterPaint);
                        });
                    }
                    var ready = window.__brainScoreRankPlotReady;
                    if (ready && typeof ready.then === 'function') {
                        ready.then(function () {
                            requestAnimationFrame(tryWireRankHover);
                        });
                    } else {
                        requestAnimationFrame(tryWireRankHover);
                    }
                }
            });
        });
    }

    /* Keep ``gd`` sized through window resizes AND container visibility
       flips. A plot initialized while hidden caches a 0-width layout and
       then disagrees with its sibling tab on width unless re-measured. */
    function wireResponsiveResize(gd) {
        if (!gd) return;
        var resize = function () {
            if (typeof Plotly === 'undefined') return;
            if (!gd.isConnected || !gd.offsetWidth) return;
            try {
                // Plotly v3 sometimes ignores a bare Plots.resize; force a
                // re-measurement via relayout(autosize).
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

    function hoverPointsFromEvent(ev) {
        if (!ev) return null;
        if (ev.points && ev.points.length) return ev.points;
        if (ev.detail && ev.detail.points && ev.detail.points.length) return ev.detail.points;
        if (ev.detail && ev.detail.event && ev.detail.event.points && ev.detail.event.points.length) {
            return ev.detail.event.points;
        }
        return null;
    }

    function normDateKey(v) {
        if (v === undefined || v === null) return '';
        if (Object.prototype.toString.call(v) === '[object Date]' && !isNaN(v.getTime())) {
            return v.toISOString().slice(0, 10);
        }
        if (typeof v === 'number' && !isNaN(v)) {
            try {
                return new Date(v).toISOString().slice(0, 10);
            } catch (e) {
                return String(v);
            }
        }
        var s = String(v);
        if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
            return s.slice(0, 10);
        }
        try {
            var parsed = new Date(s);
            if (!isNaN(parsed.getTime())) {
                return parsed.toISOString().slice(0, 10);
            }
        } catch (e) { /* ignore */ }
        return s.length >= 10 ? s.slice(0, 10) : s;
    }

    function pointIndexFromHover(pt, spec) {
        if (!pt) return -1;
        /* Plotly spline / line hover often omits pointNumber; server sends index in customdata. */
        var cd = pt.customdata;
        if (cd != null) {
            if (typeof cd === 'number' && cd >= 0) return cd;
            if (Array.isArray(cd) && cd.length && typeof cd[0] === 'number' && cd[0] >= 0) return cd[0];
        }
        var idx = pt.pointIndex;
        if (idx == null || idx < 0) idx = pt.pointNumber;
        if (idx != null && idx >= 0) return idx;

        var xs = spec && spec.data && spec.data[0] && spec.data[0].x;
        if (!xs || pt.x === undefined || pt.x === null) return -1;
        var target = normDateKey(pt.x);
        for (var j = 0; j < xs.length; j++) {
            if (normDateKey(xs[j]) === target) return j;
        }
        /* Spline / timezone: snap to nearest series month */
        var tMs = Date.parse(target + 'T12:00:00.000Z');
        if (isNaN(tMs)) return -1;
        var best = -1;
        var bestAbs = Infinity;
        for (var k = 0; k < xs.length; k++) {
            var key = normDateKey(xs[k]);
            var xMs = Date.parse(key + 'T12:00:00.000Z');
            if (isNaN(xMs)) continue;
            var d = Math.abs(xMs - tMs);
            if (d < bestAbs) {
                bestAbs = d;
                best = k;
            }
        }
        if (best >= 0 && bestAbs <= 40 * 86400000) return best;
        return -1;
    }

    function wireTrendMeta(gd, spec) {
        var meta = spec && spec.trendMeta;
        if (!gd || !meta) return false;

        var listId = meta.attributionListId
            || (meta.kind === 'score' ? 'model-score-attribution-list' : 'model-rank-attribution-list');
        var ul = document.getElementById(listId);
        var points = meta.points || [];

        if (!points.length) return false;
        if (!ul) return false;

        var aside = ul.closest('aside');
        var pinnedIdx = null;
        var lastMouseIdx = -1;
        var holdBar = null;

        function restoreDefault() {
            if (pinnedIdx !== null) return;
            renderAttributionList(ul, meta.defaultLines || []);
        }

        function clearPin() {
            pinnedIdx = null;
            lastMouseIdx = -1;
            if (holdBar) holdBar.classList.remove('is-active');
            if (aside) aside.classList.remove('trend-attribution-panel--pinned');
            renderAttributionList(ul, meta.defaultLines || []);
        }

        function setPin(idx) {
            if (idx < 0 || idx >= points.length) return;
            var entry = points[idx];
            if (!entry || !entry.lines) return;
            pinnedIdx = idx;
            lastMouseIdx = idx;
            renderAttributionList(ul, entry.lines);
            if (holdBar) holdBar.classList.add('is-active');
            if (aside) aside.classList.add('trend-attribution-panel--pinned');
        }

        holdBar = ensureHoldBar(aside, clearPin);

        function onKeydown(e) {
            if (e.key !== 'Escape' || pinnedIdx === null) return;
            clearPin();
        }
        document.addEventListener('keydown', onKeydown);

        restoreDefault();

        bindPlotlyHover(gd, function (ev) {
            if (pinnedIdx !== null) return;
            var pts = hoverPointsFromEvent(ev);
            if (!pts || !pts.length) return;
            var idx = pointIndexFromHover(pts[0], spec);
            if (idx < 0) return;
            lastMouseIdx = idx;
            var entry = points[idx];
            if (entry && entry.lines) renderAttributionList(ul, entry.lines);
        }, function () {
            if (pinnedIdx !== null) return;
            restoreDefault();
        });

        function onPlotMouseMove(e) {
            if (pinnedIdx !== null) return;
            var idx = nearestIndexFromMouseX(gd, spec, e.clientX);
            if (idx < 0) return;
            if (idx === lastMouseIdx) return;
            lastMouseIdx = idx;
            var entry = points[idx];
            if (entry && entry.lines) renderAttributionList(ul, entry.lines);
        }
        function onPlotMouseLeave() {
            if (pinnedIdx !== null) return;
            lastMouseIdx = -1;
            restoreDefault();
        }
        gd.addEventListener('mousemove', onPlotMouseMove);

        function pinAtPointer(e) {
            if (e.button !== undefined && e.button !== 0) return;
            if (!eventTouchesPlot(gd, e)) return;
            if (e.target && e.target.closest && e.target.closest('.modebar')) return;
            var idx = nearestIndexFromMouseX(gd, spec, e.clientX);
            if (idx < 0) {
                idx = lastMouseIdx;
            }
            if (idx >= 0) {
                setPin(idx);
            }
        }
        /*
         * pointerdown in capture runs before Plotly tears down hover (plotly_unhover), so the sidebar
         * is not cleared to default before we pin. composedPath covers shadow/SVG targets.
         */
        gd.addEventListener('pointerdown', pinAtPointer, true);
        gd.addEventListener('click', pinAtPointer, true);
        /* Leave the whole tab panel (chart + sidebar), not just the plot -- avoids clearing when reading the aside. */
        var tabPanel = gd.closest('[id^="trend-tab-"]');
        if (tabPanel) {
            tabPanel.addEventListener('mouseleave', onPlotMouseLeave);
        } else {
            gd.addEventListener('mouseleave', onPlotMouseLeave);
        }

        return true;
    }

    function initPlots() {
        if (typeof Plotly === 'undefined') return;

        var scoreEl = document.getElementById('model-score-trend-plot-data');
        var scoreContainer = document.getElementById('model-score-trend-plot');
        if (scoreEl && scoreContainer) {
            try {
                var scoreSpec = JSON.parse(scoreEl.textContent);
                var scorePromise = Plotly.newPlot(
                    'model-score-trend-plot',
                    scoreSpec.data || [],
                    scoreSpec.layout || {},
                    scoreSpec.config || { responsive: true }
                );
                function attachScore() {
                    var gd = document.getElementById('model-score-trend-plot');
                    wireTrendMeta(gd, scoreSpec);
                    wireResponsiveResize(gd);
                }
                if (scorePromise && typeof scorePromise.then === 'function') {
                    scorePromise.then(attachScore).catch(attachScore);
                } else {
                    attachScore();
                }
            } catch (e) {
                console.warn('Score trend plot: failed to parse or render', e);
            }
        }

        var rankEl = document.getElementById('model-rank-trend-plot-data');
        var rankContainer = document.getElementById('model-rank-trend-plot');
        if (rankEl && rankContainer) {
            try {
                var rankSpec = JSON.parse(rankEl.textContent);
                window.__brainScoreRankTrendSpec = rankSpec;
                var rankPromise = Plotly.newPlot(
                    'model-rank-trend-plot',
                    rankSpec.data || [],
                    rankSpec.layout || {},
                    rankSpec.config || { responsive: true }
                );
                window.__brainScoreRankPlotReady = rankPromise || Promise.resolve();

                /**
                 * Only wire rank hover on first paint when the Rankings tab is the primary view
                 * (rank-only model). If both tabs exist, defer=true: never wire here -- must wire on tab click
                 * so Plotly attaches hover after the plot is visible.
                 */
                function attachRankHoverOnLoadIfNotDeferred() {
                    wireResponsiveResize(document.getElementById('model-rank-trend-plot'));
                    if (shouldDeferRankHoverFromServer()) return;
                    if (window.__brainScoreRankHoverWired) return;
                    var gd = document.getElementById('model-rank-trend-plot');
                    if (wireTrendMeta(gd, rankSpec)) {
                        window.__brainScoreRankHoverWired = true;
                    }
                }

                if (rankPromise && typeof rankPromise.then === 'function') {
                    rankPromise.then(attachRankHoverOnLoadIfNotDeferred).catch(function () {
                        if (!shouldDeferRankHoverFromServer()) {
                            var gd = document.getElementById('model-rank-trend-plot');
                            if (wireTrendMeta(gd, rankSpec)) {
                                window.__brainScoreRankHoverWired = true;
                            }
                        }
                    });
                } else {
                    attachRankHoverOnLoadIfNotDeferred();
                }
            } catch (e) {
                console.warn('Rank trend plot: failed to parse or render', e);
            }
        }
    }

    initTrendTabs();
    initPlots();
})();
