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

    function resizePlots(panel, expanded, browserRoot) {
        var plotly = browserRoot.Plotly;
        if (plotly) {
            panel.querySelectorAll('.js-plotly-plot').forEach(function (plot) {
                if (!plot.data || !plot.layout) return;
                if (expanded) {
                    plot.__compareOriginalSize = {
                        height: plot.layout.height,
                        width: plot.layout.width
                    };
                    plotly.relayout(plot, {
                        height: expandedPlotHeight(browserRoot.innerHeight),
                        width: Math.max(420, plot.clientWidth || panel.clientWidth || 800),
                        autosize: false
                    });
                } else {
                    var original = plot.__compareOriginalSize || {};
                    plotly.relayout(plot, {
                        height: original.height === undefined ? null : original.height,
                        width: original.width === undefined ? null : original.width,
                        autosize: original.width === undefined
                    });
                    plot.__compareOriginalSize = null;
                }
                if (plotly.Plots && plotly.Plots.resize) plotly.Plots.resize(plot);
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
        expandIconClass: expandIconClass,
        expandedPlotHeight: expandedPlotHeight,
        initializeExpandButtons: initializeExpandButtons,
        resizePlots: resizePlots,
        updateButton: updateButton
    };
}));
