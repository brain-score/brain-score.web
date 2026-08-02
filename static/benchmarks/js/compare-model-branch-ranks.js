(function (root, factory) {
    'use strict';

    var core = factory();
    if (typeof module === 'object' && module.exports) module.exports = core;
    root.CompareModelBranchRanksCore = core;

    function initialize() {
        if (!root.document || !root.compare_dashboard_data || !root.CompareDashboard) return;
        if (!root.document.getElementById('model-branch-rank-panel')) return;
        root.CompareModelBranchRanks = core.createBranchRankPlot(
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
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    var MODEL_A_COLOR = '#45C676';
    var MODEL_B_COLOR = '#47B7DE';

    function branchLabel(benchmark) {
        var labels = {
            average_vision: 'Overall Vision',
            neural_vision: 'Neural',
            behavior_vision: 'Behavioral',
            average_language: 'Overall Language',
            neural_language: 'Neural',
            behavior_language: 'Behavioral'
        };
        return labels[benchmark.type_id] || benchmark.label || benchmark.type_id;
    }

    function selectRankBranches(benchmarks, domain) {
        var typeOrder = domain === 'vision'
            ? ['average_vision', 'neural_vision', 'V1', 'V2', 'V4', 'IT', 'behavior_vision']
            : ['average_' + domain, 'neural_' + domain, 'behavior_' + domain];
        var byType = {};
        (benchmarks || []).forEach(function (benchmark) { byType[benchmark.type_id] = benchmark; });
        return typeOrder.map(function (typeId) { return byType[typeId]; }).filter(function (benchmark) {
            return !!benchmark && !benchmark.is_engineering;
        });
    }

    function finiteScore(value) {
        if (value === null || value === undefined || value === '') return null;
        var numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : null;
    }

    function rankRows(rows, benchmarkId) {
        var ranked = (rows || []).map(function (row) {
            return {
                modelId: row.model_id,
                model: row.model,
                score: finiteScore(row[benchmarkId + '-score'])
            };
        }).filter(function (row) { return row.score !== null; }).sort(function (left, right) {
            return right.score - left.score || String(left.model).localeCompare(String(right.model));
        });
        var previousScore = null;
        var previousRank = 0;
        ranked.forEach(function (row, index) {
            if (previousScore !== null && row.score === previousScore) {
                row.rank = previousRank;
            } else {
                row.rank = index + 1;
                previousRank = row.rank;
                previousScore = row.score;
            }
        });
        return ranked;
    }

    function buildBranchRanks(benchmarks, rows, domain, modelIdA, modelIdB) {
        return selectRankBranches(benchmarks, domain).map(function (benchmark) {
            var ranked = rankRows(rows, benchmark.id);
            var modelA = ranked.find(function (row) { return String(row.modelId) === String(modelIdA); });
            var modelB = ranked.find(function (row) { return String(row.modelId) === String(modelIdB); });
            if (!modelA || !modelB) return null;
            return {
                benchmark: branchLabel(benchmark),
                rankA: modelA.rank,
                rankB: modelB.rank,
                scoreA: modelA.score,
                scoreB: modelB.score,
                eligibleModels: ranked.length
            };
        }).filter(function (row) { return row !== null; });
    }

    function buildPlotlyBranchRanks(branchRanks, options) {
        options = options || {};
        var labels = branchRanks.map(function (row) { return row.benchmark; });
        var lineX = [];
        var lineY = [];
        branchRanks.forEach(function (row) {
            lineX.push(row.rankA, row.rankB, null);
            lineY.push(row.benchmark, row.benchmark, null);
        });
        var maximumRank = Math.max.apply(null, branchRanks.map(function (row) {
            return Math.max(row.rankA, row.rankB);
        }).concat([2]));
        return {
            data: [
                {
                    x: lineX,
                    y: lineY,
                    type: 'scatter',
                    mode: 'lines',
                    line: {color: '#cdd6d0', width: 3},
                    hoverinfo: 'skip',
                    showlegend: false
                },
                {
                    x: branchRanks.map(function (row) { return row.rankA; }),
                    y: labels,
                    customdata: branchRanks.map(function (row) {
                        return [row.scoreA, row.eligibleModels];
                    }),
                    type: 'scatter',
                    mode: 'markers',
                    name: options.nameA || 'Model A',
                    marker: {color: MODEL_A_COLOR, size: 13, symbol: 'circle'},
                    hovertemplate: '<b>%{y}</b><br>Rank: %{x}<br>Score: %{customdata[0]:.3f}<br>Eligible models: %{customdata[1]}<extra></extra>'
                },
                {
                    x: branchRanks.map(function (row) { return row.rankB; }),
                    y: labels,
                    customdata: branchRanks.map(function (row) {
                        return [row.scoreB, row.eligibleModels];
                    }),
                    type: 'scatter',
                    mode: 'markers',
                    name: options.nameB || 'Model B',
                    marker: {color: MODEL_B_COLOR, size: 13, symbol: 'diamond'},
                    hovertemplate: '<b>%{y}</b><br>Rank: %{x}<br>Score: %{customdata[0]:.3f}<br>Eligible models: %{customdata[1]}<extra></extra>'
                }
            ],
            layout: {
                height: Math.max(360, branchRanks.length * 55 + 150),
                margin: {t: 45, r: 35, b: 65, l: 145},
                paper_bgcolor: '#ffffff',
                plot_bgcolor: '#ffffff',
                font: {family: "'Open Sans', Arial, sans-serif", color: '#26342d'},
                hovermode: 'closest',
                legend: {orientation: 'h', x: 0, y: 1.12},
                xaxis: {
                    title: 'Rank within branch (1 is best)',
                    range: [0.5, maximumRank + 0.5],
                    tick0: 1,
                    dtick: maximumRank <= 12 ? 1 : undefined,
                    gridcolor: '#edf1ee',
                    zeroline: false
                },
                yaxis: {
                    categoryorder: 'array',
                    categoryarray: labels.slice().reverse(),
                    automargin: true,
                    gridcolor: '#f1f4f2'
                },
                images: options.logoUrl ? [{
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
                displayModeBar: true,
                modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                toImageButtonOptions: {
                    format: 'svg',
                    filename: 'brain-score-model-rank-by-branch'
                }
            }
        };
    }

    function escapeCsv(value) {
        var text = String(value === null || value === undefined ? '' : value);
        return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }

    function branchRanksToCsv(branchRanks, nameA, nameB) {
        var rows = [[
            'benchmark_branch', (nameA || 'model_a') + '_rank', (nameA || 'model_a') + '_score',
            (nameB || 'model_b') + '_rank', (nameB || 'model_b') + '_score', 'eligible_models'
        ]];
        (branchRanks || []).forEach(function (row) {
            rows.push([
                row.benchmark, row.rankA, row.scoreA,
                row.rankB, row.scoreB, row.eligibleModels
            ]);
        });
        return rows.map(function (row) { return row.map(escapeCsv).join(','); }).join('\n');
    }

    function downloadText(document, contents) {
        var browserRoot = document.defaultView || {};
        var blob = new browserRoot.Blob([contents], {type: 'text/csv;charset=utf-8'});
        var url = browserRoot.URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'brain-score-model-rank-by-branch.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        browserRoot.URL.revokeObjectURL(url);
    }

    function createBranchRankPlot(payload, dashboard, document) {
        var container = document.getElementById('model-branch-rank-plot');
        var empty = document.getElementById('model-branch-rank-empty');
        var downloadSvg = document.getElementById('model-branch-rank-download-svg');
        var downloadCsv = document.getElementById('model-branch-rank-download-csv');
        var browserRoot = document.defaultView || {};
        var plotly = browserRoot.Plotly;
        var latestRanks = [];
        var latestDetail = {};

        function render(detail) {
            latestDetail = detail || {};
            if (!latestDetail.modelIdA || !latestDetail.modelIdB || !plotly) {
                latestRanks = [];
            } else {
                latestRanks = buildBranchRanks(
                    payload.benchmarks,
                    dashboard.getLatestComparisonData(),
                    payload.domain,
                    latestDetail.modelIdA,
                    latestDetail.modelIdB
                );
            }
            var hasData = latestRanks.length > 0;
            container.style.display = hasData ? '' : 'none';
            if (empty) empty.style.display = hasData ? 'none' : '';
            if (!hasData) {
                if (plotly) plotly.purge(container);
                return;
            }
            var plot = buildPlotlyBranchRanks(latestRanks, {
                nameA: latestDetail.nameA,
                nameB: latestDetail.nameB,
                logoUrl: browserRoot.logo_url
            });
            plotly.react(container, plot.data, plot.layout, plot.config);
        }

        document.addEventListener('compare-models:change', function (event) {
            render(event.detail || {});
        });
        if (downloadSvg) downloadSvg.addEventListener('click', function () {
            if (!latestRanks.length || !plotly) return;
            plotly.downloadImage(container, {
                format: 'svg',
                filename: 'brain-score-model-rank-by-branch'
            });
        });
        if (downloadCsv) downloadCsv.addEventListener('click', function () {
            if (!latestRanks.length) return;
            downloadText(document, branchRanksToCsv(
                latestRanks,
                latestDetail.nameA,
                latestDetail.nameB
            ));
        });
        if (browserRoot.CompareModelsCurrent) render(browserRoot.CompareModelsCurrent);

        return {getRanks: function () { return latestRanks.slice(); }};
    }

    return {
        branchLabel: branchLabel,
        branchRanksToCsv: branchRanksToCsv,
        buildBranchRanks: buildBranchRanks,
        buildPlotlyBranchRanks: buildPlotlyBranchRanks,
        createBranchRankPlot: createBranchRankPlot,
        rankRows: rankRows,
        selectRankBranches: selectRankBranches
    };
}));
