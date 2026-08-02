(function (root, factory) {
    'use strict';

    var core = factory();
    if (typeof module === 'object' && module.exports) module.exports = core;
    root.CompareModelBranchRanksCore = core;
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

    function buildBranchRankOverlay(branchRanks, options) {
        options = options || {};
        var labels = branchRanks.map(function (row) { return row.benchmark; });
        var connectorX = [];
        var connectorY = [];
        branchRanks.forEach(function (row) {
            connectorX.push(row.benchmark, row.benchmark, null);
            connectorY.push(row.rankA, row.rankB, null);
        });
        var maximumRank = Math.max.apply(null, branchRanks.map(function (row) {
            return Math.max(row.rankA, row.rankB);
        }).concat([2]));
        return {
            data: [
                {
                    x: connectorX,
                    y: connectorY,
                    type: 'scatter',
                    mode: 'lines',
                    yaxis: 'y2',
                    showlegend: false,
                    hoverinfo: 'skip',
                    line: {color: '#cdd6d0', width: 3}
                },
                {
                    x: labels,
                    y: branchRanks.map(function (row) { return row.rankA; }),
                    customdata: branchRanks.map(function (row) {
                        return [row.scoreA, row.eligibleModels];
                    }),
                    type: 'scatter',
                    mode: 'markers',
                    name: (options.nameA || 'Model A') + ' branch rank',
                    yaxis: 'y2',
                    showlegend: false,
                    cliponaxis: false,
                    marker: {
                        color: MODEL_A_COLOR,
                        size: 11,
                        symbol: 'x'
                    },
                    hovertemplate: '<b>%{x}</b><br>Rank: %{y}<br>Summary score: %{customdata[0]:.3f}<br>Eligible models: %{customdata[1]}<extra>' + (options.nameA || 'Model A') + '</extra>'
                },
                {
                    x: labels,
                    y: branchRanks.map(function (row) { return row.rankB; }),
                    customdata: branchRanks.map(function (row) {
                        return [row.scoreB, row.eligibleModels];
                    }),
                    type: 'scatter',
                    mode: 'markers',
                    name: (options.nameB || 'Model B') + ' branch rank',
                    yaxis: 'y2',
                    showlegend: false,
                    cliponaxis: false,
                    marker: {
                        color: MODEL_B_COLOR,
                        size: 11,
                        symbol: 'x'
                    },
                    hovertemplate: '<b>%{x}</b><br>Rank: %{y}<br>Summary score: %{customdata[0]:.3f}<br>Eligible models: %{customdata[1]}<extra>' + (options.nameB || 'Model B') + '</extra>'
                }
            ],
            yaxis: {
                title: {text: 'Branch rank (1 is best)', font: {size: 14}},
                overlaying: 'y',
                side: 'right',
                range: [maximumRank + 1, 0],
                tick0: 1,
                dtick: maximumRank <= 12 ? 1 : undefined,
                tickfont: {size: 12},
                tickformat: ',d',
                hoverformat: ',d',
                automargin: true,
                showgrid: false,
                zeroline: false
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

    return {
        branchLabel: branchLabel,
        branchRanksToCsv: branchRanksToCsv,
        buildBranchRankOverlay: buildBranchRankOverlay,
        buildBranchRanks: buildBranchRanks,
        rankRows: rankRows,
        selectRankBranches: selectRankBranches
    };
}));
