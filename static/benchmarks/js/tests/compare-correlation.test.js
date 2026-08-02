const test = require('node:test');
const assert = require('node:assert/strict');

const correlation = require('../compare-correlation.js');

function benchmarks() {
    return [
        {id: 'average_vision_v0', type_id: 'average_vision', label: 'average_vision', parent_id: null, is_leaf: false, is_engineering: false},
        {id: 'neural_vision_v0', type_id: 'neural_vision', label: 'neural_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'V1_v0', type_id: 'V1', label: 'V1', parent_id: 'neural_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'v1-a_v0', type_id: 'v1-a', label: 'V1 A', parent_id: 'V1_v0', is_leaf: true, is_engineering: false},
        {id: 'v1-b_v0', type_id: 'v1-b', label: 'V1 B', parent_id: 'V1_v0', is_leaf: true, is_engineering: false},
        {id: 'V2_v0', type_id: 'V2', label: 'V2', parent_id: 'neural_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'v2-a_v0', type_id: 'v2-a', label: 'V2 A', parent_id: 'V2_v0', is_leaf: true, is_engineering: false},
        {id: 'V4_v0', type_id: 'V4', label: 'V4', parent_id: 'neural_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'v4-a_v0', type_id: 'v4-a', label: 'V4 A', parent_id: 'V4_v0', is_leaf: true, is_engineering: false},
        {id: 'IT_v0', type_id: 'IT', label: 'IT', parent_id: 'neural_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'it-a_v0', type_id: 'it-a', label: 'IT A', parent_id: 'IT_v0', is_leaf: true, is_engineering: false},
        {id: 'behavior_vision_v0', type_id: 'behavior_vision', label: 'behavior_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'behavior-a_v0', type_id: 'behavior-a', label: 'Behavior A', parent_id: 'behavior_vision_v0', is_leaf: true, is_engineering: false},
        {id: 'engineering_vision_v0', type_id: 'engineering_vision', label: 'engineering_vision', parent_id: null, is_leaf: false, is_engineering: true},
        {id: 'engineering-a_v0', type_id: 'engineering-a', label: 'Engineering A', parent_id: 'engineering_vision_v0', is_leaf: true, is_engineering: true}
    ];
}

function activeBenchmarks(items) {
    return Object.fromEntries(items.map(benchmark => [benchmark.id, true]));
}

function rows() {
    return Array.from({length: 10}, (_unused, index) => {
        const step = index + 1;
        return {
            model_id: step,
            model: `model-${step}`,
            'v1-a_v0-score': step / 10,
            'v1-b_v0-score': (step + 2) / 12,
            'v2-a_v0-score': (11 - step) / 10,
            'v4-a_v0-score': (step * 2 + 1) / 22,
            'it-a_v0-score': (step * 3 + 2) / 32,
            'behavior-a_v0-score': (step + 1) / 11,
            'engineering-a_v0-score': step / 10
        };
    });
}

test('defaults to neural, region, and behavioral axes and deselects engineering', () => {
    const items = benchmarks();
    const modes = correlation.createDefaultModes(items);
    const matrix = correlation.buildCorrelationMatrix(
        rows(), items, modes, activeBenchmarks(items), 8
    );

    assert.deepEqual(matrix.axes.map(benchmark => benchmark.type_id), [
        'neural_vision', 'V1', 'V2', 'V4', 'IT', 'behavior_vision'
    ]);
    assert.equal(modes['v1-a_v0'], correlation.HIDE);
    assert.equal(modes['engineering_vision_v0'], correlation.DESELECT);
    assert.equal(modes['engineering-a_v0'], correlation.DESELECT);
});

test('select all includes active non-engineering benchmarks only', () => {
    const items = benchmarks();
    const active = activeBenchmarks(items);
    active['v1-b_v0'] = false;
    const initial = correlation.createDefaultModes(items);
    const modes = correlation.selectAllBenchmarks(initial, items, active);

    items.filter(benchmark => !benchmark.is_engineering && active[benchmark.id])
        .forEach(benchmark => assert.equal(modes[benchmark.id], correlation.SELECT));
    assert.equal(modes['v1-b_v0'], correlation.HIDE);
    assert.equal(modes['engineering_vision_v0'], correlation.DESELECT);
    assert.equal(modes['engineering-a_v0'], correlation.DESELECT);
});

test('deselect cascades and selecting a child restores deselected ancestors', () => {
    const items = benchmarks();
    const hierarchy = correlation.buildHierarchy(items);
    let modes = correlation.createDefaultModes(items);

    modes = correlation.setBenchmarkMode(modes, 'V1_v0', correlation.DESELECT, hierarchy);
    assert.equal(modes['V1_v0'], correlation.DESELECT);
    assert.equal(modes['v1-a_v0'], correlation.DESELECT);
    assert.equal(modes['v1-b_v0'], correlation.DESELECT);

    modes = correlation.setBenchmarkMode(modes, 'v1-a_v0', correlation.SELECT, hierarchy);
    assert.equal(modes['v1-a_v0'], correlation.SELECT);
    assert.equal(modes['V1_v0'], correlation.HIDE);
    assert.equal(modes['neural_vision_v0'], correlation.SELECT);
    assert.equal(modes['v1-b_v0'], correlation.DESELECT);
});

test('restoring a deselected parent hides its descendants for aggregation', () => {
    const items = benchmarks();
    const hierarchy = correlation.buildHierarchy(items);
    let modes = correlation.createDefaultModes(items);
    modes = correlation.setBenchmarkMode(modes, 'V2_v0', correlation.DESELECT, hierarchy);
    modes = correlation.setBenchmarkMode(modes, 'V2_v0', correlation.SELECT, hierarchy);

    assert.equal(modes['V2_v0'], correlation.SELECT);
    assert.equal(modes['v2-a_v0'], correlation.HIDE);
});

test('hidden children contribute to parents while deselected children do not', () => {
    const items = benchmarks();
    const active = activeBenchmarks(items);
    const hierarchy = correlation.buildHierarchy(items);
    const sourceRows = rows();
    let modes = correlation.createDefaultModes(items);
    let aggregated = correlation.aggregateRows(sourceRows, items, modes, active);
    const expectedAverage = (sourceRows[0]['v1-a_v0-score'] + sourceRows[0]['v1-b_v0-score']) / 2;
    assert.equal(aggregated[0].values.V1_v0, expectedAverage);

    modes = correlation.setBenchmarkMode(modes, 'v1-b_v0', correlation.DESELECT, hierarchy);
    aggregated = correlation.aggregateRows(sourceRows, items, modes, active);
    assert.equal(aggregated[0].values.V1_v0, sourceRows[0]['v1-a_v0-score']);

    modes = correlation.setBenchmarkMode(modes, 'v1-a_v0', correlation.DESELECT, hierarchy);
    aggregated = correlation.aggregateRows(sourceRows, items, modes, active);
    assert.equal(aggregated[0].values.V1_v0, null);
});

test('retains missing included children in the parent denominator', () => {
    const items = benchmarks();
    const active = activeBenchmarks(items);
    const hierarchy = correlation.buildHierarchy(items);
    const sourceRows = rows();
    sourceRows[0]['v1-b_v0-score'] = '';
    sourceRows[0]['v1-b_v0-is_complete'] = 0;
    sourceRows[0]['v1-a_v0-is_complete'] = 1;
    let modes = correlation.createDefaultModes(items);
    let aggregated = correlation.aggregateRows(sourceRows, items, modes, active);
    assert.equal(aggregated[0].values.V1_v0, sourceRows[0]['v1-a_v0-score'] / 2);

    modes = correlation.setBenchmarkMode(modes, 'v1-b_v0', correlation.DESELECT, hierarchy);
    aggregated = correlation.aggregateRows(sourceRows, items, modes, active);
    assert.equal(aggregated[0].values.V1_v0, sourceRows[0]['v1-a_v0-score']);
});

test('uses finite pairwise scores including zero and enforces minimum overlap', () => {
    const left = [1, 2, 3, 4, 5, 6, 7, 8, 0, Number.NaN];
    const right = [2, 4, 6, 8, 10, 12, 14, 16, 0, 100];
    const supported = correlation.pearsonCorrelation(left, right, 9);
    const unsupported = correlation.pearsonCorrelation(left, right, 10);

    assert.equal(supported.n, 9);
    assert.equal(supported.r, 1);
    assert.deepEqual(unsupported, {r: null, n: 9});
});

test('starts a positive-only Plotly color scale at the lowest correlation', () => {
    const matrix = {
        axes: benchmarks().slice(0, 2),
        cells: [
            [{r: 1, n: 10}, {r: 0.25, n: 9}],
            [{r: 0.25, n: 9}, {r: 1, n: 10}]
        ],
        modelCount: 10,
        minimumOverlap: 8
    };
    const plot = correlation.buildPlotlyMatrix(matrix, '/static/logo.png', 12);

    assert.equal(plot.data[0].type, 'heatmap');
    assert.equal(plot.data[0].zmin, 0.25);
    assert.equal(plot.data[0].zmax, 1);
    assert.deepEqual(plot.data[0].colorscale, [
        [0, '#f7faf8'],
        [1, '#078930']
    ]);
    assert.equal(plot.layout.images[0].source, '/static/logo.png');
    assert.equal(plot.layout.images[0].x, 1.04);
    assert.ok(plot.layout.images[0].y < 0.1);
    assert.equal(plot.config.displayModeBar, true);
    assert.equal(
        plot.config.toImageButtonOptions.filename,
        'brain-score-benchmark-correlation-matrix'
    );
    assert.equal('width' in plot.config.toImageButtonOptions, false);
    assert.equal('height' in plot.config.toImageButtonOptions, false);
});

test('uses the full Pearson color range when the matrix contains negatives', () => {
    const matrix = {
        axes: benchmarks().slice(0, 2),
        cells: [
            [{r: 1, n: 10}, {r: -0.4, n: 9}],
            [{r: -0.4, n: 9}, {r: 1, n: 10}]
        ],
        modelCount: 10,
        minimumOverlap: 8
    };
    const plot = correlation.buildPlotlyMatrix(matrix, '/static/logo.png', 12);

    assert.equal(plot.data[0].zmin, -1);
    assert.equal(plot.data[0].zmax, 1);
    assert.deepEqual(plot.data[0].colorscale, [
        [0, '#b2182b'],
        [0.5, '#f7faf8'],
        [1, '#078930']
    ]);
});

test('chooses readable matrix text for the interpolated cell color', () => {
    const positiveConfig = correlation.matrixColorConfig([
        [{r: 0.25}, {r: 0.6}, {r: 1}]
    ]);
    const divergingConfig = correlation.matrixColorConfig([
        [{r: -1}, {r: 0}, {r: 1}]
    ]);

    assert.equal(correlation.matrixTextColor(0.25, positiveConfig), '#000000');
    assert.equal(correlation.matrixTextColor(0.6, positiveConfig), '#000000');
    assert.equal(correlation.matrixTextColor(1, positiveConfig), '#000000');
    assert.equal(correlation.matrixTextColor(-1, divergingConfig), '#ffffff');
    assert.equal(correlation.matrixTextColor(0, divergingConfig), '#000000');
    assert.equal(correlation.matrixTextColor(1, divergingConfig), '#000000');
});

test('limits dense Plotly axes while retaining the first and last labels', () => {
    const labels = Array.from({length: 139}, (_unused, index) => `Benchmark ${index + 1}`);
    const ticks = correlation.matrixAxisTicks(labels, 12);

    assert.ok(ticks.tickvals.length <= 12);
    assert.equal(ticks.tickvals[0], 0);
    assert.equal(ticks.tickvals.at(-1), 138);
});

test('shows every visible label after zooming into a small matrix range', () => {
    const labels = Array.from({length: 139}, (_unused, index) => `Benchmark ${index + 1}`);
    const forward = correlation.matrixAxisTicksForRange(labels, [40.2, 49.8], 24);
    const reversed = correlation.matrixAxisTicksForRange(labels, [49.8, 40.2], 24);

    assert.deepEqual(forward.tickvals, Array.from({length: 11}, (_unused, index) => index + 40));
    assert.deepEqual(reversed, forward);
    assert.equal(forward.ticktext[0], 'Benchmark 41');
    assert.equal(forward.ticktext.at(-1), 'Benchmark 51');
});

test('exports correlation values and paired counts as CSV', () => {
    const items = benchmarks().slice(0, 2);
    items[1] = {...items[1], label: 'Neural, aggregate'};
    const csv = correlation.matrixToCsv({
        axes: items,
        cells: [
            [{r: 1, n: 10}, {r: null, n: 7}],
            [{r: null, n: 7}, {r: 1, n: 9}]
        ]
    });
    const lines = csv.split('\n');

    assert.equal(lines.length, 5);
    assert.equal(lines[0], 'row_benchmark,column_benchmark,pearson_r,paired_models');
    assert.equal(csv.includes('_id'), false);
    assert.ok(csv.includes('Neural'));
    assert.ok(csv.includes(',,7'));
});

test('matches dashboard parent scores and paired correlation', () => {
    const items = benchmarks();
    const sourceRows = Array.from({length: 8}, (_unused, index) => {
        const first = (index + 1) / 10;
        const second = index % 2 ? '' : (index + 2) / 12;
        const v1 = (first + (second === '' ? 0 : second)) / 2;
        const v2 = Math.pow(index + 1, 2) / 100;
        return {
            model_id: index + 1,
            model: `model-${index + 1}`,
            'v1-a_v0-score': first,
            'v1-a_v0-is_complete': 1,
            'v1-b_v0-score': second,
            'v1-b_v0-is_complete': second === '' ? 0 : 1,
            'V1_v0-score': v1,
            'V1_v0-is_complete': 1,
            'v2-a_v0-score': v2,
            'v2-a_v0-is_complete': 1,
            'V2_v0-score': v2,
            'V2_v0-is_complete': 1
        };
    });
    const modes = correlation.createDefaultModes(items);
    const expected = correlation.pearsonCorrelation(
        sourceRows.map(row => row['V1_v0-score']),
        sourceRows.map(row => row['V2_v0-score']),
        8
    );
    const matrix = correlation.buildCorrelationMatrix(
        sourceRows, items, modes, activeBenchmarks(items), 8
    );
    const v1Index = matrix.axes.findIndex(benchmark => benchmark.id === 'V1_v0');
    const v2Index = matrix.axes.findIndex(benchmark => benchmark.id === 'V2_v0');

    assert.deepEqual(matrix.cells[v1Index][v2Index], expected);
});

test('deselecting behavior retains neural and its four selected regions', () => {
    const items = benchmarks();
    const hierarchy = correlation.buildHierarchy(items);
    let modes = correlation.createDefaultModes(items);
    modes = correlation.setBenchmarkMode(
        modes, 'behavior_vision_v0', correlation.DESELECT, hierarchy
    );
    const matrix = correlation.buildCorrelationMatrix(
        rows(), items, modes, activeBenchmarks(items), 8
    );

    assert.deepEqual(matrix.axes.map(benchmark => benchmark.type_id), [
        'neural_vision', 'V1', 'V2', 'V4', 'IT'
    ]);
    assert.equal(matrix.cells.length, 5);
    assert.ok(matrix.cells.every(matrixRow => matrixRow.length === 5));
});
