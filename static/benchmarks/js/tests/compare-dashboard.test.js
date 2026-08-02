const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const dashboard = require('../compare-dashboard.js');

function payload() {
    return {
        domain: 'vision',
        datetime_range: {min_unix: 1598486400, max_unix: 1785715200},
        benchmarks: [
            {id: 'average_vision_v0', type_id: 'average_vision', parent_id: null, is_leaf: false, is_engineering: false, versions: [{version: 0}]},
            {id: 'neural_vision_v0', type_id: 'neural_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: false, versions: [{version: 0}]},
            {id: 'behavior_vision_v0', type_id: 'behavior_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: false, versions: [{version: 0}]},
            {id: 'engineering_vision_v0', type_id: 'engineering_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: true, versions: [{version: 0}]},
            {
                id: 'neural-leaf_v1', type_id: 'neural-leaf', parent_id: 'neural_vision_v0',
                is_leaf: true, is_engineering: false,
                versions: [
                    {version: 0, valid_from: '2020-01-01T00:00:00Z', valid_to: '2022-01-01T00:00:00Z'},
                    {version: 1, valid_from: '2022-01-01T00:00:00Z', valid_to: null}
                ]
            },
            {id: 'behavior-leaf_v0', type_id: 'behavior-leaf', parent_id: 'behavior_vision_v0', is_leaf: true, is_engineering: false, versions: [{version: 0}]},
            {id: 'engineering-leaf_v0', type_id: 'engineering-leaf', parent_id: 'engineering_vision_v0', is_leaf: true, is_engineering: true, versions: [{version: 0}]}
        ],
        models: [
            {
                id: 1, name: 'duplicate-name', submission_timestamp: '2020-02-01T00:00:00Z',
                scores: {
                    'neural-leaf': [
                        {version: 0, value: 0.4, timestamp: '2020-03-01T00:00:00Z'},
                        {version: 1, value: 0.8, timestamp: '2022-03-01T00:00:00Z'}
                    ],
                    'behavior-leaf': [{version: 0, value: 0.5, timestamp: '2020-03-01T00:00:00Z'}],
                    'engineering-leaf': [{version: 0, value: 0.9, timestamp: '2020-03-01T00:00:00Z'}]
                }
            },
            {
                id: 2, name: 'duplicate-name', submission_timestamp: '2020-02-01T00:00:00Z',
                scores: {
                    'neural-leaf': [{version: 0, value: 0, timestamp: '2020-03-01T00:00:00Z'}],
                    'behavior-leaf': [{version: 0, value: 'NaN', timestamp: '2020-03-01T00:00:00Z'}],
                    'engineering-leaf': [{version: 0, value: 0.7, timestamp: '2020-03-01T00:00:00Z'}]
                }
            },
            {
                id: 3, name: 'future-model', submission_timestamp: '2023-01-01T00:00:00Z',
                scores: {}
            }
        ]
    };
}

function addLaterNeuralLeaf(data) {
    data.benchmarks.push({
        id: 'neural-late_v0', type_id: 'neural-late', parent_id: 'neural_vision_v0',
        is_leaf: true, is_engineering: false,
        versions: [{version: 0, valid_from: '2022-01-01T00:00:00Z', valid_to: null}]
    });
    data.models[0].scores['neural-late'] = [
        {version: 0, value: 0.6, timestamp: '2022-03-01T00:00:00Z'}
    ];
    return data;
}

test('defaults benchmark comparisons to neural versus behavior', () => {
    assert.deepEqual(
        dashboard.defaultComparisonBenchmarkTypes('vision'),
        ['neural_vision', 'behavior_vision']
    );
    assert.deepEqual(
        dashboard.defaultComparisonBenchmarkTypes('language'),
        ['neural_language', 'behavior_language']
    );
});

test('uses the latest benchmark version from the first version start date', () => {
    const oldCohort = dashboard.resolveCohort(payload(), {
        asOfDate: '2021-06-01'
    });
    assert.equal(oldCohort.rows[0]['neural-leaf_v1-score'], 0.8);
    assert.equal(oldCohort.rows[0]['neural-leaf_v1-active_version'], 1);

    const currentCohort = dashboard.resolveCohort(payload(), {
        asOfDate: '2023-06-01'
    });
    assert.equal(currentCohort.rows[0]['neural-leaf_v1-score'], 0.8);
    assert.equal(currentCohort.rows[0]['neural-leaf_v1-active_version'], 1);
});

test('does not expose a benchmark before its first version existed', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2019-06-01'
    });
    assert.equal(result.activeBenchmarkIds['neural-leaf_v1'], undefined);
});

