const test = require('node:test');
const assert = require('node:assert/strict');

const branchRanks = require('../compare-model-branch-ranks.js');

function benchmarks() {
    return [
        {id: 'average_vision_v0', type_id: 'average_vision', label: 'average_vision', is_engineering: false},
        {id: 'neural_vision_v0', type_id: 'neural_vision', label: 'neural_vision', is_engineering: false},
        {id: 'V1_v0', type_id: 'V1', label: 'V1', is_engineering: false},
        {id: 'behavior_vision_v0', type_id: 'behavior_vision', label: 'behavior_vision', is_engineering: false},
        {id: 'engineering_vision_v0', type_id: 'engineering_vision', label: 'engineering_vision', is_engineering: true}
    ];
}

test('selects official vision summary branches in display order', () => {
    assert.deepEqual(
        branchRanks.selectRankBranches(benchmarks(), 'vision').map(item => item.type_id),
        ['average_vision', 'neural_vision', 'V1', 'behavior_vision']
    );
});

test('ranks both models against every eligible model within a branch', () => {
    const rows = [
        {model_id: 1, model: 'Model A', 'average_vision_v0-score': 0.8},
        {model_id: 2, model: 'Model B', 'average_vision_v0-score': 0.6},
        {model_id: 3, model: 'Leader', 'average_vision_v0-score': 0.9},
        {model_id: 4, model: 'Tie', 'average_vision_v0-score': 0.6}
    ];
    const result = branchRanks.buildBranchRanks(
        benchmarks().slice(0, 1), rows, 'vision', 1, 2
    );

    assert.equal(result.length, 1);
    assert.equal(result[0].rankA, 2);
    assert.equal(result[0].rankB, 3);
    assert.equal(result[0].eligibleModels, 4);
});

test('exports readable branch ranks without ids', () => {
    const csv = branchRanks.branchRanksToCsv([{
        benchmark: 'Neural', rankA: 2, scoreA: 0.7,
        rankB: 4, scoreB: 0.6, eligibleModels: 20
    }], 'Model A', 'Model B');

    assert.match(csv, /benchmark_branch,Model A_rank,Model A_score,Model B_rank,Model B_score,eligible_models/);
    assert.equal(csv.includes('_id'), false);
});

test('scales the rank axis to the compared models', () => {
    const plot = branchRanks.buildPlotlyBranchRanks([{
        benchmark: 'Neural', rankA: 2, scoreA: 0.7,
        rankB: 6, scoreB: 0.6, eligibleModels: 120
    }], {nameA: 'Model A', nameB: 'Model B'});

    assert.deepEqual(plot.layout.xaxis.range, [0.5, 6.5]);
    assert.equal(plot.layout.xaxis.dtick, 1);
});
