// static/benchmarks/js/ag-grid-leaderboard.js
window.globalGridApi = null;
window.globalColumnApi = null;

// Global filter state for model properties
window.activeFilters = {
  architecture: [],
  model_family: [],
  training_dataset: [],
  task_specialization: [],
  max_param_count: null,
  max_model_size: null,
  runnable_only: false,
  benchmark_regions: [],
  benchmark_species: [],
  benchmark_tasks: [],
  public_data_only: false,
  wayback_min_date: null,
  wayback_max_date: null
};

// Global state for tracking column expansion
window.columnExpansionState = new Map();

// Global state for filtered out benchmarks
window.filteredOutBenchmarks = new Set();

// =====================================
// CELL RENDERERS
// =====================================

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

// =====================================
// RUNNABLE STATUS FUNCTIONALITY
// =====================================

// RunnableStatusCellRenderer - displays colored status circles with tooltips
function RunnableStatusCellRenderer() {}
RunnableStatusCellRenderer.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'runnable-status-cell';

  const runnable = params.data?.metadata?.runnable;
  const statusIcon = document.createElement('div');
  statusIcon.className = 'runnable-status-icon';

  if (runnable === true) {
    statusIcon.classList.add('runnable-green');
  } else if (runnable === false) {
    statusIcon.classList.add('runnable-red');
  } else {
    statusIcon.classList.add('runnable-grey');
  }

  this.eGui.appendChild(statusIcon);
};
RunnableStatusCellRenderer.prototype.getGui = function() {
  return this.eGui;
};

// Helper function to create runnable status column definition
function createRunnableStatusColumn() {
  return {
    headerName: '',
    field: 'runnable_status',
    colId: 'runnable_status',
    pinned: 'left',
    width: 80,
    cellRenderer: 'runnableStatusCellRenderer',
    sortable: true,
    filter: false,
    headerClass: 'centered-header',
    valueGetter: params => {
      const runnable = params.data?.metadata?.runnable;
      return runnable === true ? 2 : runnable === false ? 1 : 0; // For sorting: green > red > grey
    },
    tooltipValueGetter: params => {
      const runnable = params.data?.metadata?.runnable;
      if (runnable === true) {
        return 'Model code is functional and runnable';
      } else if (runnable === false) {
        return 'Model code has known issues or is non-functional';
      } else {
        return 'Model code status unknown';
      }
    }
  };
}

// Model Comparator for sorting models by name
function modelComparator(a, b) {
  // Both are objects like: { id, name, submitter }
  const nameA = a?.name?.toLowerCase() || '';
  const nameB = b?.name?.toLowerCase() || '';
  return nameA.localeCompare(nameB);
}

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
  const CELL_ALPHA = 0.85;
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


// Global search state - LOCAL VARIABLE like the original
window.currentSearchQuery = null;

// =====================================
// SEARCH FUNCTIONALITY
// =====================================

// Get searchable text from a row - EXACTLY like original
function getSearchableText(rowData) {
  const model = rowData.model || {};
  const searchFields = [
    model.name || '',
    model.submitter || ''
    // Future: Add metadata fields here when needed
    // rowData.metadata?.architecture || '', // Example: architecture: transformer
    // rowData.metadata?.model_family || ''
  ];

  return searchFields.join(' ').toLowerCase();
}

// Parse search query with logical operators (OR, AND, NOT) - EXACTLY like original
function parseSearchQuery(query) {
  if (!query.trim()) return null;

  // Split by OR first (lowest precedence)
  const orParts = query.toLowerCase().split(/\s+or\s+/);

  return {
    type: 'OR',
    parts: orParts.map(orPart => {
      // Split by AND (higher precedence than OR)
      const andParts = orPart.split(/\s+and\s+/);

      if (andParts.length === 1) {
        // Handle NOT for single terms (e.g., "NOT alexnet")
        const term = andParts[0].trim();
        if (term.startsWith('not ')) {
          return { type: 'NOT', term: term.substring(4).trim() };
        }
        return { type: 'TERM', term };
      }

      return {
        type: 'AND',
        parts: andParts.map(andPart => {
          const term = andPart.trim();
          if (term.startsWith('not ')) {
            return { type: 'NOT', term: term.substring(4).trim() };
          }
          return { type: 'TERM', term };
        })
      };
    })
  };
}

