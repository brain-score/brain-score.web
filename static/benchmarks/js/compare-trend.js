/* Compare-page two-model overlaid trend. Fetches a Plotly JSON pair from
 * the ``trend_pair`` endpoint when both dropdowns are populated and renders
 * it; hover wiring mirrors model-score-trend.js (customdata[0] indexes
 * trendMeta.points). */
(function () {
    'use strict';

    var endpoint = (function () {
        var box = document.getElementById('compare-trend-box');
        return box ? box.dataset.trendEndpoint : null;
    })();

    function _renderAttributionList(listId, lines) {
        var ul = document.getElementById(listId);
        if (!ul) return;
        ul.innerHTML = '';
        (lines || []).forEach(function (line) {
            var li = document.createElement('li');
            li.textContent = line;
            ul.appendChild(li);
        });
    }

    function _renderEmpty(message) {
        var content = document.getElementById('compare-trend-content');
        var empty = document.getElementById('compare-trend-empty');
        if (content) content.style.display = 'none';
        if (empty) {
            empty.style.display = '';
            empty.textContent = message;
        }
    }

    function _showContent() {
        var content = document.getElementById('compare-trend-content');
        var empty = document.getElementById('compare-trend-empty');
        if (content) content.style.display = '';
        if (empty) empty.style.display = 'none';
    }

    /* Mirrors wireResponsiveResize in model-score-trend.js. Idempotent so
       dropdown changes don't stack observers on the same gd. */
    function _wireResponsiveResize(gd) {
        if (!gd || gd.__compareTrendResizeWired) return;
        gd.__compareTrendResizeWired = true;
        var resize = function () {
            if (typeof Plotly === 'undefined') return;
            if (!gd.isConnected || gd.offsetParent === null) return;
            try { Plotly.Plots.resize(gd); } catch (e) { /* swallow */ }
        };
        window.addEventListener('resize', resize);
        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(resize).observe(gd);
        }
    }

    function _hoverIndex(ev) {
        if (!ev || !ev.points || !ev.points.length) return -1;
        var cd = ev.points[0].customdata;
        if (typeof cd === 'number') return cd;
        if (Array.isArray(cd) && cd.length && typeof cd[0] === 'number') return cd[0];
        return -1;
    }

    /* Hover helpers ported from model-score-trend.js so the compare panels
       react to hovering anywhere along the x-axis, not just on the line. */

    function _eventTouchesPlot(gd, e) {
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
       available, falling back to layout margins. Independent of trace count --
       both A and B share the same ``x`` array so spec.data[0].x is enough. */
    function _nearestIndexFromMouseX(gd, spec, clientX) {
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

    /* Plotly 3 sometimes delivers plotly_hover only via DOM events or only via
       gd.on() depending on the build. Bind both. */
    function _bindPlotlyHover(gd, onHover, onUnhover) {
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

    /* Per-panel hover + click-to-pin state mirroring model-score-trend.js. */
    var _panels = {score: null, rank: null};

    function _findAside(listId) {
        var ul = document.getElementById(listId);
        return ul ? ul.closest('aside') : null;
    }

    function _ensureHoldBar(aside, onRelease) {
        if (!aside) return null;
        var existing = aside.querySelector('.trend-reason-hold');
        if (existing) {
            // Replace the release button so a stale closure from a prior wire
            // pass doesn't hold the wrong panel's state.
            var oldBtn = existing.querySelector('.js-trend-reason-release');
            if (oldBtn) {
                var freshBtn = oldBtn.cloneNode(true);
                oldBtn.parentNode.replaceChild(freshBtn, oldBtn);
                freshBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    onRelease();
                });
            }
            return existing;
        }
        var bar = document.createElement('div');
        bar.className = 'trend-reason-hold';
        bar.setAttribute('role', 'status');
        bar.innerHTML = (
            '<div class="is-flex is-justify-content-space-between is-align-items-flex-start is-flex-wrap-wrap" style="gap:0.35rem">' +
            '<span class="is-size-7 has-text-weight-semibold" style="line-height:1.35">Reason hold</span>' +
            '<button type="button" class="button is-small is-light js-trend-reason-release">Release</button>' +
            '</div>' +
            '<p class="is-size-7 has-text-grey mb-0 mt-1">Pinned until Release is clicked or Esc is pressed — hover does not change this text.</p>'
        );
        aside.insertBefore(bar, aside.firstChild);
        bar.querySelector('.js-trend-reason-release').addEventListener('click', function (e) {
            e.preventDefault();
            onRelease();
        });
        return bar;
    }

    function _wireHover(plotEl, spec, listId) {
        var meta = spec && spec.trendMeta;
        if (!plotEl || !meta) return;
        var defaults = meta.defaultLines || [];
        var points = meta.points || [];
        var aside = _findAside(listId);
        var kind = meta.kind || (listId.indexOf('rank') !== -1 ? 'rank' : 'score');

        var state = {pinnedIdx: null, lastHoverIdx: -1};

        function renderEntry(idx) {
            var pt = points[idx];
            if (pt && pt.lines) _renderAttributionList(listId, pt.lines);
        }
        function renderDefault() {
            if (state.pinnedIdx !== null) return;
            _renderAttributionList(listId, defaults);
        }
        function clearPin() {
            state.pinnedIdx = null;
            state.lastHoverIdx = -1;
            if (holdBar) holdBar.classList.remove('is-active');
            if (aside) aside.classList.remove('trend-attribution-panel--pinned');
            _renderAttributionList(listId, defaults);
        }
        function setPin(idx) {
            if (idx < 0 || idx >= points.length) return;
            var pt = points[idx];
            if (!pt || !pt.lines) return;
            state.pinnedIdx = idx;
            state.lastHoverIdx = idx;
            _renderAttributionList(listId, pt.lines);
            if (holdBar) holdBar.classList.add('is-active');
            if (aside) aside.classList.add('trend-attribution-panel--pinned');
        }

        var holdBar = _ensureHoldBar(aside, clearPin);

        // Tear down listeners from a prior wire pass; dropdown changes call
        // _wireHover repeatedly and would otherwise stack handlers.
        ['plotly_hover', 'plotly_unhover'].forEach(function (ev) {
            plotEl.removeAllListeners && plotEl.removeAllListeners(ev);
        });
        if (plotEl.__compareTrendCleanup) plotEl.__compareTrendCleanup();
        var listeners = [];
        function on(target, type, handler, opts) {
            target.addEventListener(type, handler, opts);
            listeners.push([target, type, handler, opts]);
        }
        plotEl.__compareTrendCleanup = function () {
            listeners.forEach(function (l) { l[0].removeEventListener(l[1], l[2], l[3]); });
            listeners = [];
        };

        _panels[kind] = {clearPin: clearPin};

        renderDefault();

        _bindPlotlyHover(plotEl, function (ev) {
            if (state.pinnedIdx !== null) return;
            var i = _hoverIndex(ev);
            if (i < 0) return;
            state.lastHoverIdx = i;
            renderEntry(i);
        }, function () {
            // mouseleave on the tab panel owns clearing; not unhover, so
            // sliding off a marker but still over the plot keeps the entry.
        });

        on(plotEl, 'mousemove', function (e) {
            if (state.pinnedIdx !== null) return;
            var idx = _nearestIndexFromMouseX(plotEl, spec, e.clientX);
            if (idx < 0 || idx === state.lastHoverIdx) return;
            state.lastHoverIdx = idx;
            renderEntry(idx);
        });

        // Use the surrounding tab panel, not the plot div, so sliding to the
        // sidebar doesn't clear the explanation.
        var tabPanel = plotEl.closest('[id^="compare-trend-panel-"]');
        on(tabPanel || plotEl, 'mouseleave', function () {
            if (state.pinnedIdx !== null) return;
            state.lastHoverIdx = -1;
            renderDefault();
        });

        // Capture phase beats Plotly's plotly_unhover, so the index is still readable when we pin.
        function pinAtPointer(e) {
            if (e.button !== undefined && e.button !== 0) return;
            if (!_eventTouchesPlot(plotEl, e)) return;
            if (e.target && e.target.closest && e.target.closest('.modebar')) return;
            var idx = _nearestIndexFromMouseX(plotEl, spec, e.clientX);
            if (idx < 0) idx = state.lastHoverIdx;
            if (idx >= 0) setPin(idx);
        }
        on(plotEl, 'pointerdown', pinAtPointer, true);
        on(plotEl, 'click', pinAtPointer, true);
    }

    // One document-level Esc listener releases any pinned panel. Guarded so
    // repeated _wireHover calls don't pile up duplicate handlers.
    if (!window.__compareTrendEscBound) {
        document.addEventListener('keydown', function (e) {
            if (e.key !== 'Escape') return;
            ['score', 'rank'].forEach(function (kind) {
                var p = _panels[kind];
                if (p && typeof p.clearPin === 'function') p.clearPin();
            });
        });
        window.__compareTrendEscBound = true;
    }

    function _renderPair(payload) {
        if (typeof Plotly === 'undefined') {
            requestAnimationFrame(function () { _renderPair(payload); });
            return;
        }
        var scoreEl = document.getElementById('compare-score-trend-plot');
        var rankEl = document.getElementById('compare-rank-trend-plot');
        var haveScore = !!(payload && payload.score);
        var haveRank = !!(payload && payload.rank);
        if (!haveScore && !haveRank) {
            _renderEmpty('No overlapping historical data for these two models yet.');
            return;
        }
        _showContent();
        if (haveScore && scoreEl) {
            Plotly.react(scoreEl, payload.score.data, payload.score.layout, payload.score.config);
            _wireHover(scoreEl, payload.score, 'compare-score-attribution-list');
            _wireResponsiveResize(scoreEl);
        }
        if (haveRank && rankEl) {
            Plotly.react(rankEl, payload.rank.data, payload.rank.layout, payload.rank.config);
            _wireHover(rankEl, payload.rank, 'compare-rank-attribution-list');
            _wireResponsiveResize(rankEl);
        }
        // If only one kind is available, hide the other tab so users don't land on an empty panel.
        var scoreTab = document.querySelector('#compare-trend-tabs li[data-tab="score"]');
        var rankTab = document.querySelector('#compare-trend-tabs li[data-tab="rank"]');
        if (scoreTab) scoreTab.style.display = haveScore ? '' : 'none';
        if (rankTab) rankTab.style.display = haveRank ? '' : 'none';
        if (!haveScore && haveRank) _activateTab('rank');
    }

    function _activateTab(which) {
        ['score', 'rank'].forEach(function (kind) {
            var li = document.querySelector('#compare-trend-tabs li[data-tab="' + kind + '"]');
            var panel = document.getElementById('compare-trend-panel-' + kind);
            if (li) li.classList.toggle('is-active', kind === which);
            if (panel) panel.style.display = kind === which ? '' : 'none';
        });
        if (typeof Plotly !== 'undefined') {
            var el = document.getElementById('compare-' + which + '-trend-plot');
            if (el && el.data) Plotly.Plots.resize(el);
        }
    }

    var _pendingAbort = null;
    function _fetchAndRender(midA, midB) {
        if (!endpoint) return;
        if (_pendingAbort) _pendingAbort.abort();
        var controller = new AbortController();
        _pendingAbort = controller;
        var url = endpoint + '?mid_a=' + encodeURIComponent(midA) + '&mid_b=' + encodeURIComponent(midB);
        fetch(url, {signal: controller.signal, headers: {'Accept': 'application/json'}})
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (payload) {
                if (controller.signal.aborted) return;
                if (!payload) { _renderEmpty('Could not load comparison trend.'); return; }
                try { _renderPair(payload); }
                catch (e) { _renderEmpty('Could not render comparison trend: ' + (e && e.message || e)); }
            })
            .catch(function (e) {
                if (e && e.name === 'AbortError') return;
                _renderEmpty('Could not load comparison trend: ' + (e && e.message || e));
            });
    }

    function _selectedId(selectId) {
        var el = document.getElementById(selectId);
        if (!el) return null;
        var name = el.value;
        if (!name) return null;
        if (typeof model_metadata === 'undefined') return null;
        var meta = model_metadata[name];
        return meta && meta.model_id ? meta.model_id : null;
    }

    function _onSelectionChange() {
        var midA = _selectedId('model-x-select');
        var midB = _selectedId('model-y-select');
        if (!midA || !midB) {
            _renderEmpty('Select two different models to see how their average_vision score and rank have evolved over time.');
            return;
        }
        if (midA === midB) {
            _renderEmpty('Pick two different models to compare their trends.');
            return;
        }
        _fetchAndRender(midA, midB);
    }

    function _wireTabs() {
        document.querySelectorAll('.js-compare-trend-tab').forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                _activateTab(link.dataset.tab);
            });
        });
    }

    function _init() {
        _wireTabs();
        // Select2 fires 'change' via jQuery.trigger(); native addEventListener
        // doesn't always see it, so bind through jQuery when available.
        if (typeof jQuery === 'undefined') {
            ['model-x-select', 'model-y-select'].forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.addEventListener('change', _onSelectionChange);
            });
        } else {
            jQuery('#model-x-select, #model-y-select').on('change', _onSelectionChange);
        }
        _onSelectionChange();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _init);
    } else {
        _init();
    }
})();
