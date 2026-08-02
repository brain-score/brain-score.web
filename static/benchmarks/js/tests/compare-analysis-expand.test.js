const test = require('node:test');
const assert = require('node:assert/strict');

const expand = require('../compare-analysis-expand.js');

test('uses icon-only expand and collapse states', () => {
    assert.equal(
        expand.expandIconClass(false),
        'fa-solid fa-up-right-and-down-left-from-center'
    );
    assert.equal(
        expand.expandIconClass(true),
        'fa-solid fa-down-left-and-up-right-to-center'
    );
});

test('leaves useful plot height while enforcing a minimum', () => {
    assert.equal(expand.expandedPlotHeight(1000), 770);
    assert.equal(expand.expandedPlotHeight(600), 480);
});
