// export CSV logic:
document.getElementById('exportCsvButton')?.addEventListener('click', function () {
  if (!window.globalGridApi || !window.benchmarkTree) {
    console.warn('Grid or benchmark tree not ready');
    return;
  }

  const hierarchyMap = buildHierarchyFromTree(window.benchmarkTree || []);
  const allColumns = window.globalGridApi.getColumnDefs();
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  
  // Include benchmarks hidden by wayback filtering
  const waybackHiddenBenchmarks = window.waybackHiddenBenchmarks || new Set();
  const allExcludedBenchmarks = new Set([...excludedBenchmarks, ...waybackHiddenBenchmarks]);

  // Fixed columns (model_id added for database cross-referencing)
  const fixedOrder = ['rank', 'model', 'model_id', 'filtered_score', 'average_vision_v0'];
  // model_id is derived from row data, not a real column, so always include it
  const fixedColumns = fixedOrder.filter(id =>
    id === 'model_id' || allColumns.some(col => col.colId === id)
  );

  // Collect benchmark columns in BFS order, excluding filtered-out ones and wayback-hidden ones
  const benchmarkColumns = [];
  const visited = new Set();
  const queue = [...hierarchyMap.keys()];
  while (queue.length) {
    const current = queue.shift();
    if (visited.has(current) || allExcludedBenchmarks.has(current)) continue;
    visited.add(current);
    const col = allColumns.find(c => c.colId === current || c.field === current);
    if (col) benchmarkColumns.push(current);
    const children = hierarchyMap.get(current) || [];
    queue.push(...children);
  }

  const columnKeys = [...fixedColumns, ...benchmarkColumns].filter(id => id !== 'group_status');

  // Build leaderboard CSV manually
  const rows = [];
  const headerRow = columnKeys.map(id => {
    // Special case for model_id which is derived, not a real column
    if (id === 'model_id') return '"Model ID"';
    const col = allColumns.find(c => c.colId === id);
    return `"${col?.headerName || id}"`;
  }).join(',');
  rows.push(headerRow);

  // Collect nodes respecting current grid sort order
  const nodes = [];
  window.globalGridApi.forEachNodeAfterFilter(node => {
    nodes.push(node);
  });
  
  // Sort nodes according to grid's current sort state
  // Get sort state from columns (AG Grid doesn't have getSortModel, use getColumnState or iterate columns)
  const sortColumns = [];
  window.globalGridApi.getAllGridColumns().forEach(column => {
    const sort = column.getSort();
    if (sort) {
      sortColumns.push({ colId: column.getColId(), sort: sort });
    }
  });
  
  if (sortColumns.length > 0) {
    nodes.sort((a, b) => {
      for (const sortCol of sortColumns) {
        const colId = sortCol.colId;
        let aVal = a.data?.[colId];
        let bVal = b.data?.[colId];
        
        // Handle object values (like score objects with .value property)
        if (typeof aVal === 'object' && aVal !== null && 'value' in aVal) {
          aVal = aVal.value;
        }
        if (typeof bVal === 'object' && bVal !== null && 'value' in bVal) {
          bVal = bVal.value;
        }
        
        // Handle model name
        if (colId === 'model') {
          aVal = aVal?.name || '';
          bVal = bVal?.name || '';
        }
        
        // Compare values
        if (aVal === bVal) continue;
        if (aVal == null) return 1;
        if (bVal == null) return -1;
        if (aVal === 'X') return 1;
        if (bVal === 'X') return -1;
        
        const comparison = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
        return sortCol.sort === 'desc' ? -comparison : comparison;
      }
      return 0;
    });
  }

  // Build CSV rows from sorted nodes
  nodes.forEach(node => {
    const row = columnKeys.map(colId => {
      const val = node.data?.[colId];
      if (colId === 'model') return `"${val?.name || ''}"`;
      if (colId === 'model_id') return `"${node.data?.id || node.data?.model?.id || ''}"`;
      if (colId === 'submitter') return `"${val?.submitter || ''}"`;
      if (typeof val === 'object' && val !== null && 'value' in val)
        return val.value === 'X' ? '' : `"${val.value}"`;
      return `"${val ?? ''}"`;
    }).join(',');
    rows.push(row);
  });
  const leaderboardCsv = rows.join('\n');

  // Get local timestamp
  const now = new Date();
  const tz = Intl.DateTimeFormat('en-US', { timeZoneName: 'short' })
    .formatToParts(now).find(part => part.type === 'timeZoneName')?.value || 'local';

  // Create datetime comment for CSV files
  const datetimeComment = `# Generated on ${now.toISOString()} (${tz})`;
  // Wayback date range logic
  const DEFAULT_MIN_TS = 1598524327; // 2020 baseline in seconds

  let minTs = window.activeFilters?.min_wayback_timestamp;
  let maxTs = window.activeFilters?.max_wayback_timestamp;

  // Set min to DEFAULT_MIN_TS if it's not been interacted with
  if (minTs == null || minTs < DEFAULT_MIN_TS) {
    minTs = DEFAULT_MIN_TS;
  }

  let startDate = new Date(minTs * 1000);

  // For max: if it's missing or still in 1970, use "now"
  let endDate;
  if (maxTs == null) {
    endDate = now;
  } else {
    const tentativeEnd = new Date(maxTs * 1000);
    if (tentativeEnd.getUTCFullYear() === 1970) {
      endDate = now;
    } else {
      endDate = tentativeEnd;
    }
  }
  const waybackComment = `# Date from ${startDate.toISOString()} to ${endDate.toISOString()}`;

  // Add datetime comment to leaderboard CSV
  const leaderboardCsvWithComment = `${datetimeComment}\n${waybackComment}\n${leaderboardCsv}`;

  const blob = new Blob([leaderboardCsvWithComment], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'leaderboard.csv';
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
});
