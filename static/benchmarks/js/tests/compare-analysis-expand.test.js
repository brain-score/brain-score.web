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

test('preserves the original collapsed size across repeated toggles', () => {
    const plot = {
        data: [{}],
        layout: {height: 620, autosize: true},
        _fullLayout: {height: 620},
        clientHeight: 620
    };
    const updates = [];
    const plotly = {
        relayout(_plot, update) {
            updates.push(update);
            _plot.layout.height = update.height;
            _plot.layout.width = update.width;
            _plot.layout.autosize = update.autosize;
        },
        Plots: {resize() {}}
    };
    const panel = {querySelectorAll() { return [plot]; }};
    const browserRoot = {
        Plotly: plotly,
        innerHeight: 1000,
        requestAnimationFrame(callback) { callback(); }
    };

    expand.resizePlots(panel, true, browserRoot);
    expand.resizePlots(panel, false, browserRoot);
    expand.rememberCollapsedPlotSize(plot, {height: 540, width: null, autosize: true});
    expand.resizePlots(panel, true, browserRoot);
    expand.resizePlots(panel, false, browserRoot);

    assert.equal(updates[0].height, 770);
    assert.equal(updates[1].height, 620);
    assert.equal(updates[2].height, 770);
    assert.equal(updates[3].height, 540);
    assert.equal(updates[1].autosize, true);
    assert.equal(updates[3].width, null);
});
