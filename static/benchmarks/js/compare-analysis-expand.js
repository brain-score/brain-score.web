(function (root, factory) {
    'use strict';

    var core = factory();
    if (typeof module === 'object' && module.exports) module.exports = core;
    root.CompareAnalysisExpandCore = core;

    function initialize() {
        if (!root.document) return;
        core.initializeExpandButtons(root.document, root);
    }

    if (root.document) {
        if (root.document.readyState === 'loading') {
            root.document.addEventListener('DOMContentLoaded', initialize);
        } else {
            initialize();
        }
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function expandIconClass(expanded) {
        return expanded
            ? 'fa-solid fa-down-left-and-up-right-to-center'
            : 'fa-solid fa-up-right-and-down-left-from-center';
    }

    function expandedPlotHeight(viewportHeight) {
        return Math.max(480, Number(viewportHeight || 800) - 230);
    }

    function updateButton(button, expanded) {
        var action = expanded ? 'Collapse' : 'Expand';
        var icon = button.querySelector('i');
        if (icon) icon.className = expandIconClass(expanded);
        button.setAttribute('aria-pressed', expanded ? 'true' : 'false');
        button.setAttribute('aria-label', action);
        button.title = action;
    }

    function finiteDimension(value) {
        value = Number(value);
        return Number.isFinite(value) && value > 0 ? value : null;
    }

    function collapsedPlotSize(plot) {
        if (plot.__compareCollapsedSize) return plot.__compareCollapsedSize;
        var layout = plot.layout || {};
        var fullLayout = plot._fullLayout || {};
        plot.__compareCollapsedSize = {
            height: finiteDimension(layout.height) ||
                finiteDimension(fullLayout.height) ||
                finiteDimension(plot.clientHeight) ||
                480,
            width: finiteDimension(layout.width),
            autosize: layout.autosize !== false
        };
        return plot.__compareCollapsedSize;
    }

    function resizeAfterRelayout(plot, plotly, browserRoot, update) {
        function resize() {
            var callback = function () {
                if (plotly.Plots && plotly.Plots.resize) plotly.Plots.resize(plot);
            };
            if (typeof browserRoot.requestAnimationFrame === 'function') {
                browserRoot.requestAnimationFrame(callback);
            } else {
                callback();
            }
        }
        var relayout = plotly.relayout(plot, update);
        if (relayout && typeof relayout.then === 'function') relayout.then(resize);
        else resize();
    }

    function resizePlots(panel, expanded, browserRoot) {
        var plotly = browserRoot.Plotly;
        if (plotly) {
            panel.querySelectorAll('.js-plotly-plot').forEach(function (plot) {
                if (!plot.data || !plot.layout) return;
                var original = collapsedPlotSize(plot);
                if (expanded) {
                    resizeAfterRelayout(plot, plotly, browserRoot, {
                        height: expandedPlotHeight(browserRoot.innerHeight),
                        width: null,
                        autosize: true
                    });
                } else {
                    resizeAfterRelayout(plot, plotly, browserRoot, {
                        height: original.height,
                        width: original.width,
                        autosize: original.autosize
                    });
                }
            });
        }
        if (typeof browserRoot.dispatchEvent === 'function' && typeof browserRoot.Event === 'function') {
            browserRoot.dispatchEvent(new browserRoot.Event('resize'));
        }
    }

    function initializeExpandButtons(document, browserRoot) {
        var active = null;

        function setExpanded(controller, expanded) {
            if (expanded && active && active !== controller) setExpanded(active, false);
            controller.panel.classList.toggle('is-expanded-plot', expanded);
            document.body.classList.toggle('compare-analysis-plot-expanded', expanded);
            updateButton(controller.button, expanded);
            active = expanded ? controller : null;
            browserRoot.requestAnimationFrame(function () {
                resizePlots(controller.panel, expanded, browserRoot);
            });
        }

        document.querySelectorAll('.js-compare-analysis-expand').forEach(function (button) {
            var panel = document.getElementById(button.getAttribute('data-expand-panel'));
            if (!panel) return;
            var controller = {button: button, panel: panel};
            updateButton(button, false);
            button.addEventListener('click', function () {
                setExpanded(controller, !panel.classList.contains('is-expanded-plot'));
            });
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && active) setExpanded(active, false);
        });
    }

    return {
        collapsedPlotSize: collapsedPlotSize,
        expandIconClass: expandIconClass,
        expandedPlotHeight: expandedPlotHeight,
        initializeExpandButtons: initializeExpandButtons,
        resizePlots: resizePlots,
        updateButton: updateButton
    };
}));
