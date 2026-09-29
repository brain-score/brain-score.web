const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const stability = require('../compare-stability.js');
const correlation = require('../compare-correlation.js');

test('builds historical snapshots and preserves the latest date', () => {
    assert.deepEqual(
        stability.stabilitySnapshotDates('2020-08-27', '2020-10-14'),
        ['2020-08-31', '2020-09-30', '2020-10-14']
    );
});

test('uses quarterly snapshots before the latest year', () => {
    const dates = stability.stabilitySnapshotDates('2020-01-01', '2022-08-02');

    assert.equal(dates.includes('2020-01-31'), false);
    assert.equal(dates.includes('2020-03-31'), true);
    assert.equal(dates.includes('2021-09-30'), true);
    assert.equal(dates.includes('2021-10-31'), true);
    assert.equal(dates.at(-1), '2022-08-02');
});

test('uses the scatterplot paired-score rule for historical correlations', () => {
    const result = stability.pairedCorrelation([
        {'left-score': 1, 'left-is_complete': 1, 'right-score': 2, 'right-is_complete': 1},
        {'left-score': 2, 'left-is_complete': 1, 'right-score': 4, 'right-is_complete': 1},
        {'left-score': 0, 'left-is_complete': 1, 'right-score': 0, 'right-is_complete': 1},
        {'left-score': '', 'left-is_complete': 0, 'right-score': 8, 'right-is_complete': 1}
    ], 'left', 'right');

    assert.equal(result.r, 1);
    assert.equal(result.n, 3);
});

test('builds stability snapshots incrementally between scheduled tasks', async () => {
    const payload = {
        domain: 'vision',
        datetime_range: {min: '2025-01-01', max: '2025-02-28'},
        benchmarks: [
            {id: 'average_vision_v0', type_id: 'average_vision', parent_id: null, is_leaf: false, is_engineering: false, versions: [{version: 0}]},
            {id: 'left_v0', type_id: 'left', parent_id: 'average_vision_v0', is_leaf: true, is_engineering: false, versions: [{version: 0}]},
            {id: 'right_v0', type_id: 'right', parent_id: 'average_vision_v0', is_leaf: true, is_engineering: false, versions: [{version: 0}]}
        ],
        models: [
            {id: 1, name: 'one', submission_timestamp: null, scores: {left: [{version: 0, value: 1}], right: [{version: 0, value: 2}]}},
            {id: 2, name: 'two', submission_timestamp: null, scores: {left: [{version: 0, value: 2}], right: [{version: 0, value: 4}]}}
        ]
    };
    const options = {
        firstBenchmarkId: 'left_v0',
        secondBenchmarkId: 'right_v0',
        dates: ['2025-01-31', '2025-02-28']
    };
    const tasks = [];
    const resultPromise = stability.buildStabilitySeriesIncrementally(
        payload,
        options,
        callback => tasks.push(callback)
    );

    assert.equal(tasks.length, 1);
    while (tasks.length) tasks.shift()();
    const result = await resultPromise;

    assert.deepEqual(result, stability.buildStabilitySeries(payload, options));
    assert.equal(result.length, 2);
});

test('resolves the correlation helper after stability initializes', () => {
    const source = fs.readFileSync(path.join(__dirname, '../compare-stability.js'), 'utf8');
    const browserContext = {CompareDashboardCore: {}};
    vm.createContext(browserContext);
    vm.runInContext(source, browserContext);

    browserContext.CompareCorrelationCore = correlation;
    const result = browserContext.CompareStabilityCore.pairedCorrelation([
        {'left-score': 1, 'left-is_complete': 1, 'right-score': 2, 'right-is_complete': 1},
        {'left-score': 2, 'left-is_complete': 1, 'right-score': 4, 'right-is_complete': 1}
    ], 'left', 'right');

    assert.equal(result.r, 1);
    assert.equal(result.n, 2);
});

test('exports readable stability data without benchmark ids', () => {
    const csv = stability.stabilityToCsv([
        {date: '2026-07-31', r: 0.42, n: 18},
        {date: '2026-08-02', r: null, n: 1}
    ], {
        firstLabel: 'Neural',
        secondLabel: 'Behavioral',
        minimumCompleteness: 50
    });

    assert.match(csv, /horizontal_benchmark,vertical_benchmark/);
    assert.match(csv, /Neural,Behavioral,50/);
    assert.equal(csv.includes('_id'), false);
});

test('reduces compact timeline dates to three readable ticks', () => {
    assert.deepEqual(stability.compactDateTicks([
        '2020-03-31', '2021-03-31', '2022-03-31', '2023-03-31', '2024-03-31'
    ]), [
        {value: '2020-03-31', label: '2020-03'},
        {value: '2022-03-31', label: '2022-03'},
        {value: '2024-03-31', label: '2024-03'}
    ]);
});

test('makes the compact timeline static and the expanded timeline interactive', () => {
    const series = [
        {date: '2025-03-31', r: 0.4, n: 20},
        {date: '2026-08-02', r: 0.6, n: 40}
    ];
    const compact = stability.buildPlotlyStability(series, {compact: true});
    const expanded = stability.buildPlotlyStability(series, {compact: false});

    assert.equal(compact.config.staticPlot, true);
    assert.equal(compact.config.displayModeBar, false);
    assert.deepEqual(compact.layout.yaxis.tickvals, [-1, 0, 1]);
    assert.equal(compact.layout.xaxis.tickvals.length, 2);
    assert.equal(expanded.config.staticPlot, false);
    assert.equal(expanded.config.displayModeBar, true);
    assert.equal(expanded.layout.hovermode, 'x unified');
    assert.equal(expanded.layout.xaxis.title, 'Wayback date');
    assert.equal(expanded.layout.yaxis.title.text, 'Pearson r');
    assert.equal(expanded.layout.yaxis2.title.text, 'Paired models');
    assert.equal(expanded.layout.yaxis.automargin, true);
    assert.equal(expanded.layout.yaxis2.automargin, true);
});
