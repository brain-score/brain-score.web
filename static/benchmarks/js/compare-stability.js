(function (root, factory) {
    'use strict';

    var dashboardCore = root.CompareDashboardCore;
    var correlationCore = root.CompareCorrelationCore;
    if (typeof module === 'object' && module.exports) {
        dashboardCore = require('./compare-dashboard.js');
        correlationCore = require('./compare-correlation.js');
    }
    var core = factory(dashboardCore, correlationCore);
    if (typeof module === 'object' && module.exports) module.exports = core;
    root.CompareStabilityCore = core;

    function initialize() {
        if (!root.document || !root.CompareDashboard || !root.compare_dashboard_data) return;
        if (!root.document.getElementById('benchmark-correlation-stability-panel')) return;
        root.CompareStability = core.createStabilityPlot(
            root.compare_dashboard_data,
            root.CompareDashboard,
            root.document
        );
    }

    if (root.document) {
        if (root.document.readyState === 'loading') {
            root.document.addEventListener('DOMContentLoaded', initialize);
        } else {
            initialize();
        }
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function (dashboardCore, correlationCore) {
    'use strict';

    function stabilitySnapshotDates(minimumDate, maximumDate) {
        var minimum = new Date(String(minimumDate).slice(0, 10) + 'T00:00:00.000Z');
        var maximum = new Date(String(maximumDate).slice(0, 10) + 'T00:00:00.000Z');
        if (!Number.isFinite(minimum.getTime()) || !Number.isFinite(maximum.getTime()) || minimum > maximum) {
            return [];
        }
        var dates = [];
        var recentStart = new Date(Date.UTC(
            maximum.getUTCFullYear(),
            maximum.getUTCMonth() - 11,
            1
        ));
        var cursor = new Date(Date.UTC(minimum.getUTCFullYear(), minimum.getUTCMonth() + 1, 0));
        while (cursor <= maximum) {
            var isRecent = cursor >= recentStart;
            var isQuarterEnd = [2, 5, 8, 11].indexOf(cursor.getUTCMonth()) !== -1;
            if (isRecent || isQuarterEnd) dates.push(cursor.toISOString().slice(0, 10));
            cursor = new Date(Date.UTC(cursor.getUTCFullYear(), cursor.getUTCMonth() + 2, 0));
        }
        var maximumValue = maximum.toISOString().slice(0, 10);
        if (!dates.length || dates[dates.length - 1] !== maximumValue) dates.push(maximumValue);
        return dates;
    }

    function pairedCorrelation(rows, firstBenchmarkId, secondBenchmarkId) {
        var left = [];
        var right = [];
        (rows || []).forEach(function (row) {
            var first = correlationCore.validMatrixScore(row[firstBenchmarkId + '-score']);
            var second = correlationCore.validMatrixScore(row[secondBenchmarkId + '-score']);
            if (first === null || second === null) return;
            if (row[firstBenchmarkId + '-is_complete'] != 1 || row[secondBenchmarkId + '-is_complete'] != 1) return;
            left.push(first);
            right.push(second);
        });
        return correlationCore.pearsonCorrelation(left, right, 2);
    }

    function buildStabilitySeries(payload, options) {
        options = options || {};
        var dates = options.dates || stabilitySnapshotDates(
            payload.datetime_range.min || new Date(Number(payload.datetime_range.min_unix) * 1000).toISOString(),
            payload.datetime_range.max || new Date(Number(payload.datetime_range.max_unix) * 1000).toISOString()
        );
        return dates.map(function (date) {
            var resolved = dashboardCore.resolveCohort(payload, {
                asOfDate: date,
                minimumCompleteness: options.minimumCompleteness || 0,
                comparisonBenchmarkIds: [options.firstBenchmarkId, options.secondBenchmarkId]
            });
            var correlation = pairedCorrelation(
                resolved.rows,
                options.firstBenchmarkId,
                options.secondBenchmarkId
            );
            return {date: date, r: correlation.r, n: correlation.n};
        });
    }

    function escapeCsv(value) {
        var text = String(value === null || value === undefined ? '' : value);
        return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }

    function stabilityToCsv(series, options) {
        options = options || {};
        var rows = [[
            'date', 'pearson_r', 'paired_models', 'horizontal_benchmark',
            'vertical_benchmark', 'minimum_completedness_percent'
        ]];
        (series || []).forEach(function (point) {
            rows.push([
                point.date,
                point.r === null ? '' : point.r,
                point.n,
                options.firstLabel || '',
                options.secondLabel || '',
                options.minimumCompleteness || 0
            ]);
        });
        return rows.map(function (row) { return row.map(escapeCsv).join(','); }).join('\n');
    }

    function compactDateTicks(dates) {
        if (!dates.length) return [];
        var indexes = dates.length < 3
            ? dates.map(function (_date, index) { return index; })
            : [0, Math.floor((dates.length - 1) / 2), dates.length - 1];
        return indexes.filter(function (index, position) {
            return indexes.indexOf(index) === position;
        }).map(function (index) {
            return {
                value: dates[index],
                label: dates[index].slice(0, 7)
            };
        });
    }

    function buildPlotlyStability(series, options) {
        options = options || {};
        var compact = !!options.compact;
        var dates = series.map(function (point) { return point.date; });
        var counts = series.map(function (point) { return point.n; });
        var correlations = series.map(function (point) { return point.r; });
        var compactTicks = compactDateTicks(dates);
        return {
            data: [
                {
                    x: dates,
                    y: counts,
                    type: 'bar',
                    name: 'Paired models',
                    yaxis: 'y2',
                    marker: {color: 'rgba(97, 112, 105, 0.18)'},
                    hovertemplate: '%{x}<br>Paired models: %{y}<extra></extra>'
                },
                {
                    x: dates,
                    y: correlations,
                    customdata: counts,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'Pearson r',
                    connectgaps: false,
                    line: {color: '#078930', width: 2},
                    marker: {color: '#078930', size: 6},
                    hovertemplate: '%{x}<br>Pearson r: %{y:.3f}<br>Paired models: %{customdata}<extra></extra>'
                }
            ],
            layout: {
                height: compact ? 230 : (options.expandedHeight || 640),
                margin: compact ? {t: 8, r: 10, b: 30, l: 35} : {t: 45, r: 75, b: 65, l: 70},
                paper_bgcolor: '#ffffff',
                plot_bgcolor: '#ffffff',
                font: {family: "'Open Sans', Arial, sans-serif", color: '#26342d'},
                bargap: 0.08,
                hovermode: compact ? false : 'x unified',
                showlegend: !compact,
                legend: {orientation: 'h', x: 0, y: 1.08},
                xaxis: compact ? {
                    tickmode: 'array',
                    tickvals: compactTicks.map(function (tick) { return tick.value; }),
                    ticktext: compactTicks.map(function (tick) { return tick.label; }),
                    tickfont: {size: 9},
                    fixedrange: true,
                    gridcolor: '#edf1ee'
                } : {
                    title: 'Wayback date',
                    gridcolor: '#edf1ee'
                },
                yaxis: {
                    title: compact ? '' : 'Pearson r',
                    range: [-1.05, 1.05],
                    tickmode: compact ? 'array' : 'auto',
                    tickvals: compact ? [-1, 0, 1] : undefined,
                    tickfont: compact ? {size: 9} : undefined,
                    fixedrange: compact,
                    zerolinecolor: '#cfd8d2',
                    gridcolor: '#edf1ee'
                },
                yaxis2: {
                    title: compact ? '' : 'Paired models',
                    overlaying: 'y',
                    side: 'right',
                    rangemode: 'tozero',
                    showgrid: false,
                    showticklabels: !compact,
                    fixedrange: compact
                },
                shapes: options.currentDate ? [{
                    type: 'line',
                    x0: options.currentDate,
                    x1: options.currentDate,
                    y0: 0,
                    y1: 1,
                    xref: 'x',
                    yref: 'paper',
                    line: {color: '#26342d', width: 1, dash: 'dot'}
                }] : [],
                images: !compact && options.logoUrl ? [{
                    source: options.logoUrl,
                    xref: 'paper',
                    yref: 'paper',
                    x: 1,
                    y: 0,
                    sizex: 0.16,
                    sizey: 0.10,
                    xanchor: 'right',
                    yanchor: 'bottom',
                    layer: 'above'
                }] : []
            },
            config: {
                responsive: true,
                displaylogo: false,
                displayModeBar: !compact,
                staticPlot: compact,
                scrollZoom: !compact,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                toImageButtonOptions: {
                    format: 'svg',
                    filename: 'brain-score-benchmark-correlation-stability'
                }
            }
        };
    }

    function downloadText(document, contents, filename, mimeType) {
        var browserRoot = document.defaultView || {};
        var blob = new browserRoot.Blob([contents], {type: mimeType});
        var url = browserRoot.URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        browserRoot.URL.revokeObjectURL(url);
    }

    function createStabilityPlot(payload, dashboard, document) {
        var container = document.getElementById('benchmark-correlation-stability');
        var empty = document.getElementById('benchmark-correlation-stability-empty');
        var downloadSvg = document.getElementById('benchmark-stability-download-svg');
        var downloadCsv = document.getElementById('benchmark-stability-download-csv');
        var expandButton = document.getElementById('benchmark-stability-expand');
        var panel = document.getElementById('benchmark-correlation-stability-panel');
        var browserRoot = document.defaultView || {};
        var plotly = browserRoot.Plotly;
        var latestSeries = [];
        var latestOptions = {};
        var seriesKey = null;
        var expanded = false;

        function selection() {
            var first = document.getElementById('xlabel');
            var second = document.getElementById('ylabel');
            return {
                firstBenchmarkId: first ? first.value : null,
                secondBenchmarkId: second ? second.value : null,
                firstLabel: first && first.options[first.selectedIndex] ? first.options[first.selectedIndex].text : '',
                secondLabel: second && second.options[second.selectedIndex] ? second.options[second.selectedIndex].text : ''
            };
        }

        function render(_resolved, state) {
            var selected = selection();
            if (!selected.firstBenchmarkId || !selected.secondBenchmarkId || !plotly) return;
            var nextKey = [
                selected.firstBenchmarkId,
                selected.secondBenchmarkId,
                state.minimumCompleteness
            ].join('|');
            if (nextKey !== seriesKey) {
                latestSeries = buildStabilitySeries(payload, {
                    firstBenchmarkId: selected.firstBenchmarkId,
                    secondBenchmarkId: selected.secondBenchmarkId,
                    minimumCompleteness: state.minimumCompleteness
                });
                seriesKey = nextKey;
            }
            latestOptions = {
                firstLabel: selected.firstLabel,
                secondLabel: selected.secondLabel,
                minimumCompleteness: state.minimumCompleteness,
                currentDate: state.asOfDate,
                logoUrl: browserRoot.logo_url,
                compact: !expanded,
                expandedHeight: Math.max(500, (browserRoot.innerHeight || 800) - 210)
            };
            var hasCorrelation = latestSeries.some(function (point) { return point.r !== null; });
            if (empty) empty.style.display = hasCorrelation ? 'none' : '';
            container.style.display = hasCorrelation ? '' : 'none';
            if (!hasCorrelation) return;

            var plot = buildPlotlyStability(latestSeries, latestOptions);
            plotly.react(container, plot.data, plot.layout, plot.config).then(function () {
                if (container.__stabilityClickBound || typeof container.on !== 'function') return;
                container.on('plotly_click', function (event) {
                    var point = event && event.points && event.points[0];
                    if (point && point.x) dashboard.setAsOfDate(String(point.x).slice(0, 10));
                });
                container.__stabilityClickBound = true;
            });
        }

        dashboard.subscribe(render);
        function setExpanded(nextExpanded) {
            expanded = nextExpanded;
            if (panel) panel.classList.toggle('is-expanded', expanded);
            if (document.body) document.body.classList.toggle('benchmark-stability-expanded', expanded);
            if (expandButton) {
                var expandAction = expanded ? 'Collapse' : 'Expand';
                var expandIcon = expandButton.querySelector('i');
                if (expandIcon) {
                    expandIcon.className = expanded
                        ? 'fa-solid fa-down-left-and-up-right-to-center'
                        : 'fa-solid fa-up-right-and-down-left-from-center';
                }
                expandButton.setAttribute('aria-pressed', expanded ? 'true' : 'false');
                expandButton.setAttribute('aria-label', expandAction);
                expandButton.title = expandAction;
            }
            // Rebuild when changing interaction modes so Plotly re-enables
            // hover immediately after leaving the compact static view.
            if (plotly && container) {
                plotly.purge(container);
                container.__stabilityClickBound = false;
            }
            if (dashboard.getState) render(null, dashboard.getState());
        }
        if (expandButton) expandButton.addEventListener('click', function () {
            setExpanded(!expanded);
        });
        document.addEventListener('keydown', function (event) {
            if (expanded && event.key === 'Escape') setExpanded(false);
        });
        if (downloadSvg) downloadSvg.addEventListener('click', function () {
            if (!latestSeries.length || !plotly) return;
            plotly.downloadImage(container, {
                format: 'svg',
                filename: 'brain-score-benchmark-correlation-stability'
            });
        });
        if (downloadCsv) downloadCsv.addEventListener('click', function () {
            if (!latestSeries.length) return;
            downloadText(
                document,
                stabilityToCsv(latestSeries, latestOptions),
                'brain-score-benchmark-correlation-stability.csv',
                'text/csv;charset=utf-8'
            );
        });

        return {
            getSeries: function () { return latestSeries.slice(); },
            isExpanded: function () { return expanded; }
        };
    }

    return {
        buildPlotlyStability: buildPlotlyStability,
        buildStabilitySeries: buildStabilitySeries,
        compactDateTicks: compactDateTicks,
        createStabilityPlot: createStabilityPlot,
        stabilitySnapshotDates: stabilitySnapshotDates,
        pairedCorrelation: pairedCorrelation,
        stabilityToCsv: stabilityToCsv
    };
}));