test('removes models submitted after the wayback date', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2021-06-01'
    });
    assert.deepEqual(result.rows.map(row => row.model_id), [1, 2]);
});

test('does not backdate a score recorded after the cutoff', () => {
    const data = payload();
    data.models[0].scores['behavior-leaf'][0].timestamp = '2022-01-01T00:00:00Z';
    const result = dashboard.resolveCohort(data, {
        asOfDate: '2021-06-01'
    });
    const row = result.rows.find(item => item.model_id === 1);
    assert.equal(row['behavior-leaf_v0-score'], '');
    assert.equal(row.completeness, 50);
});

test('excludes engineering from completedness but retains its scores', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2021-06-01'
    });
    const complete = result.rows.find(row => row.model_id === 1);
    const incomplete = result.rows.find(row => row.model_id === 2);
    assert.equal(result.completenessBenchmarkCount, 2);
    assert.equal(complete.completeness, 100);
    assert.equal(incomplete.completeness, 0);
    assert.equal(incomplete['engineering-leaf_v0-score'], 0.7);
});

test('treats zero and NaN as incomplete without removing the model', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2021-06-01'
    });
    assert.deepEqual(result.rows.map(row => row.model_id), [1, 2]);
    assert.equal(result.rows.find(row => row.model_id === 2).completeness, 0);
});

test('filters the benchmark cohort by an inclusive completedness threshold', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2023-06-01', minimumCompleteness: 100
    });
    assert.deepEqual(
        result.rows.map(row => row.model_id),
        [1]
    );
});

test('selects the top two ranked models for language comparison defaults', () => {
    const modelIds = dashboard.topRankedModelIds([
        {model_id: 4, model: 'unranked', rank: null},
        {model_id: 3, model: 'third', rank: 3},
        {model_id: 2, model: 'second', rank: 2},
        {model_id: 1, model: 'first', rank: 1}
    ], 2);

    assert.deepEqual(modelIds, [1, 2]);
});

test('calculates completedness from the two selected benchmark subtrees', () => {
    const data = addLaterNeuralLeaf(payload());
    data.models.push({
        id: 4, name: 'selected-pair-only', submission_timestamp: '2020-02-01T00:00:00Z',
        scores: {
            'neural-leaf': [{version: 1, value: 0.3, timestamp: '2020-03-01T00:00:00Z'}],
            'behavior-leaf': [{version: 0, value: 0.4, timestamp: '2020-03-01T00:00:00Z'}]
        }
    });

    const selectedPair = dashboard.resolveCohort(data, {
        asOfDate: '2023-06-01',
        minimumCompleteness: 100,
        comparisonBenchmarkIds: ['neural-leaf_v1', 'behavior-leaf_v0']
    });
    assert.deepEqual(selectedPair.completenessBenchmarkIds, [
        'neural-leaf_v1', 'behavior-leaf_v0'
    ]);
    assert.deepEqual(selectedPair.rows.map(row => row.model_id), [1, 4]);
    assert.equal(selectedPair.rows.find(row => row.model_id === 4).completeness, 100);

    const fullSuite = dashboard.resolveCohort(data, {
        asOfDate: '2023-06-01', minimumCompleteness: 100
    });
    assert.equal(fullSuite.completenessBenchmarkCount, 3);
    assert.deepEqual(fullSuite.rows.map(row => row.model_id), [1]);
});

test('updates parent-category completedness as active descendants change', () => {
    const data = addLaterNeuralLeaf(payload());
    const selectedParents = ['neural_vision_v0', 'behavior_vision_v0'];
    const historical = dashboard.resolveCohort(data, {
        asOfDate: '2021-06-01', comparisonBenchmarkIds: selectedParents
    });
    const current = dashboard.resolveCohort(data, {
        asOfDate: '2023-06-01', comparisonBenchmarkIds: selectedParents
    });
    assert.deepEqual(historical.completenessBenchmarkIds, [
        'neural-leaf_v1', 'behavior-leaf_v0'
    ]);
    assert.deepEqual(current.completenessBenchmarkIds, [
        'neural-leaf_v1', 'behavior-leaf_v0', 'neural-late_v0'
    ]);

    const overlappingSelection = dashboard.resolveCohort(data, {
        asOfDate: '2023-06-01',
        comparisonBenchmarkIds: ['neural_vision_v0', 'neural-leaf_v1']
    });
    assert.deepEqual(overlappingSelection.completenessBenchmarkIds, [
        'neural-leaf_v1', 'neural-late_v0'
    ]);
});

