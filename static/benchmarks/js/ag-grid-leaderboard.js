// static/benchmarks/js/ag-grid-leaderboard.js
window.globalGridApi = null;
window.globalColumnApi = null;

// ModelCellRenderer
function ModelCellRenderer() {}
ModelCellRenderer.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'model-cell';
  const a = document.createElement('a');
  a.href = `/model/vision/${params.value.id}`;
  a.textContent = params.value.name;
  this.eGui.appendChild(a);

  // add submitter
  if (params.value.submitter) {
    const contributor = document.createElement('div');
    contributor.className = 'model-submitter';
    contributor.textContent = params.value.submitter;
    this.eGui.appendChild(contributor);
  }
};
ModelCellRenderer.prototype.getGui = function() {
  return this.eGui;
};

// Model Comparator for sorting models by name
function modelComparator(a, b) {
  // Both are objects like: { id, name, submitter }
  const nameA = a?.name?.toLowerCase() || '';
  const nameB = b?.name?.toLowerCase() || '';
  return nameA.localeCompare(nameB);
}

function LeafHeaderComponent() {}
LeafHeaderComponent.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'leaf-header';

  const label = document.createElement('span');
  label.className = 'leaf-header-label';
  label.textContent = params.displayName || params.colDef.headerName;

  // Add a tooltip for full text
  label.title = label.textContent;

  this.eGui.appendChild(label);

  // Click on pill to sort
  this.eGui.addEventListener('click', (event) => {
    if (event.target.closest('.expand-toggle')) return;

    const column = params.column;
    const colId = column.getColId();
    const currentSort = column.getSort();
    const nextSort = currentSort === 'asc' ? 'desc' : (currentSort === 'desc' ? null : 'asc');

    // AG Grid 33 approach - use applyColumnState which is available
    if (params.api && typeof params.api.applyColumnState === 'function') {
      params.api.applyColumnState({
        state: [{ colId, sort: nextSort }],
        defaultState: { sort: null }
      });
    } else {
      console.warn('applyColumnState method not available');
    }
  });
};
LeafHeaderComponent.prototype.getGui = function() {
  return this.eGui;
};

// ScoreCellRenderer
function ScoreCellRenderer() {}
ScoreCellRenderer.prototype.init = function(params) {
  // grab the raw object off your row
  const field = params.colDef.field;
  const cellObj = params.data[field] || {};

  // now unwrap
  let display = 'X';
  if (cellObj.value != null && cellObj.value !== '' && !isNaN(Number(cellObj.value))) {
    display = Number(cellObj.value).toFixed(2);
  }
  const CELL_ALPHA = 0.75;
  let bg = '#e0e1e2';
  if (cellObj.color) {
    const m = cellObj.color.match(/rgba?\([^)]*\)/);
    if (m) {
      const colorStr = m[0];
      if (colorStr.startsWith('rgba(')) {
        bg = colorStr.replace(/,\s*[\d.]+\)$/, `, ${CELL_ALPHA})`);
      } else if (colorStr.startsWith('rgb(')) {
        bg = colorStr.replace('rgb(', 'rgba(').replace(')', `, ${CELL_ALPHA})`);
      } else {
        bg = colorStr;
      }
    }
  }

  // build pill
  this.eGui = document.createElement('div');
  this.eGui.className = 'score-pill-container';
  const pill = document.createElement('div');
  pill.className = 'score-pill';
  pill.textContent = display;
  pill.style.backgroundColor = bg;
  this.eGui.appendChild(pill);
};
ScoreCellRenderer.prototype.getGui = function() {
  return this.eGui;
};

