// export CSV logic:
document.getElementById('exportCsvButton')?.addEventListener('click', async function () {
  if (!window.globalGridApi || !window.benchmarkTree) {
    console.warn('Grid or benchmark tree not ready');
    return;
  }

  const hierarchyMap = buildHierarchyFromTree(window.benchmarkTree || []);
  const allColumns = window.globalGridApi.getColumnDefs();
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);

  // Fixed columns
  const fixedOrder = ['rank', 'model', 'filtered_score', 'average_vision_v0'];
  const fixedColumns = fixedOrder.filter(id =>
    allColumns.some(col => col.colId === id)
  );

  // Collect benchmark columns in BFS order, excluding filtered-out ones
  const benchmarkColumns = [];
  const visited = new Set();
  const queue = [...hierarchyMap.keys()];
  while (queue.length) {
    const current = queue.shift();
    if (visited.has(current) || excludedBenchmarks.has(current)) continue;
    visited.add(current);
    const col = allColumns.find(c => c.colId === current || c.field === current);
    if (col) benchmarkColumns.push(current);
    const children = hierarchyMap.get(current) || [];
    queue.push(...children);
  }

  const columnKeys = [...fixedColumns, ...benchmarkColumns].filter(id => id !== 'runnable_status');

  // Build leaderboard CSV manually
  const rows = [];
  const headerRow = columnKeys.map(id => {
    const col = allColumns.find(c => c.colId === id);
    return `"${col?.headerName || id}"`;
  }).join(',');
  rows.push(headerRow);

  window.globalGridApi.forEachNodeAfterFilter(node => {
    const row = columnKeys.map(colId => {
      const val = node.data?.[colId];
      if (colId === 'model') return `"${val?.name || ''}"`;
      if (colId === 'submitter') return `"${val?.submitter || ''}"`;
      if (typeof val === 'object' && val !== null && 'value' in val)
        return val.value === 'X' ? '' : `"${val.value}"`;
      return `"${val ?? ''}"`;
    }).join(',');
    rows.push(row);
  });
  const leaderboardCsv = rows.join('\n');

  // Create plugins CSV
  const pluginRows = [['plugin_name', 'plugin_type', 'metadata']];

  // Add model rows
  window.globalGridApi.forEachNodeAfterFilter(node => {
    const modelName = node.data?.model?.name;
    if (!modelName) return;
    // grab per‐model metadata from the map we created
    const meta = window.modelMetadataMap[modelName] || node.data.metadata || {};
    const modelJson = JSON.stringify(meta).replace(/"/g, '""');
    const modelCell = `"${modelJson}"`;
    pluginRows.push([
      modelName,
      'model',
      modelCell
    ]);
  });

  // Add benchmark leaf nodes that are *not excluded*
  const benchmarkLeafIds = [];
  const queue2 = [...window.benchmarkTree];
  while (queue2.length) {
    const node = queue2.shift();
    if (node.children && node.children.length) {
      queue2.push(...node.children);
    } else {
      if (!excludedBenchmarks.has(node.id)) {
        benchmarkLeafIds.push(node.id);
      }
    }
  }

  benchmarkLeafIds.forEach(id => {
    // look up the metadata entry for this benchmark
    const stimuliMeta = (window.benchmarkStimuliMetaMap || {})[id] || {};
    const dataMeta    = (window.benchmarkDataMetaMap    || {})[id] || {};
    const metricMeta  = (window.benchmarkMetricMetaMap  || {})[id] || {};
    const combined    = { Stimuli: stimuliMeta, Data: dataMeta, Metric: metricMeta };
    const jsonStr     = JSON.stringify(combined).replace(/"/g,'""');
    pluginRows.push([ id, 'benchmark', `"${jsonStr}"` ]);
  });

  const pluginCsv = pluginRows
    .map(row => row.join(','))
    .join('\n');

  // Get local timestamp
  const now = new Date();
  const pad = n => String(n).padStart(2, '0');
  const tz = Intl.DateTimeFormat('en-US', { timeZoneName: 'short' })
    .formatToParts(now).find(part => part.type === 'timeZoneName')?.value || 'local';
  const timestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}_${pad(now.getHours())}-${pad(now.getMinutes())}-${pad(now.getSeconds())}_${tz}`;

  // Create datetime comment for CSV files
  const datetimeComment = `# Generated on ${now.toISOString()} (${tz})`;

  // Add datetime comment to leaderboard CSV
  const leaderboardCsvWithComment = `${datetimeComment}\n${leaderboardCsv}`;

  // Add datetime comment to plugin CSV
  const pluginCsvWithComment = `${datetimeComment}\n${pluginCsv}`;

  // Create ZIP
  const zip = new JSZip();
  zip.file('leaderboard.csv', leaderboardCsvWithComment);
  zip.file('plugin-info.csv', pluginCsvWithComment);

  const zipBlob = await zip.generateAsync({ type: 'blob' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(zipBlob);
  link.download = `leaderboard_export_${timestamp}.zip`;
  link.click();
});