// Execute parsed search query against searchable text - EXACTLY like original
function executeSearchQuery(parsedQuery, searchableText) {
  if (!parsedQuery) return true;

  function evaluateNode(node) {
    switch (node.type) {
      case 'TERM':
        return searchableText.includes(node.term);
      case 'NOT':
        return !searchableText.includes(node.term);
      case 'AND':
        return node.parts.every(evaluateNode);
      case 'OR':
        return node.parts.some(evaluateNode);
      default:
        return false;
    }
  }

  return evaluateNode(parsedQuery);
}

// =====================================
// INITIALIZATION
// =====================================

function initializeGrid(rowData, columnDefs, benchmarkGroups) {
  window.originalRowData = rowData;

  // Initialize filtered scores (will be all the same as global initially)
  updateFilteredScores(rowData);

  columnDefs.forEach(col => {
    col.colId = col.field;

    // Columns are sortable by default via defaultColDef

    // Set up model column for sorting (search handled by external filter)
    if (col.field === 'model') {
      col.comparator = modelComparator;
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

  // Add the runnable status column
  const runnableStatusColumn = createRunnableStatusColumn();

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

  // Insert columns after the model column
  const modelColumnIndex = columnDefs.findIndex(col => col.field === 'model');
  if (modelColumnIndex !== -1) {
    columnDefs.splice(modelColumnIndex + 1, 0, runnableStatusColumn, filteredScoreColumn);
  } else {
    columnDefs.push(runnableStatusColumn, filteredScoreColumn);
  }

  const gridOptions = {
    rowData,
    columnDefs,
    headerHeight: 60,
    rowHeight: 60,
    tooltipShowDelay: 500, // Show tooltip after 0.5 seconds
    components: {
      // Core cell renderers
      modelCellRenderer: ModelCellRenderer,
      scoreCellRenderer: ScoreCellRenderer,

      // Runnable status functionality
      runnableStatusCellRenderer: RunnableStatusCellRenderer,

      // Header components will be loaded from modular files
      expandableHeaderComponent: window.LeaderboardHeaderComponents?.ExpandableHeaderComponent,
      leafComponent: window.LeaderboardHeaderComponents?.LeafHeaderComponent,
    },
    suppressFieldDotNotation: true,

    // External filter for logical search
    isExternalFilterPresent: () => {
      return window.currentSearchQuery !== null;
    },
    // If search query is present, filter the grid based on the search query
    doesExternalFilterPass: (node) => {
      if (!window.currentSearchQuery) return true;
      const searchableText = getSearchableText(node.data);
      return executeSearchQuery(window.currentSearchQuery, searchableText);
    },

    sortingOrder: ['desc', 'asc', null],  // Sort cycle: desc -> asc -> none
    defaultColDef: {
      sortable: true,
      resizable: false,
      unSortIcon: true,  // Show unsort icon for 3-state sorting
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

      // Set initial column visibility state
      setInitialColumnState();

      setTimeout(() => {
        initializeWaybackDateFilter();
        syncSliderWithDateInputs();
      }, 0);

      // Ensure filtered score column starts hidden (clean initial state) - EXACTLY like old file
      params.api.applyColumnState({
        state: [
          { colId: 'runnable_status', hide: false },
          { colId: 'filtered_score', hide: true },
          { colId: 'average_vision_v0', hide: false }
        ]
      });
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
    // Connect the search input with logical operators - EXACTLY like original
    const searchInput = document.getElementById('modelSearchInput');
    if (searchInput) {
      // Remove any existing listeners
      const newInput = searchInput.cloneNode(true);
      searchInput.parentNode.replaceChild(newInput, searchInput);

      newInput.addEventListener('input', function () {
        const searchText = this.value;

        // Parse search query with logical operators (OR, AND, NOT)
        window.currentSearchQuery = parseSearchQuery(searchText);

        // Use external filter for logical search
        if (typeof gridApi.onFilterChanged === 'function') {
          gridApi.onFilterChanged();
        } else {
          console.warn('onFilterChanged not available on gridApi');
        }
      });
    } else {
      console.error('Search input not found');
    }
  } else {
    console.error('Grid API not available after initialization');
  }
}

// Function to set initial column visibility state
function setInitialColumnState() {
  if (!window.globalGridApi) return;

  const allColumns = window.globalGridApi.getAllGridColumns();
  const initialColumnState = [];

  // Initialize expansion state - all columns start collapsed
  window.columnExpansionState.clear();

  allColumns.forEach(column => {
    const colId = column.getColId();

    // Always show these columns (including runnable status)
    if (['model', 'rank', 'runnable_status', 'filtered_score'].includes(colId)) {
      initialColumnState.push({ colId: colId, hide: false });
      return;
    }

    // Show top-level benchmark categories initially (including engineering)
    const topLevelCategories = ['average_vision_v0', 'neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0'];
    const shouldShow = topLevelCategories.includes(colId);

    initialColumnState.push({ colId: colId, hide: !shouldShow });

    // Initialize expansion state (all start collapsed)
    if (topLevelCategories.includes(colId)) {
      window.columnExpansionState.set(colId, false);
    }
  });

  // Apply initial column state
  window.globalGridApi.applyColumnState({
    state: initialColumnState
  });
}

// Placeholder functions that will delegate to modular components
function populateFilterDropdowns(filterOptions) {
  if (typeof window.LeaderboardModelFilters?.populateFilterDropdowns === 'function') {
    window.LeaderboardModelFilters.populateFilterDropdowns(filterOptions);
  }
}

function setupDropdownHandlers() {
  if (typeof window.LeaderboardModelFilters?.setupDropdownHandlers === 'function') {
    window.LeaderboardModelFilters.setupDropdownHandlers();
  }
}

function applyCombinedFilters(skipColumnToggle = false) {
  if (typeof window.LeaderboardFilterCoordinator?.applyCombinedFilters === 'function') {
    window.LeaderboardFilterCoordinator.applyCombinedFilters(skipColumnToggle);
  }
}

function resetAllFilters() {
  if (typeof window.LeaderboardFilterCoordinator?.resetAllFilters === 'function') {
    window.LeaderboardFilterCoordinator.resetAllFilters();
  }
}

function initializeDualHandleSliders() {
  if (typeof window.LeaderboardRangeFilters?.initializeDualHandleSliders === 'function') {
    window.LeaderboardRangeFilters.initializeDualHandleSliders();
  }
}

function formatDateInput(date) {
  if (!(date instanceof Date) || isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 10); // 'YYYY-MM-DD'
}

function initializeWaybackDateFilter() {
  const dateMinInput = document.getElementById('waybackDateMin');
  const dateMaxInput = document.getElementById('waybackDateMax');

  // Pre-fill inputs with default values from filterOptions
  if (window.filterOptions?.datetime_range) {
    const { min, max } = window.filterOptions.datetime_range;

    if (min) {
      dateMinInput.value = formatDateInput(new Date(min));
    }
    if (max) {
      dateMaxInput.value = formatDateInput(new Date(max));
    }
  }
  const handleDateChange = () => {
    setTimeout(() => {
      const dateMinInput = document.getElementById("waybackDateMin");
      const dateMaxInput = document.getElementById("waybackDateMax");

      // Debug logs
      console.log("Got inputs:", {
        dateMinInput,
        dateMaxInput,
      });

      if (!dateMinInput || !dateMaxInput) {
        console.error("Could not find one or both input elements.");
        return;
      }

      console.log("Raw input values:", {
        minValueAttr: dateMinInput.getAttribute("value"),
        maxValueAttr: dateMaxInput.getAttribute("value"),
        minInputValue: dateMinInput.value,
        maxInputValue: dateMaxInput.value,
      });

      const minRaw = dateMinInput?.value;
      const maxRaw = dateMaxInput?.value;

      console.log("Manual date input values:", { minRaw, maxRaw });

      const minDate = minRaw ? new Date(minRaw) : null;
      const maxDate = maxRaw ? new Date(maxRaw) : null;

      // Check validity
      if (!minRaw || !maxRaw || isNaN(minDate) || isNaN(maxDate)) {
        console.warn("One or both date inputs are empty or invalid. Skipping filter update.");
        return;
      }

      // Update global filters
      window.activeFilters.wayback_min_date = minDate;
      window.activeFilters.wayback_max_date = maxDate;

      console.log("Filter dates set:", { minDate, maxDate });

      applyCombinedFilters(); // Trigger grid refresh
    }, 0);
  };

  const dateMinInputLive = document.getElementById("waybackDateMin");
  const dateMaxInputLive = document.getElementById("waybackDateMax");

  // if (dateMinInputLive && dateMaxInputLive) {
  //   ["change"].forEach(event => {
  //     dateMinInputLive.addEventListener(event, handleDateChange);
  //     dateMaxInputLive.addEventListener(event, handleDateChange);
  //   });
  // } else {
  //   console.error("🚨 Date inputs not found in DOM when attaching listeners");
  // }
}

function syncSliderWithDateInputs() {
  const sliderMinHandle = document.querySelector('.slider-handle.handle-min');
  const sliderMaxHandle = document.querySelector('.slider-handle.handle-max');
  const dateMinInput = document.getElementById('waybackDateMin');
  const dateMaxInput = document.getElementById('waybackDateMax');

  if (!sliderMinHandle || !sliderMaxHandle || !dateMinInput || !dateMaxInput) return;

  const updateDatesFromSlider = () => {
    const minUnix = parseInt(sliderMinHandle.getAttribute('data-value'), 10);
    const maxUnix = parseInt(sliderMaxHandle.getAttribute('data-value'), 10);

    if (!isNaN(minUnix)) {
      const minDate = new Date(minUnix);  // JS timestamps in ms
      dateMinInput.value = minDate.toISOString().slice(0, 10);
    }

    if (!isNaN(maxUnix)) {
      const maxDate = new Date(maxUnix * 1000);
      dateMaxInput.value = maxDate.toISOString().slice(0, 10);
    }

    // Also update filters
    window.activeFilters.wayback_min_date = new Date(dateMinInput.value);
    window.activeFilters.wayback_max_date = new Date(dateMaxInput.value);
    applyCombinedFilters();
  };

  sliderMinHandle.addEventListener('mouseup', updateDatesFromSlider);
  sliderMaxHandle.addEventListener('mouseup', updateDatesFromSlider);
}

function onSliderChange() {
  const handleMin = document.querySelector('.slider-handle.handle-min');
  const handleMax = document.querySelector('.slider-handle.handle-max');

  const minUnix = parseInt(handleMin.dataset.value);
  const maxUnix = parseInt(handleMax.dataset.value);

  const minDate = new Date(minUnix * 1000);
  const maxDate = new Date(maxUnix * 1000);

  document.getElementById('waybackDateMin').value = formatDateInput(minDate);
  document.getElementById('waybackDateMax').value = formatDateInput(maxDate);

  window.activeFilters.wayback_min_date = minDate;
  window.activeFilters.wayback_max_date = maxDate;

  applyCombinedFilters();
}

function parseURLFilters() {
  if (typeof window.LeaderboardURLState?.parseURLFilters === 'function') {
    window.LeaderboardURLState.parseURLFilters();
  }
}

function updateURLFromFilters() {
  if (typeof window.LeaderboardURLState?.updateURLFromFilters === 'function') {
    window.LeaderboardURLState.updateURLFromFilters();
  }
}

function encodeBenchmarkFilters() {
  if (typeof window.LeaderboardURLState?.encodeBenchmarkFilters === 'function') {
    return window.LeaderboardURLState.encodeBenchmarkFilters();
  }
  return null;
}

function decodeBenchmarkFilters(encodedFilters) {
  if (typeof window.LeaderboardURLState?.decodeBenchmarkFilters === 'function') {
    return window.LeaderboardURLState.decodeBenchmarkFilters(encodedFilters);
  }
  return [];
}

function buildHierarchyFromTree(tree, hierarchyMap = new Map()) {
  if (typeof window.LeaderboardHeaderComponents?.buildHierarchyFromTree === 'function') {
    return window.LeaderboardHeaderComponents.buildHierarchyFromTree(tree, hierarchyMap);
  }
  // Fallback implementation
  tree.forEach(node => {
    const children = node.children ? node.children.map(child => child.id) : [];
    hierarchyMap.set(node.id, children);
    if (node.children && node.children.length > 0) {
      buildHierarchyFromTree(node.children, hierarchyMap);
    }
  });
  return hierarchyMap;
}

function updateColumnVisibility() {
  if (typeof window.LeaderboardHeaderComponents?.updateColumnVisibility === 'function') {
    window.LeaderboardHeaderComponents.updateColumnVisibility();
  }
}

function copyBibtexToClipboard() {
  if (typeof window.LeaderboardCitationExport?.copyBibtexToClipboard === 'function') {
    window.LeaderboardCitationExport.copyBibtexToClipboard();
  }
}

function updateAllCountBadges() {
  if (typeof window.LeaderboardHierarchyUtils?.updateAllCountBadges === 'function') {
    window.LeaderboardHierarchyUtils.updateAllCountBadges();
  }
}

function getFilteredLeafCount(parentField) {
  if (typeof window.LeaderboardHierarchyUtils?.getFilteredLeafCount === 'function') {
    return window.LeaderboardHierarchyUtils.getFilteredLeafCount(parentField);
  }
  return 0;
}

function updateFilteredScores(rowData) {
  if (typeof window.LeaderboardFilterCoordinator?.updateFilteredScores === 'function') {
    const updatedData = window.LeaderboardFilterCoordinator.updateFilteredScores(rowData);
    if (updatedData && window.globalGridApi) {
      window.globalGridApi.setGridOption('rowData', updatedData);
    }
    return updatedData;
  }
  return rowData;
}

function toggleFilteredScoreColumn(gridApi) {
  if (typeof window.LeaderboardFilterCoordinator?.toggleFilteredScoreColumn === 'function') {
    window.LeaderboardFilterCoordinator.toggleFilteredScoreColumn(gridApi);
  }
}

function setupBenchmarkCheckboxes(filterOptions) {
  if (typeof window.LeaderboardBenchmarkFilters?.setupBenchmarkCheckboxes === 'function') {
    window.LeaderboardBenchmarkFilters.setupBenchmarkCheckboxes(filterOptions);
  }
}

function renderBenchmarkTree(container, benchmarkTree) {
  if (typeof window.LeaderboardBenchmarkFilters?.renderBenchmarkTree === 'function') {
    window.LeaderboardBenchmarkFilters.renderBenchmarkTree(container, benchmarkTree);
  }
}

function getAllDescendantsFromHierarchy(parentId, hierarchyMap) {
  if (typeof window.LeaderboardHeaderComponents?.getAllDescendantsFromHierarchy === 'function') {
    return window.LeaderboardHeaderComponents.getAllDescendantsFromHierarchy(parentId, hierarchyMap);
  }
  return [];
}

// Make all functions available globally - EXACTLY like original monolithic file
window.initializeGrid = initializeGrid;
window.populateFilterDropdowns = populateFilterDropdowns;
window.setupDropdownHandlers = setupDropdownHandlers;
window.applyCombinedFilters = applyCombinedFilters;
window.resetAllFilters = resetAllFilters;
window.initializeDualHandleSliders = initializeDualHandleSliders;
window.parseURLFilters = parseURLFilters;
window.updateURLFromFilters = updateURLFromFilters;
window.encodeBenchmarkFilters = encodeBenchmarkFilters;
window.decodeBenchmarkFilters = decodeBenchmarkFilters;
window.buildHierarchyFromTree = buildHierarchyFromTree;
window.updateColumnVisibility = updateColumnVisibility;
window.setInitialColumnState = setInitialColumnState;
window.copyBibtexToClipboard = copyBibtexToClipboard;
window.updateAllCountBadges = updateAllCountBadges;
window.getFilteredLeafCount = getFilteredLeafCount;
window.updateFilteredScores = updateFilteredScores;
window.toggleFilteredScoreColumn = toggleFilteredScoreColumn;
window.setupBenchmarkCheckboxes = setupBenchmarkCheckboxes;
window.renderBenchmarkTree = renderBenchmarkTree;
window.getAllDescendantsFromHierarchy = getAllDescendantsFromHierarchy;
window.initializeWaybackDateFilter = initializeWaybackDateFilter;
window.initializeDualDateSlider = initializeDualDateSlider;



// Log successful module load
console.log('📦 Monolithic leaderboard file loaded successfully');