// ExpandableHeaderComponent
function ExpandableHeaderComponent() {}
ExpandableHeaderComponent.prototype.init = function(params) {
  this.params = params;

  const colDef = params.column?.userProvidedColDef || params.column?.colDef || {};
  const benchmarkId = colDef.benchmarkId || colDef.field || colDef.headerName;
  const nameMap = {
    average_vision_v0: 'Global Score',
    neural_vision_v0: 'Neural',
    behavior_vision_v0: 'Behavior',
    engineering_vision_v0: 'Engineering'
  };
  const displayName = nameMap[benchmarkId] || params.displayName || benchmarkId;

  this.eGui = document.createElement('div');
  const type = benchmarkId.split('_')[0];
  this.eGui.className = `expandable-header ${type}`;
  this.eGui.style.display = 'flex';
  this.eGui.style.alignItems = 'center';

  const labelContainer = document.createElement('div');
  labelContainer.className = 'expandable-header-label-container';

  // Create the label
  const title = document.createElement('span');
  title.className = 'expandable-header-label';
  title.textContent = displayName;
  title.title = displayName;

  labelContainer.appendChild(title);
  this.eGui.appendChild(labelContainer);

  if (!benchmarkId || !params.api?.getAllGridColumns) return;
  const allCols = params.api.getAllGridColumns();

  const benchmarkFieldBase = colDef.field?.split('_v')[0];

  function getDirectChildren(parentField) {
    const parentBase = parentField.split('_v')[0];

    return allCols.filter(col => {
      const ctx = col.getColDef()?.context || {};
      const childParent = ctx.parentField;
      if (!childParent) return false;

      const childBase = childParent.split('_v')[0];
      return childBase === parentBase;
    });
  }

  function getAllDescendants(parentField) {
    const directChildren = getDirectChildren(parentField);
    let descendants = [...directChildren];
    for (const child of directChildren) {
      const childField = child.getColDef()?.field;
      if (childField) {
        descendants.push(...getAllDescendants(childField));
      }
    }
    return descendants;
  }

  const childCols = getAllDescendants(colDef.field);

  // 2. Only leaf-level descendants for the badge
  function getLeafFields(parentField) {
    const parentBase = parentField.split('_v')[0];

    const directChildren = allCols.filter(col => {
      const ctx = col.getColDef()?.context || {};
      const childParent = ctx.parentField;
      const childBase = childParent?.split('_v')[0];
      const isDirect = childBase === parentBase;
      return isDirect;
    });

    if (directChildren.length === 0) {
      return [parentField];
    }

    return directChildren.flatMap(child => {
      const field = child.getColDef()?.field;
      return field ? getLeafFields(field) : [];
    });
  }

  const leafFields = getLeafFields(colDef.field);

  // Show count badge for number of leaf benchmarks
  if (leafFields.length > 0) {
    const count = document.createElement('span');
    count.className = 'benchmark-count';
    count.textContent = leafFields.length;
    this.eGui.appendChild(count);
  }

  // Click on pill to sort
  this.eGui.addEventListener('click', (event) => {
    if (event.target.closest('.expand-toggle')) return;

    const column = params.column;
    const colId = column.getColId();
    const currentSort = column.getSort();
    const nextSort = currentSort === 'asc' ? 'desc' : (currentSort === 'desc' ? null : 'asc');

    if (params.api && typeof params.api.applyColumnState === 'function') {
      params.api.applyColumnState({
        state: [{ colId, sort: nextSort }],
        defaultState: { sort: null }
      });
    } else {
      console.warn('applyColumnState method not available');
    }
  });

  // Don't show toggle for global score
  if (benchmarkId?.startsWith('average_')) return;

  // Add toggle if children exist
  const directChildren = getDirectChildren(colDef.field);
  if (directChildren.length > 0) {
    const toggle = document.createElement('span');
    toggle.className = 'expand-toggle';
    toggle.textContent = '▾';
    toggle.style.cursor = 'pointer';
    toggle.style.marginLeft = '4px';
    this.eGui.appendChild(toggle);

    // Click on toggle to open up children
    toggle.addEventListener('click', e => {
      e.stopPropagation();

      // Only get direct children for toggling
      const directChildren = getDirectChildren(colDef.field);

      const shouldShow = directChildren.some(c => !c.isVisible());
      const colIds = shouldShow
        ? directChildren.map(c => c.getColId())  // on expand: show only direct children
        : getAllDescendants(colDef.field).map(c => c.getColId());  // on collapse: hide all descendants

      params.api.setColumnsVisible(colIds, shouldShow);

      if (shouldShow) {
        const allCols = params.api.getAllGridColumns();
        const parentIndex = allCols.findIndex(col => col.getColId() === colDef.field);
        if (parentIndex !== -1) {
          const insertIndex = parentIndex + 1;
          params.api.moveColumns(colIds, insertIndex);
        }
      }

      toggle.textContent = shouldShow ? '▴' : '▾';
    });
  }
};
ExpandableHeaderComponent.prototype.getGui = function() {
  return this.eGui;
};

