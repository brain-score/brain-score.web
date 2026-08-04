(function (root, factory) {
    'use strict';

    var core = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = core;
    }
    root.CompareCorrelationCore = core;
    var initialized = false;

    function initialize() {
        if (initialized || !root.document || !root.CompareDashboard || !root.compare_dashboard_data) return;
        if (!root.document.getElementById('benchmark-correlation-explorer')) return;
        initialized = true;
        root.CompareCorrelation = core.createExplorer(
            root.compare_dashboard_data,
            root.CompareDashboard,
            root.document
        );
    }

    if (root.document) {
        root.document.addEventListener('compare-dashboard:ready', initialize);
        if (root.document.readyState === 'loading') {
            root.document.addEventListener('DOMContentLoaded', initialize);
        } else {
            initialize();
        }
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    var SELECT = 'select';
    var HIDE = 'hide';
    var DESELECT = 'deselect';
    var DEFAULT_SELECTED_TYPES = {
        neural_vision: true,
        V1: true,
        V2: true,
        V4: true,
        IT: true,
        behavior_vision: true
    };
    var CORRELATION_PRESETS = [
        {
            id: 'rdm',
            label: 'RDM',
            description: 'Compare active benchmark leaves whose names contain RDM.',
            kind: 'metric',
            token: 'rdm'
        },
        {
            id: 'ridge',
            label: 'Ridge',
            description: 'Compare active benchmark leaves whose names contain ridge.',
            kind: 'metric',
            token: 'ridge'
        },
        {
            id: 'nsd-stimuli',
            label: 'NSD stimuli',
            description: 'Compare Allen2022, Li2026, and Zerbe2026 benchmark leaves.',
            kind: 'families',
            prefixes: ['allen2022', 'li2026', 'zerbe2026']
        },
        {
            id: 'things-stimuli',
            label: 'THINGS stimuli',
            description: 'Compare Papale, Hebart fMRI, and Gifford benchmark leaves.',
            kind: 'families',
            prefixes: ['papale', 'hebart2023_fmri', 'gifford']
        },
        {
            id: 'fmri',
            label: 'fMRI',
            description: 'Compare active benchmark leaves whose names contain fMRI.',
            kind: 'metric',
            token: 'fmri'
        }
    ];

    function buildHierarchy(benchmarks) {
        var byId = {};
        var childrenById = {};
        var parentById = {};
        var orderById = {};
        (benchmarks || []).forEach(function (benchmark, index) {
            byId[benchmark.id] = benchmark;
            childrenById[benchmark.id] = [];
            orderById[benchmark.id] = index;
        });
        (benchmarks || []).forEach(function (benchmark) {
            if (benchmark.parent_id && childrenById[benchmark.parent_id]) {
                childrenById[benchmark.parent_id].push(benchmark.id);
                parentById[benchmark.id] = benchmark.parent_id;
            }
        });
        return {
            byId: byId,
            childrenById: childrenById,
            parentById: parentById,
            orderById: orderById,
            roots: (benchmarks || []).filter(function (benchmark) {
                return !parentById[benchmark.id];
            }).map(function (benchmark) { return benchmark.id; })
        };
    }

    function createDefaultModes(benchmarks) {
        var modes = {};
        var foundPreferred = false;
        (benchmarks || []).forEach(function (benchmark) {
            if (benchmark.is_engineering) {
                modes[benchmark.id] = DESELECT;
            } else if (DEFAULT_SELECTED_TYPES[benchmark.type_id]) {
                modes[benchmark.id] = SELECT;
                foundPreferred = true;
            } else {
                modes[benchmark.id] = HIDE;
            }
        });
        if (!foundPreferred) {
            var hierarchy = buildHierarchy(benchmarks);
            (benchmarks || []).forEach(function (benchmark) {
                var parent = hierarchy.byId[benchmark.parent_id];
                if (parent && !parent.parent_id && !benchmark.is_engineering) {
                    modes[benchmark.id] = SELECT;
                }
            });
        }
        return modes;
    }

    function selectAllBenchmarks(currentModes, benchmarks, activeBenchmarkIds) {
        var next = Object.assign({}, currentModes);
        (benchmarks || []).forEach(function (benchmark) {
            if (benchmark.is_engineering) {
                next[benchmark.id] = DESELECT;
            } else if (activeBenchmarkIds[benchmark.id]) {
                next[benchmark.id] = SELECT;
            }
        });
        return next;
    }

    function benchmarkSearchTokens(benchmark) {
        return [benchmark.id, benchmark.type_id, benchmark.label]
            .filter(Boolean)
            .join(' ')
            .toLowerCase()
            .split(/[^a-z0-9]+/)
            .filter(Boolean);
    }

    function benchmarkContainsToken(benchmark, token) {
        var normalizedToken = String(token || '').toLowerCase();
        return benchmarkSearchTokens(benchmark).some(function (candidate) {
            return candidate.indexOf(normalizedToken) === 0;
        });
    }

    function presetDefinition(presetId) {
        return CORRELATION_PRESETS.find(function (preset) { return preset.id === presetId; });
    }

    function matchingPresetBenchmarkIds(presetId, benchmarks) {
        var preset = presetDefinition(presetId);
        if (!preset) return [];
        var leaves = (benchmarks || []).filter(function (benchmark) {
            return benchmark.is_leaf && !benchmark.is_engineering;
        });

        if (preset.kind === 'metric') {
            return leaves.filter(function (benchmark) {
                return benchmarkContainsToken(benchmark, preset.token);
            }).map(function (benchmark) { return benchmark.id; });
        }

        if (preset.kind === 'families') {
            return leaves.filter(function (benchmark) {
                var typeId = String(benchmark.type_id || benchmark.label || '').toLowerCase();
                return preset.prefixes.some(function (prefix) {
                    return typeId.indexOf(prefix) === 0;
                });
            }).map(function (benchmark) { return benchmark.id; });
        }

        return [];
    }

    function getCorrelationPresets(benchmarks) {
        return CORRELATION_PRESETS.map(function (preset) {
            return {
                id: preset.id,
                label: preset.label,
                description: preset.description,
                benchmarkIds: matchingPresetBenchmarkIds(preset.id, benchmarks)
            };
        }).filter(function (preset) { return preset.benchmarkIds.length >= 2; });
    }

    function createPresetModes(presetId, benchmarks, activeBenchmarkIds) {
        var hierarchy = buildHierarchy(benchmarks);
        var next = {};
        (benchmarks || []).forEach(function (benchmark) {
            next[benchmark.id] = DESELECT;
        });
        matchingPresetBenchmarkIds(presetId, benchmarks).forEach(function (benchmarkId) {
            if (!activeBenchmarkIds[benchmarkId]) return;
            next[benchmarkId] = SELECT;
            var parentId = hierarchy.parentById[benchmarkId];
            while (parentId) {
                if (!hierarchy.byId[parentId].is_engineering) next[parentId] = HIDE;
                parentId = hierarchy.parentById[parentId];
            }
        });
        return next;
    }

    function descendantsOf(benchmarkId, hierarchy) {
        var descendants = [];
        (hierarchy.childrenById[benchmarkId] || []).forEach(function (childId) {
            descendants.push(childId);
            descendants = descendants.concat(descendantsOf(childId, hierarchy));
        });
        return descendants;
    }

    function setBenchmarkMode(currentModes, benchmarkId, mode, hierarchy) {
        if ([SELECT, HIDE, DESELECT].indexOf(mode) < 0 || !hierarchy.byId[benchmarkId]) {
            return Object.assign({}, currentModes);
        }
        var next = Object.assign({}, currentModes);
        var descendants = descendantsOf(benchmarkId, hierarchy);
        if (mode === DESELECT) {
            next[benchmarkId] = DESELECT;
            descendants.forEach(function (childId) { next[childId] = DESELECT; });
            return next;
        }

        next[benchmarkId] = mode;
        var parentId = hierarchy.parentById[benchmarkId];
        while (parentId) {
            if (next[parentId] === DESELECT) next[parentId] = HIDE;
            parentId = hierarchy.parentById[parentId];
        }

        var hasIncludedDescendant = descendants.some(function (childId) {
            return next[childId] !== DESELECT;
        });
        if (descendants.length && !hasIncludedDescendant) {
            descendants.forEach(function (childId) { next[childId] = HIDE; });
        }
        return next;
    }

    function validMatrixScore(value) {
        if (value === null || value === undefined || value === '') return null;
        var number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function aggregateRows(rows, benchmarks, modes, activeBenchmarkIds) {
        var hierarchy = buildHierarchy(benchmarks);
        return (rows || []).map(function (row) {
            var memo = {};
            function valueFor(benchmarkId) {
                if (Object.prototype.hasOwnProperty.call(memo, benchmarkId)) return memo[benchmarkId];
                if (!activeBenchmarkIds[benchmarkId] || modes[benchmarkId] === DESELECT) {
                    memo[benchmarkId] = null;
                    return null;
                }
                var allChildren = hierarchy.childrenById[benchmarkId] || [];
                var children = allChildren.filter(function (childId) {
                    return activeBenchmarkIds[childId] && modes[childId] !== DESELECT;
                });
                if (!allChildren.length) {
                    var completenessKey = benchmarkId + '-is_complete';
                    if (Object.prototype.hasOwnProperty.call(row, completenessKey) &&
                        row[completenessKey] != 1) {
                        memo[benchmarkId] = null;
                        return null;
                    }
                    memo[benchmarkId] = validMatrixScore(row[benchmarkId + '-score']);
                    return memo[benchmarkId];
                }
                if (!children.length) {
                    memo[benchmarkId] = null;
                    return null;
                }
                var values = children.map(valueFor);
                var hasValidValue = values.some(function (value) { return value !== null; });
                memo[benchmarkId] = hasValidValue
                    ? values.reduce(function (sum, value) {
                        return sum + (value === null ? 0 : value);
                    }, 0) / children.length
                    : null;
                return memo[benchmarkId];
            }
            (benchmarks || []).forEach(function (benchmark) { valueFor(benchmark.id); });
            return {model_id: row.model_id, model: row.model, values: memo};
        });
    }

    function pearsonCorrelation(leftValues, rightValues, minimumOverlap) {
        var pairs = [];
        for (var index = 0; index < Math.min(leftValues.length, rightValues.length); index++) {
            var left = validMatrixScore(leftValues[index]);
            var right = validMatrixScore(rightValues[index]);
            if (left !== null && right !== null) pairs.push([left, right]);
        }
        var n = pairs.length;
        var minimum = Math.max(2, Number(minimumOverlap) || 8);
        if (n < minimum) return {r: null, n: n};
        var meanLeft = pairs.reduce(function (sum, pair) { return sum + pair[0]; }, 0) / n;
        var meanRight = pairs.reduce(function (sum, pair) { return sum + pair[1]; }, 0) / n;
        var numerator = 0;
        var leftSquares = 0;
        var rightSquares = 0;
        pairs.forEach(function (pair) {
            var leftDelta = pair[0] - meanLeft;
            var rightDelta = pair[1] - meanRight;
            numerator += leftDelta * rightDelta;
            leftSquares += leftDelta * leftDelta;
            rightSquares += rightDelta * rightDelta;
        });
        var denominator = Math.sqrt(leftSquares * rightSquares);
        if (!denominator) return {r: null, n: n};
        var correlation = Math.max(-1, Math.min(1, numerator / denominator));
        return {r: correlation, n: n};
    }

    function buildCorrelationMatrix(rows, benchmarks, modes, activeBenchmarkIds, minimumOverlap) {
        var axes = (benchmarks || []).filter(function (benchmark) {
            return modes[benchmark.id] === SELECT && activeBenchmarkIds[benchmark.id];
        });
        var aggregatedRows = aggregateRows(rows, benchmarks, modes, activeBenchmarkIds);
        var cells = axes.map(function (left) {
            return axes.map(function (right) {
                return pearsonCorrelation(
                    aggregatedRows.map(function (row) { return row.values[left.id]; }),
                    aggregatedRows.map(function (row) { return row.values[right.id]; }),
                    minimumOverlap
                );
            });
        });
        return {
            axes: axes,
            cells: cells,
            modelCount: aggregatedRows.length,
            minimumOverlap: Math.max(2, Number(minimumOverlap) || 8)
        };
    }

    function displayLabel(benchmark) {
        var labels = {
            average_vision: 'Vision',
            neural_vision: 'Neural',
            behavior_vision: 'Behavioral',
            engineering_vision: 'Engineering',
            average_language: 'Language',
            neural_language: 'Neural',
            behavior_language: 'Behavioral',
            engineering_language: 'Engineering'
        };
        return labels[benchmark.type_id] || benchmark.label || benchmark.type_id;
    }

    function matrixAxisTicks(labels, maximumTicks) {
        var limit = Math.max(2, Number(maximumTicks) || 12);
        if (labels.length <= limit) {
            return {
                tickvals: labels.map(function (_label, index) { return index; }),
                ticktext: labels.slice()
            };
        }
        var step = Math.ceil((labels.length - 1) / (limit - 1));
        var indexes = [];
        for (var index = 0; index < labels.length; index += step) indexes.push(index);
        if (indexes[indexes.length - 1] !== labels.length - 1) indexes.push(labels.length - 1);
        return {
            tickvals: indexes,
            ticktext: indexes.map(function (tickIndex) { return labels[tickIndex]; })
        };
    }

    function matrixAxisTicksForRange(labels, range, maximumTicks) {
        if (!Array.isArray(range) || range.length < 2 ||
            !Number.isFinite(Number(range[0])) || !Number.isFinite(Number(range[1]))) {
            return matrixAxisTicks(labels, maximumTicks);
        }
        var lower = Math.min(Number(range[0]), Number(range[1]));
        var upper = Math.max(Number(range[0]), Number(range[1]));
        var first = Math.max(0, Math.ceil(lower - 0.5));
        var last = Math.min(labels.length - 1, Math.floor(upper + 0.5));
        if (last < first) return matrixAxisTicks(labels, maximumTicks);
        var visibleLabels = labels.slice(first, last + 1);
        var visibleTicks = matrixAxisTicks(visibleLabels, maximumTicks);
        return {
            tickvals: visibleTicks.tickvals.map(function (tickValue) { return tickValue + first; }),
            ticktext: visibleTicks.ticktext
        };
    }

    function csvValue(value) {
        var text = value === null || value === undefined ? '' : String(value);
        return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }

    function matrixColorConfig(cells) {
        var values = [];
        (cells || []).forEach(function (row) {
            (row || []).forEach(function (result) {
                if (result && result.r !== null && Number.isFinite(result.r)) values.push(result.r);
            });
        });
        var hasNegative = values.some(function (value) { return value < 0; });
        if (hasNegative) {
            return {
                zmin: -1,
                zmax: 1,
                colorscale: [
                    [0, '#b2182b'],
                    [0.5, '#f7faf8'],
                    [1, '#078930']
                ]
            };
        }
        var minimum = values.length ? Math.min.apply(null, values) : 0;
        if (minimum >= 1) minimum = 0;
        return {
            zmin: minimum,
            zmax: 1,
            colorscale: [
                [0, '#f7faf8'],
                [1, '#078930']
            ]
        };
    }

    function hexColorToRgb(color) {
        var hex = String(color || '').replace('#', '');
        if (hex.length === 3) {
            hex = hex.split('').map(function (character) { return character + character; }).join('');
        }
        return {
            r: parseInt(hex.slice(0, 2), 16),
            g: parseInt(hex.slice(2, 4), 16),
            b: parseInt(hex.slice(4, 6), 16)
        };
    }

    function colorAtScale(position, colorscale) {
        var bounded = Math.max(0, Math.min(1, position));
        var lower = colorscale[0];
        var upper = colorscale[colorscale.length - 1];
        for (var index = 1; index < colorscale.length; index++) {
            if (bounded <= colorscale[index][0]) {
                lower = colorscale[index - 1];
                upper = colorscale[index];
                break;
            }
        }
        var span = upper[0] - lower[0];
        var fraction = span ? (bounded - lower[0]) / span : 0;
        var start = hexColorToRgb(lower[1]);
        var end = hexColorToRgb(upper[1]);
        return {
            r: start.r + (end.r - start.r) * fraction,
            g: start.g + (end.g - start.g) * fraction,
            b: start.b + (end.b - start.b) * fraction
        };
    }

    function relativeLuminance(color) {
        function linearChannel(channel) {
            var value = channel / 255;
            return value <= 0.04045
                ? value / 12.92
                : Math.pow((value + 0.055) / 1.055, 2.4);
        }
        return 0.2126 * linearChannel(color.r) +
            0.7152 * linearChannel(color.g) +
            0.0722 * linearChannel(color.b);
    }

    function contrastRatio(left, right) {
        var lighter = Math.max(relativeLuminance(left), relativeLuminance(right));
        var darker = Math.min(relativeLuminance(left), relativeLuminance(right));
        return (lighter + 0.05) / (darker + 0.05);
    }

    function matrixTextColor(value, colorConfig) {
        if (value === null || value === undefined || !Number.isFinite(value)) return '#000000';
        var position = (value - colorConfig.zmin) / (colorConfig.zmax - colorConfig.zmin);
        var background = colorAtScale(position, colorConfig.colorscale);
        var dark = {r: 0, g: 0, b: 0};
        var light = {r: 255, g: 255, b: 255};
        return contrastRatio(dark, background) >= contrastRatio(light, background)
            ? '#000000'
            : '#ffffff';
    }

    function matrixToCsv(matrix) {
        var rows = [[
            'row_benchmark',
            'column_benchmark',
            'pearson_r',
            'paired_models'
        ]];
        matrix.axes.forEach(function (left, rowIndex) {
            matrix.axes.forEach(function (right, columnIndex) {
                var result = matrix.cells[rowIndex][columnIndex];
                rows.push([
                    displayLabel(left),
                    displayLabel(right),
                    result.r === null ? '' : result.r,
                    result.n
                ]);
            });
        });
        return rows.map(function (row) { return row.map(csvValue).join(','); }).join('\n');
    }

    function paddedScatterRange(values) {
        var minimum = Math.min.apply(null, values);
        var maximum = Math.max.apply(null, values);
        var span = maximum - minimum;
        var padding = span ? span * 0.05 : Math.max(Math.abs(maximum) * 0.05, 0.05);
        return [minimum - padding, maximum + padding];
    }

    function buildPlotlyBenchmarkScatter(points, options) {
        options = options || {};
        var xValues = points.map(function (point) { return point.x; });
        var yValues = points.map(function (point) { return point.y; });
        var xRange = paddedScatterRange(xValues);
        var yRange = paddedScatterRange(yValues);
        var regression = options.regression || {slope: 0, intercept: 0};
        var regressionX = [xRange[0], xRange[1]];
        var regressionY = regressionX.map(function (value) {
            return regression.slope * value + regression.intercept;
        });
        var images = options.logoSource ? [{
            source: options.logoSource,
            xref: 'paper',
            yref: 'paper',
            x: 0.985,
            y: 0.025,
            sizex: 0.16,
            sizey: 0.055,
            xanchor: 'right',
            yanchor: 'bottom',
            sizing: 'contain',
            opacity: 0.82,
            layer: 'above'
        }] : [];

        return {
            data: [
                {
                    x: regressionX,
                    y: regressionY,
                    type: 'scatter',
                    mode: 'lines',
                    line: {color: '#c8ceca', width: 2, dash: 'dot'},
                    hoverinfo: 'skip',
                    showlegend: false
                },
                {
                    x: xValues,
                    y: yValues,
                    customdata: points.map(function (point) { return point.model; }),
                    type: 'scatter',
                    mode: 'markers',
                    marker: {
                        color: '#078930',
                        opacity: 0.48,
                        size: 11,
                        line: {color: 'rgba(7, 137, 48, 0.22)', width: 1}
                    },
                    hovertemplate: '<b>%{customdata}</b>' +
                        '<br>' + options.xLabel + ': %{x:.4f}' +
                        '<br>' + options.yLabel + ': %{y:.4f}<extra></extra>',
                    showlegend: false
                }
            ],
            layout: {
                title: {
                    text: options.statsText || '',
                    x: 0.5,
                    xanchor: 'center',
                    font: {size: 13, color: '#26342d'}
                },
                autosize: true,
                height: options.height || 560,
                margin: {l: 75, r: 35, t: 58, b: 70, pad: 2},
                paper_bgcolor: '#ffffff',
                plot_bgcolor: '#ffffff',
                font: {family: "'Open Sans', Arial, sans-serif", color: '#26342d'},
                hovermode: 'closest',
                dragmode: 'zoom',
                showlegend: false,
                images: images,
                xaxis: {
                    title: {text: options.xLabel},
                    range: xRange,
                    automargin: true,
                    gridcolor: '#edf1ee',
                    zeroline: false
                },
                yaxis: {
                    title: {text: options.yLabel},
                    range: yRange,
                    automargin: true,
                    gridcolor: '#edf1ee',
                    zeroline: false
                }
            },
            config: {
                responsive: true,
                scrollZoom: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['select2d', 'lasso2d'],
                toImageButtonOptions: {
                    format: 'png',
                    filename: 'brain-score-benchmark-scatter',
                    scale: 2
                }
            }
        };
    }

    function buildPlotlyMatrix(matrix, logoSource, maximumTicks, expanded) {
        expanded = !!expanded;
        var labels = matrix.axes.map(displayLabel);
        var indexes = labels.map(function (_label, index) { return index; });
        var ticks = matrixAxisTicks(labels, maximumTicks);
        var colorConfig = matrixColorConfig(matrix.cells);
        var customdata = matrix.cells.map(function (row, rowIndex) {
            return row.map(function (result, columnIndex) {
                return [
                    labels[rowIndex],
                    labels[columnIndex],
                    result.r === null ? 'Unavailable' : result.r.toFixed(3),
                    result.n
                ];
            });
        });
        var traces = [{
            type: 'heatmap',
            x: indexes,
            y: indexes,
            z: matrix.cells.map(function (row) {
                return row.map(function (result) { return result.r; });
            }),
            customdata: customdata,
            zmin: colorConfig.zmin,
            zmax: colorConfig.zmax,
            colorscale: colorConfig.colorscale,
            xgap: labels.length <= 20 ? 2 : 0,
            ygap: labels.length <= 20 ? 2 : 0,
            hoverongaps: true,
            hovertemplate: '<b>%{customdata[0]}</b> \u00d7 <b>%{customdata[1]}</b>' +
                '<br>Pearson r = %{customdata[2]}' +
                '<br>Paired models n = %{customdata[3]}<extra></extra>',
            colorbar: {
                title: {text: 'Pearson r', side: 'right'},
                thickness: 14,
                len: 0.72,
                x: 1.02,
                y: 0.55
            }
        }];

        if (labels.length <= 12) {
            var textGroups = {
                dark: {x: [], y: [], text: [], color: '#000000'},
                light: {x: [], y: [], text: [], color: '#ffffff'}
            };
            matrix.cells.forEach(function (row, rowIndex) {
                row.forEach(function (result, columnIndex) {
                    var group = matrixTextColor(result.r, colorConfig) === '#ffffff'
                        ? textGroups.light
                        : textGroups.dark;
                    group.x.push(columnIndex);
                    group.y.push(rowIndex);
                    group.text.push(
                        (result.r === null ? '\u2014' : result.r.toFixed(2)) + '<br>n=' + result.n
                    );
                });
            });
            [textGroups.dark, textGroups.light].forEach(function (group) {
                if (!group.text.length) return;
                traces.push({
                    type: 'scatter',
                    mode: 'text',
                    x: group.x,
                    y: group.y,
                    text: group.text,
                    textfont: {color: group.color, size: 10},
                    hoverinfo: 'skip',
                    showlegend: false
                });
            });
        }

        var images = logoSource ? [{
            source: logoSource,
            xref: 'paper',
            yref: 'paper',
            x: expanded ? 0.98 : 1.02,
            y: 0.02,
            sizex: 0.16,
            sizey: 0.045,
            xanchor: expanded ? 'right' : 'left',
            yanchor: 'bottom',
            sizing: 'contain',
            opacity: 0.82,
            layer: 'above'
        }] : [];

        return {
            data: traces,
            layout: {
                title: {
                    text: 'Brain-Score benchmark correlation matrix',
                    x: 0,
                    xanchor: 'left',
                    font: {size: 14, color: '#26342d'}
                },
                autosize: true,
                margin: {l: 90, r: expanded ? 105 : 150, t: 58, b: 100, pad: 2},
                paper_bgcolor: '#ffffff',
                plot_bgcolor: '#f7faf8',
                font: {family: 'Open Sans, Arial, sans-serif', size: 10, color: '#26342d'},
                hovermode: 'closest',
                dragmode: 'pan',
                showlegend: false,
                images: images,
                xaxis: {
                    tickmode: 'array',
                    tickvals: ticks.tickvals,
                    ticktext: ticks.ticktext,
                    tickangle: -45,
                    automargin: true,
                    constrain: 'domain',
                    zeroline: false
                },
                yaxis: {
                    tickmode: 'array',
                    tickvals: ticks.tickvals,
                    ticktext: ticks.ticktext,
                    automargin: true,
                    autorange: 'reversed',
                    constrain: 'domain',
                    scaleanchor: 'x',
                    scaleratio: 1,
                    zeroline: false
                }
            },
            config: {
                responsive: true,
                scrollZoom: true,
                displayModeBar: true,
                displaylogo: false,
                modeBarButtonsToRemove: ['select2d', 'lasso2d'],
                toImageButtonOptions: {
                    format: 'png',
                    filename: 'brain-score-benchmark-correlation-matrix',
                    scale: 2
                }
            }
        };
    }

    function createElement(document, tagName, className, text) {
        var element = document.createElement(tagName);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function createExplorer(payload, dashboard, document) {
        var benchmarks = payload.benchmarks || [];
        var hierarchy = buildHierarchy(benchmarks);
        var modes = createDefaultModes(benchmarks);
        var collapsed = {};
        var resolved = dashboard.getResolved();
        var treeContainer = document.getElementById('benchmark-correlation-tree');
        var matrixContainer = document.getElementById('benchmark-correlation-matrix');
        var explorer = document.getElementById('benchmark-correlation-explorer');
        var summary = document.getElementById('benchmark-correlation-summary');
        var expand = document.getElementById('benchmark-correlation-expand');
        var selectAll = document.getElementById('benchmark-correlation-select-all');
        var reset = document.getElementById('benchmark-correlation-reset');
        var presetSelect = document.getElementById('benchmark-correlation-preset-select');
        var downloadSvg = document.getElementById('benchmark-correlation-download-svg');
        var downloadCsv = document.getElementById('benchmark-correlation-download-csv');
        var browserRoot = document.defaultView || {};
        var plotly = browserRoot.Plotly;
        var latestMatrix = null;
        var relayoutHandler = null;
        var updatingTicks = false;
        var activePresetId = null;
        var availablePresets = getCorrelationPresets(benchmarks);

        benchmarks.forEach(function (benchmark) {
            var depth = 0;
            var parentId = hierarchy.parentById[benchmark.id];
            while (parentId) {
                depth += 1;
                parentId = hierarchy.parentById[parentId];
            }
            collapsed[benchmark.id] = depth >= 2 || benchmark.is_engineering ||
                benchmark.type_id.indexOf('behavior_') === 0;
        });

        function renderNode(benchmarkId) {
            var benchmark = hierarchy.byId[benchmarkId];
            var children = hierarchy.childrenById[benchmarkId] || [];
            var node = createElement(document, 'li', 'benchmark-correlation-node');
            if (!resolved.activeBenchmarkIds[benchmarkId]) node.classList.add('is-unavailable');

            var row = createElement(document, 'div', 'benchmark-correlation-node-row');
            if (children.length) {
                var toggle = createElement(
                    document,
                    'button',
                    'benchmark-correlation-toggle',
                    collapsed[benchmarkId] ? '\u25b6' : '\u25bc'
                );
                toggle.type = 'button';
                toggle.setAttribute('aria-label', (collapsed[benchmarkId] ? 'Expand ' : 'Collapse ') + displayLabel(benchmark));
                toggle.addEventListener('click', function () {
                    collapsed[benchmarkId] = !collapsed[benchmarkId];
                    renderTree();
                });
                row.appendChild(toggle);
            } else {
                row.appendChild(createElement(document, 'span', 'benchmark-correlation-toggle-spacer'));
            }

            var label = createElement(document, 'span', 'benchmark-correlation-node-label', displayLabel(benchmark));
            if (!resolved.activeBenchmarkIds[benchmarkId]) label.title = 'Unavailable at the selected wayback date';
            row.appendChild(label);

            var controls = createElement(document, 'span', 'benchmark-correlation-state-controls');
            [SELECT, HIDE, DESELECT].forEach(function (mode) {
                var button = createElement(
                    document,
                    'button',
                    'benchmark-correlation-state is-' + mode,
                    mode.charAt(0).toUpperCase() + mode.slice(1)
                );
                button.type = 'button';
                button.disabled = !resolved.activeBenchmarkIds[benchmarkId];
                button.setAttribute('aria-pressed', modes[benchmarkId] === mode ? 'true' : 'false');
                if (modes[benchmarkId] === mode) button.classList.add('is-active');
                button.addEventListener('click', function () {
                    activePresetId = null;
                    modes = setBenchmarkMode(modes, benchmarkId, mode, hierarchy);
                    render();
                });
                controls.appendChild(button);
            });
            row.appendChild(controls);
            node.appendChild(row);

            if (children.length && !collapsed[benchmarkId]) {
                var childList = createElement(document, 'ul', 'benchmark-correlation-tree-list');
                children.forEach(function (childId) { childList.appendChild(renderNode(childId)); });
                node.appendChild(childList);
            }
            return node;
        }

        function renderTree() {
            if (!treeContainer) return;
            treeContainer.innerHTML = '';
            var rootList = createElement(document, 'ul', 'benchmark-correlation-tree-list is-root');
            hierarchy.roots.forEach(function (rootId) { rootList.appendChild(renderNode(rootId)); });
            treeContainer.appendChild(rootList);
        }

        function renderPresets() {
            if (!presetSelect) return;
            presetSelect.innerHTML = '';
            var placeholder = createElement(document, 'option', '', 'Choose a preset');
            placeholder.value = '';
            presetSelect.appendChild(placeholder);
            availablePresets.forEach(function (preset) {
                var activeCount = preset.benchmarkIds.filter(function (benchmarkId) {
                    return resolved.activeBenchmarkIds[benchmarkId];
                }).length;
                var option = createElement(
                    document, 'option', '', preset.label + ' (' + activeCount + ')'
                );
                option.value = preset.id;
                option.disabled = activeCount < 2;
                option.title = preset.description;
                presetSelect.appendChild(option);
            });
            presetSelect.value = activePresetId || '';
            presetSelect.disabled = !availablePresets.length;
        }

        function renderMatrix() {
            if (!matrixContainer) return;
            if (relayoutHandler && matrixContainer.removeListener) {
                matrixContainer.removeListener('plotly_relayout', relayoutHandler);
            }
            relayoutHandler = null;
            if (plotly && matrixContainer.data) plotly.purge(matrixContainer);
            matrixContainer.innerHTML = '';
            var matrix = buildCorrelationMatrix(
                resolved.rows,
                benchmarks,
                modes,
                resolved.activeBenchmarkIds,
                8
            );
            latestMatrix = matrix;
            if (downloadSvg) downloadSvg.disabled = matrix.axes.length < 2 || !plotly;
            if (downloadCsv) downloadCsv.disabled = matrix.axes.length < 2;
            if (summary) {
                summary.textContent = matrix.axes.length + ' selected benchmarks \u00b7 ' +
                    matrix.modelCount + ' eligible cohort models \u00b7 hover for paired n ' +
                    '(minimum ' + matrix.minimumOverlap + ')';
            }
            if (matrix.axes.length < 2) {
                matrixContainer.appendChild(createElement(
                    document,
                    'div',
                    'notification is-light',
                    'Select at least two active benchmarks to build the correlation matrix.'
                ));
                return;
            }
            if (!plotly) {
                matrixContainer.appendChild(createElement(
                    document,
                    'div',
                    'notification is-warning is-light',
                    'The correlation matrix requires Plotly. Reload the page to try again.'
                ));
                return;
            }

            var isExpanded = explorer && explorer.classList.contains('is-expanded');
            var maximumTicks = isExpanded ? 48 : 24;
            var plot = buildPlotlyMatrix(
                matrix,
                browserRoot.logo_url || '/static/benchmarks/img/logo.png',
                maximumTicks,
                isExpanded
            );
            matrixContainer.setAttribute(
                'aria-label',
                matrix.axes.length + ' by ' + matrix.axes.length + ' benchmark correlation heatmap'
            );
            Promise.resolve(plotly.react(matrixContainer, plot.data, plot.layout, plot.config))
                .then(function () {
                    if (latestMatrix !== matrix || !matrixContainer.on) return;
                    var labels = matrix.axes.map(displayLabel);
                    relayoutHandler = function (eventData) {
                        if (updatingTicks || latestMatrix !== matrix || !matrixContainer._fullLayout) return;
                        var changedKeys = Object.keys(eventData || {});
                        var rangeChanged = changedKeys.some(function (key) {
                            return key.indexOf('xaxis.range') === 0 ||
                                key.indexOf('yaxis.range') === 0 ||
                                key === 'xaxis.autorange' || key === 'yaxis.autorange';
                        });
                        if (!rangeChanged) return;
                        var xaxis = matrixContainer._fullLayout.xaxis;
                        var yaxis = matrixContainer._fullLayout.yaxis;
                        var xTicks = matrixAxisTicksForRange(labels, xaxis.range, maximumTicks);
                        var yTicks = matrixAxisTicksForRange(labels, yaxis.range, maximumTicks);
                        updatingTicks = true;
                        Promise.resolve(plotly.relayout(matrixContainer, {
                            'xaxis.tickvals': xTicks.tickvals,
                            'xaxis.ticktext': xTicks.ticktext,
                            'yaxis.tickvals': yTicks.tickvals,
                            'yaxis.ticktext': yTicks.ticktext
                        })).then(function () {
                            updatingTicks = false;
                        }, function () {
                            updatingTicks = false;
                        });
                    };
                    matrixContainer.on('plotly_relayout', relayoutHandler);
                });
        }

        function render() {
            renderPresets();
            renderTree();
            renderMatrix();
        }

        if (selectAll) selectAll.addEventListener('click', function () {
            activePresetId = null;
            modes = selectAllBenchmarks(modes, benchmarks, resolved.activeBenchmarkIds);
            render();
        });
        if (presetSelect) presetSelect.addEventListener('change', function () {
            activePresetId = presetSelect.value || null;
            if (!activePresetId) return;
            modes = createPresetModes(
                activePresetId, benchmarks, resolved.activeBenchmarkIds
            );
            render();
        });
        if (downloadSvg) downloadSvg.addEventListener('click', function () {
            if (!plotly || !matrixContainer || !latestMatrix || latestMatrix.axes.length < 2) return;
            plotly.downloadImage(matrixContainer, {
                format: 'svg',
                filename: 'brain-score-benchmark-correlation-matrix'
            });
        });
        if (downloadCsv) downloadCsv.addEventListener('click', function () {
            if (!latestMatrix || latestMatrix.axes.length < 2 || !browserRoot.Blob || !browserRoot.URL) return;
            var blob = new browserRoot.Blob([matrixToCsv(latestMatrix)], {type: 'text/csv;charset=utf-8;'});
            var url = browserRoot.URL.createObjectURL(blob);
            var link = document.createElement('a');
            link.href = url;
            link.download = 'brain-score-benchmark-correlation-matrix.csv';
            document.body.appendChild(link);
            link.click();
            link.remove();
            browserRoot.setTimeout(function () { browserRoot.URL.revokeObjectURL(url); }, 0);
        });
        function setExpanded(isExpanded) {
            if (!explorer || !expand) return;
            explorer.classList.toggle('is-expanded', isExpanded);
            document.body.classList.toggle('benchmark-correlation-expanded', isExpanded);
            var expandAction = isExpanded ? 'Collapse' : 'Expand';
            var expandIcon = expand.querySelector('i');
            if (expandIcon) {
                expandIcon.className = isExpanded
                    ? 'fa-solid fa-down-left-and-up-right-to-center'
                    : 'fa-solid fa-up-right-and-down-left-from-center';
            }
            expand.setAttribute('aria-pressed', isExpanded ? 'true' : 'false');
            expand.setAttribute('aria-label', expandAction);
            expand.title = expandAction;
            renderMatrix();
        }
        if (expand) expand.addEventListener('click', function () {
            setExpanded(!explorer.classList.contains('is-expanded'));
        });
        document.addEventListener('keydown', function (event) {
            if (event.key === 'Escape' && explorer && explorer.classList.contains('is-expanded')) {
                setExpanded(false);
            }
        });
        if (reset) reset.addEventListener('click', function () {
            activePresetId = null;
            modes = createDefaultModes(benchmarks);
            render();
        });
        dashboard.subscribe(function (nextResolved) {
            resolved = nextResolved;
            if (activePresetId) {
                modes = createPresetModes(
                    activePresetId, benchmarks, resolved.activeBenchmarkIds
                );
            }
            render();
        });

        return {
            getModes: function () { return Object.assign({}, modes); },
            setExpanded: setExpanded,
            selectAll: function () {
                activePresetId = null;
                modes = selectAllBenchmarks(modes, benchmarks, resolved.activeBenchmarkIds);
                render();
            },
            reset: function () {
                activePresetId = null;
                modes = createDefaultModes(benchmarks);
                render();
            },
            applyPreset: function (presetId) {
                activePresetId = presetId;
                modes = createPresetModes(presetId, benchmarks, resolved.activeBenchmarkIds);
                render();
            },
            setMode: function (benchmarkId, mode) {
                activePresetId = null;
                modes = setBenchmarkMode(modes, benchmarkId, mode, hierarchy);
                render();
            }
        };
    }

    return {
        SELECT: SELECT,
        HIDE: HIDE,
        DESELECT: DESELECT,
        aggregateRows: aggregateRows,
        buildPlotlyBenchmarkScatter: buildPlotlyBenchmarkScatter,
        buildCorrelationMatrix: buildCorrelationMatrix,
        buildHierarchy: buildHierarchy,
        buildPlotlyMatrix: buildPlotlyMatrix,
        createDefaultModes: createDefaultModes,
        createPresetModes: createPresetModes,
        createExplorer: createExplorer,
        descendantsOf: descendantsOf,
        displayLabel: displayLabel,
        getCorrelationPresets: getCorrelationPresets,
        matchingPresetBenchmarkIds: matchingPresetBenchmarkIds,
        matrixColorConfig: matrixColorConfig,
        matrixTextColor: matrixTextColor,
        matrixAxisTicks: matrixAxisTicks,
        matrixAxisTicksForRange: matrixAxisTicksForRange,
        matrixToCsv: matrixToCsv,
        paddedScatterRange: paddedScatterRange,
        pearsonCorrelation: pearsonCorrelation,
        selectAllBenchmarks: selectAllBenchmarks,
        setBenchmarkMode: setBenchmarkMode,
        validMatrixScore: validMatrixScore
    };
}));
