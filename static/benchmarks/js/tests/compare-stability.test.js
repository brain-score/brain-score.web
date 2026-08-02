const test = require('node:test');
const assert = require('node:assert/strict');

const stability = require('../compare-stability.js');

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
    assert.equal(expanded.layout.xaxis.title, 'Wayback date');
});