function renderBenchmarkTree(container, tree) {
  const ul = document.createElement('ul');
  ul.classList.add('benchmark-tree');

  tree.forEach(node => {
    const li = document.createElement('li');
    li.classList.add('benchmark-node');

    const header = document.createElement('div');
    header.classList.add('tree-node-header');

    // Checkbox
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = node.id;
    checkbox.checked = true;
    checkbox.checked = node.id !== 'engineering_vision_v0';  // doesn't factor into global so start unchecked

    checkbox.addEventListener('change', (e) => {
      const isChecked = e.target.checked;

      if (!window.filteredOutBenchmarks) window.filteredOutBenchmarks = new Set();

      // Function to update exclusions based on tree state
      function updateExclusions() {
        // Clear current exclusions
        window.filteredOutBenchmarks.clear();

        // Find all unchecked checkboxes
        const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
        allCheckboxes.forEach(cb => {
          if (!cb.checked) {
            window.filteredOutBenchmarks.add(cb.value);
          }
        });
      }

      // Toggle this checkbox and its children
      function toggleChildrenSilently(element, checked) {
        const childCheckboxes = element.querySelectorAll('input[type="checkbox"]');
        childCheckboxes.forEach(childCb => {
          if (childCb !== checkbox) {
            childCb.checked = checked;
          }
        });
      }

      toggleChildrenSilently(li, isChecked);

      // Update exclusions based on current tree state
      updateExclusions();

      // Update filtered scores and refresh grid
      updateFilteredScores(window.originalRowData);
      toggleFilteredScoreColumn(window.globalGridApi);
    });

    const label = document.createElement('label');
    label.appendChild(checkbox);
    label.append(` ${node.label}`);

    // Expand/Collapse toggle
    let toggle = null;
    if (node.children?.length) {
      toggle = document.createElement('span');
      toggle.classList.add('tree-toggle');
      toggle.textContent = '▶';  // collapsed state
      li.classList.add('collapsed');  // start collapsed

      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        li.classList.toggle('collapsed');
        toggle.textContent = li.classList.contains('collapsed') ? '▶' : '▼';
      });

      header.appendChild(toggle);
    } else {
      const spacer = document.createElement('span');
      spacer.classList.add('tree-toggle');
      spacer.textContent = ' ';  // for alignment
      header.appendChild(spacer);
    }

    header.appendChild(label);
    li.appendChild(header);

    // Recurse if needed
    if (node.children?.length) {
      renderBenchmarkTree(li, node.children);
    }

    ul.appendChild(li);
  });

  container.appendChild(ul);
}

