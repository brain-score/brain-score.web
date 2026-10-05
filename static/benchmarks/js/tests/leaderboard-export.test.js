const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('downloads only filtered and sorted leaderboard scores as CSV', async () => {
  let onClick, download, blob, revoked;
  const nodes = [
    { data: { id: 7, rank: 2, model: { name: 'lower' }, average_vision_v0: { value: 0.3 }, visible: { value: 0.2 } } },
    { data: { id: 42, rank: 1, model: { name: 'higher' }, average_vision_v0: { value: 0.8 }, visible: { value: 0.7 } } },
  ];
  const columns = ['rank', 'model', 'average_vision_v0', 'visible', 'excluded', 'wayback-hidden']
    .map(colId => ({ colId, headerName: colId }));
  const button = { addEventListener: (type, fn) => { assert.equal(type, 'click'); onClick = fn; } };
  const link = { click() { download = { name: this.download, href: this.href }; }, remove() {} };
  const context = {
    Blob, Set, Date, Intl, console, setTimeout: fn => fn(),
    URL: { createObjectURL(value) { blob = value; return 'blob:leaderboard'; }, revokeObjectURL(url) { revoked = url; } },
    document: { getElementById: id => { assert.equal(id, 'exportCsvButton'); return button; },
                createElement: name => { assert.equal(name, 'a'); return link; },
                body: { appendChild: child => assert.equal(child, link) } },
    window: {
      benchmarkTree: [], filteredOutBenchmarks: ['excluded'],
      waybackHiddenBenchmarks: new Set(['wayback-hidden']),
      globalGridApi: {
        getColumnDefs: () => columns,
        forEachNodeAfterFilter: fn => nodes.forEach(fn),
        getAllGridColumns: () => [{ getSort: () => 'desc', getColId: () => 'average_vision_v0' }],
      },
    },
    buildHierarchyFromTree: () => new Map([['visible', []], ['excluded', []], ['wayback-hidden', []]]),
  };
  Object.defineProperty(context, 'JSZip', { get() { throw Error('ZIP export must not run'); } });
  Object.defineProperty(context.window, 'modelMetadataMap', { get() { throw Error('Legacy metadata must not be read'); } });
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../leaderboard/export/csv-export.js'), 'utf8'), context);
  onClick();
  assert.equal(download.name, 'leaderboard.csv');
  assert.equal(download.href, 'blob:leaderboard');
  assert.equal(blob.type, 'text/csv;charset=utf-8');
  assert.equal(revoked, download.href);
  const lines = (await blob.text()).split('\n');
  assert.match(lines[0], /^# Generated on /);
  assert.match(lines[1], /^# Date from /);
  assert.deepEqual(lines.slice(2), [
    '"rank","model","Model ID","average_vision_v0","visible"',
    '"1","higher","42","0.8","0.7"',
    '"2","lower","7","0.3","0.2"',
  ]);
});