test('keeps duplicate model names distinct by model id', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2021-06-01'
    });
    assert.equal(result.rows.length, 2);
    assert.deepEqual(result.rows.map(row => row.model_id), [1, 2]);
});

test('rebuilds historical parent aggregates from active leaves', () => {
    const result = dashboard.resolveCohort(payload(), {
        asOfDate: '2021-06-01'
    });
    const row = result.rows.find(item => item.model_id === 1);
    assert.equal(row['neural_vision_v0-score'], 0.8);
    assert.equal(row['behavior_vision_v0-score'], 0.5);
    assert.equal(row['engineering_vision_v0-score'], 0.9);
    assert.equal(row['average_vision_v0-score'], (0.8 + 0.5 + 0.9) / 3);
});

test('restores the date but starts completedness at zero', () => {
    let currentHref = 'http://localhost/vision/compare/?as_of=2021-06-01&min_complete=50';
    const fakeRoot = {
        location: {
            href: currentHref,
            search: '?as_of=2021-06-01&min_complete=50'
        },
        URL,
        URLSearchParams,
        history: {
            replaceState(_state, _title, value) {
                currentHref = 'http://localhost' + value;
                fakeRoot.location.href = currentHref;
                fakeRoot.location.search = new URL(currentHref).search;
            }
        }
    };
    const instance = dashboard.createDashboard(payload(), fakeRoot);
    assert.equal(instance.getState().asOfDate, '2021-06-01');
    assert.equal(instance.getState().minimumCompleteness, 0);
    assert.doesNotMatch(currentHref, /min_complete/);
    assert.deepEqual(
        instance.getComparisonData().map(row => row.model_id),
        [1, 2]
    );
    assert.deepEqual(
        instance.getLatestComparisonData().map(row => row.model_id),
        [1, 2, 3]
    );
    assert.equal(instance.getLatestRow(3).model, 'future-model');
    assert.equal(instance.getBenchmarkTypeId('neural-leaf_v1'), 'neural-leaf');
    assert.equal(instance.getBenchmarkIdByTypeId('neural-leaf'), 'neural-leaf_v1');
    instance.setComparisonBenchmarks('neural-leaf_v1', 'neural-leaf_v1');
    assert.deepEqual(instance.getState().comparisonBenchmarkIds, ['neural-leaf_v1']);
    assert.equal(instance.getResolved().completenessBenchmarkCount, 1);
    instance.reset();
    assert.doesNotMatch(currentHref, /as_of|min_complete/);
});

test('converts wayback slider days without local timezone drift', () => {
    const day = dashboard.dateToUtcDay('2021-06-01');
    assert.equal(dashboard.utcDayToDate(day), '2021-06-01');
    assert.equal(dashboard.utcDayToDate(day + 1), '2021-06-02');
});

test('initializes the UI after a deferred script creates the dashboard API', () => {
    const elements = {};
    function element(id) {
        elements[id] = {
            id,
            style: {},
            value: '',
            textContent: '',
            innerHTML: '',
            addEventListener() {},
            setAttribute(name, value) { this[name] = value; }
        };
        return elements[id];
    }
    [
        'compare-dashboard', 'compare-wayback-range',
        'compare-wayback-value', 'compare-wayback-min-label',
        'compare-completeness-range', 'compare-completeness-number',
        'compare-dashboard-reset', 'compare-kpi-models',
        'compare-kpi-benchmarks', 'compare-kpi-date',
        'compare-kpi-median', 'compare-completeness-histogram',
        'compare-dashboard-empty'
    ].forEach(element);

    const context = {
        compare_dashboard_data: payload(),
        document: {
            readyState: 'interactive',
            getElementById(id) { return elements[id] || null; },
            dispatchEvent() {}
        },
        location: {
            href: 'http://localhost/vision/compare/',
            search: ''
        },
        history: {replaceState() {}},
        URL,
        URLSearchParams,
        setTimeout,
        clearTimeout
    };
    context.globalThis = context;

    const source = fs.readFileSync(require.resolve('../compare-dashboard.js'), 'utf8');
    vm.runInNewContext(source, context);

    assert.ok(context.CompareDashboard);
    assert.equal(elements['compare-kpi-models'].textContent, '3');
    assert.equal(elements['compare-kpi-benchmarks'].textContent, '2');
    assert.equal(elements['compare-kpi-median'].textContent, '0.0%');
    assert.equal(elements['compare-completeness-range'].value, 0);
    assert.equal(elements['compare-wayback-value'].textContent, '2026-08-03');
    assert.equal(elements['compare-wayback-min-label'].textContent, '2020-08-27');
});