function addResetFiltersButton() {
  const filterPanel = document.getElementById('benchmarkFilterPanel');
  if (!filterPanel) return;

  // Check if button already exists
  if (document.getElementById('resetFiltersBtn')) return;

  const resetBtn = document.createElement('button');
  resetBtn.id = 'resetFiltersBtn';
  resetBtn.textContent = 'Reset All Filters';
  resetBtn.style.marginBottom = '10px';
  resetBtn.style.padding = '8px 16px';
  resetBtn.style.backgroundColor = '#007bff';
  resetBtn.style.color = 'white';
  resetBtn.style.border = 'none';
  resetBtn.style.borderRadius = '4px';
  resetBtn.style.cursor = 'pointer';

  resetBtn.addEventListener('click', () => {
    // Clear all filters
    window.filteredOutBenchmarks = new Set();

    // Check all checkboxes
    const checkboxes = filterPanel.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = true);

    // Update scores and grid
    updateFilteredScores(window.originalRowData);
    toggleFilteredScoreColumn(window.globalGridApi);
  });

  // Insert button at the top of the filter panel
  filterPanel.insertBefore(resetBtn, filterPanel.firstChild);
}

function updateFilteredScores(rowData) {
  // Capture the excluded state once at the start
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  console.log('🔍 Excluded set when neural unchecked but V1 checked:', [...excludedBenchmarks]);


  // Build hierarchy map from the benchmark tree
  function buildHierarchyFromTree(tree, hierarchyMap = new Map()) {
    tree.forEach(node => {
      const children = node.children ? node.children.map(child => child.id) : [];
      hierarchyMap.set(node.id, children);
      if (node.children && node.children.length > 0) {
        buildHierarchyFromTree(node.children, hierarchyMap);
      }
    });
    return hierarchyMap;
  }

  const hierarchyMap = window.benchmarkTree
    ? buildHierarchyFromTree(window.benchmarkTree)
    : new Map();

  const filteredScores = [];
  rowData.forEach((row, rowIndex) => {
    // Use the captured excluded set, not the global one

    function calculateHierarchicalAverage(parentField) {
      const children = hierarchyMap.get(parentField) || [];

      if (children.length === 0) {
        // LEAF NODE: Check exclusion here
        if (excludedBenchmarks.has(parentField)) {
          return null;
        }

        const obj = row[parentField];
        if (obj && typeof obj === 'object' && 'value' in obj) {
          const val = obj.value;
          if (val === 'X' || val === '' || val === null || val === undefined) {
            return 0; // Treat X as 0
          }
          const numVal = typeof val === 'string' ? parseFloat(val) : val;
          return !isNaN(numVal) ? numVal : 0;
        }
        return 0;
      } else {
        // PARENT NODE: Don't check exclusion, always process children
        const childValues = children
          .map(child => calculateHierarchicalAverage(child))
          .filter(val => val !== null);

        if (childValues.length === 0) {
          return null;
        } else if (childValues.length === children.length) {
          // ALL children included - use pre-calculated value
          const obj = row[parentField];
          if (obj && typeof obj === 'object' && 'value' in obj) {
            const val = obj.value;
            if (val !== null && val !== undefined && val !== '' && val !== 'X') {
              const numVal = typeof val === 'string' ? parseFloat(val) : val;
              return !isNaN(numVal) ? numVal : null;
            }
          }
          // Fall back to calculating from children
          return childValues.reduce((a, b) => a + b, 0) / childValues.length;
        } else {
          // PARTIAL inclusion - calculate from included children
          return childValues.reduce((a, b) => a + b, 0) / childValues.length;
        }
      }
    }

    // Calculate filtered score
    const topLevelCategories = ['neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0'];
    const categoryAverages = topLevelCategories
      .map(category => calculateHierarchicalAverage(category))
      .filter(val => val !== null);

    const mean = categoryAverages.length > 0
      ? categoryAverages.reduce((a, b) => a + b, 0) / categoryAverages.length
      : null;

    // Store scores for color calculation
    if (mean !== null) {
      filteredScores.push(mean);
    }
    row._tempFilteredScore = mean;
  });

  // Calculate min and max for color scaling
  const minScore = filteredScores.length > 0 ? Math.min(...filteredScores) : 0;
  const maxScore = filteredScores.length > 0 ? Math.max(...filteredScores) : 1;
  const scoreRange = maxScore - minScore;

  // Second pass: assign colors based on min/max
  rowData.forEach((row) => {
    const mean = row._tempFilteredScore;
    delete row._tempFilteredScore; // Clean up temp property

    if (mean !== null) {
      // Calculate intensity (0 to 1, where 1 is highest score)
      const intensity = scoreRange > 0 ? (mean - minScore) / scoreRange : 0.5;

      // Create blue color with varying intensity
      const baseBlue = 255;
      const green = Math.round(173 + (105 * (1 - intensity))); // 150-255
      const red = Math.round(216 * (1 - intensity)); // 0-100

      const color = `rgba(${red}, ${green}, ${baseBlue}, 0.6)`;

      row.filtered_score = {
        value: parseFloat(mean.toFixed(3)),
        color: color
      };
    } else {
      row.filtered_score = {
        value: 'X',
        color: '#e0e1e2'
      };
    }
  });

  if (window.globalGridApi) {
    window.globalGridApi.refreshCells({
      columns: ['filtered_score'],
      force: true
    });
  }
}

