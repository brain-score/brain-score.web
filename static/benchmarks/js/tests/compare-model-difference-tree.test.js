const test = require('node:test');
const assert = require('node:assert/strict');

const differenceTree = require('../compare-model-difference-tree.js');

function benchmarks() {
    return [
        {id: 'average_vision_v0', type_id: 'average_vision', label: 'average_vision', parent_id: null, is_leaf: false, is_engineering: false},
        {id: 'neural_vision_v0', type_id: 'neural_vision', label: 'neural_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'neural-a_v0', type_id: 'neural-a', label: 'Neural A', parent_id: 'neural_vision_v0', is_leaf: true, is_engineering: false},
        {id: 'neural-b_v0', type_id: 'neural-b', label: 'Neural B', parent_id: 'neural_vision_v0', is_leaf: true, is_engineering: false},
        {id: 'behavior_vision_v0', type_id: 'behavior_vision', label: 'behavior_vision', parent_id: 'average_vision_v0', is_leaf: false, is_engineering: false},
        {id: 'behavior-a_v0', type_id: 'behavior-a', label: 'Behavior A', parent_id: 'behavior_vision_v0', is_leaf: true, is_engineering: false},
        {id: 'engineering_vision_v0', type_id: 'engineering_vision', label: 'engineering_vision', parent_id: null, is_leaf: false, is_engineering: true},
        {id: 'engineering-a_v0', type_id: 'engineering-a', label: 'Engineering A', parent_id: 'engineering_vision_v0', is_leaf: true, is_engineering: true}
    ];
}

test('aggregates shared leaves through the benchmark hierarchy', () => {
    const tree = differenceTree.buildDifferenceTree(benchmarks(), [
        {benchId: 'neural-a_v0', scoreA: 0.8, scoreB: 0.6},
        {benchId: 'neural-b_v0', scoreA: 0.4, scoreB: 0.2},
        {benchId: 'behavior-a_v0', scoreA: 0.3, scoreB: 0.5},
        {benchId: 'engineering-a_v0', scoreA: 0.9, scoreB: 0.1}
    ]);

    assert.equal(tree.length, 1);
    assert.equal(tree[0].label, 'Vision');
    assert.equal(tree[0].leafCount, 3);
    assert.ok(Math.abs(tree[0].children[0].scoreA - 0.6) < 1e-12);
    assert.ok(Math.abs(tree[0].children[0].scoreB - 0.4) < 1e-12);
    assert.ok(Math.abs(tree[0].scoreA - 0.45) < 1e-12);
    assert.ok(Math.abs(tree[0].scoreB - 0.45) < 1e-12);
    assert.equal(differenceTree.flattenTree(tree).some(row => row.benchmark === 'Engineering A'), false);
});

test('exports readable difference-tree columns without ids', () => {
    const tree = differenceTree.buildDifferenceTree(benchmarks(), [
        {benchId: 'neural-a_v0', scoreA: 0.8, scoreB: 0.6}
    ]);
    const csv = differenceTree.differenceTreeToCsv(tree, 'Model A', 'Model B');

    assert.match(csv, /benchmark,parent,tree_level,shared_leaves,Model A,Model B,difference/);
    assert.equal(csv.includes('_id'), false);
});