function toggleFilteredScoreColumn(gridApi) {
  if (!gridApi) return;

  const hasFilters = window.filteredOutBenchmarks && window.filteredOutBenchmarks.size > 0;

  if (hasFilters) {
    // Show filtered score, hide global score
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: false },
        { colId: 'average_vision_v0', hide: true }
      ]
    });
  } else {
    // Hide filtered score, show global score
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: true },
        { colId: 'average_vision_v0', hide: false }
      ]
    });
  }
}

function initializeGrid(rowData, columnDefs, benchmarkGroups) {
  window.originalRowData = rowData;

  // Initialize filtered scores (will be all the same as global initially)
  updateFilteredScores(rowData);

  columnDefs.forEach(col => {
    col.colId = col.field;

    // Explicitly make benchmark columns sortable
    if (
      col.headerComponent === 'expandableHeaderComponent' ||
      col.headerComponent === 'leafComponent'
    ) {
      col.sortable = true;
    }

    // Set up model column for searching and sorting
    if (col.field === 'model') {
      col.getQuickFilterText = params => {
        const model = params.data.model;
        if (!model || typeof model !== 'object') {
          console.warn('⚠️ model object missing or malformed:', model);
          return '';
        }
        const name = model.name || '';
        const submitter = model.submitter || '';
        return `${name} ${submitter}`.toLowerCase();
      };
      col.comparator = modelComparator;
    } else {
      col.getQuickFilterText = () => '';
    }

    // Set up score columns
    if (col.cellRenderer === 'scoreCellRenderer') {
      col.cellDataType = 'object';
      col.valueFormatter = params => {
        const v = params.value;
        return (v && typeof v === 'object' && 'value' in v) ? v.value : v;
      };

      col.comparator = (valueA, valueB, nodeA, nodeB, isDescending) => {
        const objA = valueA && typeof valueA === 'object' ? valueA : {};
        const objB = valueB && typeof valueB === 'object' ? valueB : {};

        const valA = 'value' in objA ? objA.value : valueA;
        const valB = 'value' in objB ? objB.value : valueB;

        const isMissingA = valA == null || valA === '' || valA === 'X';
        const isMissingB = valB == null || valB === '' || valB === 'X';

        const MISSING_VALUE = Number.NEGATIVE_INFINITY;

        const numA = isMissingA ? MISSING_VALUE : parseFloat(valA);
        const numB = isMissingB ? MISSING_VALUE : parseFloat(valB);

        const isNanA = isNaN(numA) && !isMissingA;
        const isNanB = isNaN(numB) && !isMissingB;

        if (isNanA && isNanB) return 0;
        if (isNanA) return -1;
        if (isNanB) return 1;

        return numA - numB;
      };
    }

    if (col.headerComponent === 'expandableHeaderComponent') {
      col.headerComponentParams = {
        benchmarkId: col.context?.benchmarkId || null
      };
    }
  });

  // Add the filtered score column
  const filteredScoreColumn = {
    headerName: 'Filtered Score',
    field: 'filtered_score',
    colId: 'filtered_score',
    hide: true,  // start hidden
    pinned: 'left',
    width: 150,
    cellRenderer: 'scoreCellRenderer',
    cellDataType: 'object',
    sortable: true,
    valueFormatter: params => {
      const v = params.value;
      return v && typeof v === 'object' && 'value' in v ? v.value : v;
    },
    headerClass: 'centered-header',
    comparator: (valueA, valueB) => {
      const objA = valueA && typeof valueA === 'object' ? valueA : {};
      const objB = valueB && typeof valueB === 'object' ? valueB : {};

      const valA = 'value' in objA ? objA.value : valueA;
      const valB = 'value' in objB ? objB.value : valueB;

      const isMissingA = valA == null || valA === '' || valA === 'X';
      const isMissingB = valB == null || valB === '' || valB === 'X';

      const numA = isMissingA ? Number.NEGATIVE_INFINITY : parseFloat(valA);
      const numB = isMissingB ? Number.NEGATIVE_INFINITY : parseFloat(valB);

      return numA - numB;
    }
  };

  // Insert filtered score column after the model column
  const modelColumnIndex = columnDefs.findIndex(col => col.field === 'model');
  if (modelColumnIndex !== -1) {
    columnDefs.splice(modelColumnIndex + 1, 0, filteredScoreColumn);
  } else {
    columnDefs.push(filteredScoreColumn);
  }

  const gridOptions = {
    rowData,
    columnDefs,
    headerHeight: 60,
    rowHeight: 60,
    components: {
      modelCellRenderer: ModelCellRenderer,
      scoreCellRenderer: ScoreCellRenderer,
      expandableHeaderComponent: ExpandableHeaderComponent,
      leafComponent: LeafHeaderComponent,
    },
    suppressFieldDotNotation: true,
    defaultColDef: {
      sortable: true,
      resizable: false,
      valueFormatter: params => {
        const v = params.value;
        return (v != null && typeof v === 'object' && 'value' in v)
          ? v.value
          : v;
      }
    },
    onGridReady: params => {
      window.globalGridApi = params.api;
      params.api.resetRowHeights();
    }
  };

  const eGridDiv = document.getElementById('leaderboardGrid');
  if (!eGridDiv) {
    console.error('Could not find #leaderboardGrid');
    return;
  }

  let gridApi;

  if (window.agGrid && typeof agGrid.createGrid === 'function') {
    gridApi = agGrid.createGrid(eGridDiv, gridOptions);
    window.globalGridApi = gridApi;
    console.log('Grid API initialized (createGrid):', !!gridApi);
  } else if (window.agGrid && typeof agGrid.Grid === 'function') {
    const grid = new agGrid.Grid(eGridDiv, gridOptions);
    gridApi = gridOptions.api;
    window.globalGridApi = gridApi;
    console.log('Grid API initialized (Grid constructor):', !!gridApi);
  } else {
    console.error('AG Grid not found on window.agGrid');
  }

  if (gridApi) {
    // Connect the search input
    const searchInput = document.getElementById('modelSearchInput');
    if (searchInput) {
      // Remove any existing listeners
      const newInput = searchInput.cloneNode(true);
      searchInput.parentNode.replaceChild(newInput, searchInput);

      newInput.addEventListener('input', function () {
        const searchText = this.value;
        if (typeof gridApi.setGridOption === 'function') {
          gridApi.setGridOption('quickFilterText', searchText);
          gridApi.refreshClientSideRowModel('filter');
        } else {
          console.warn('setGridOption not available on gridApi');
        }
      });
    } else {
      console.error('Search input not found');
    }
  } else {
    console.error('Grid API not available after initialization');
  }
}

// Make functions available globally
window.addResetFiltersButton = addResetFiltersButton;
window.initializeGrid = initializeGrid;