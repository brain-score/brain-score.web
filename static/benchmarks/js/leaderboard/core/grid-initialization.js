// Grid initialization and configuration

// Set initial column visibility state
function setInitialColumnState() {
  if (!window.globalGridApi) return;
  
  const allColumns = window.globalGridApi.getAllGridColumns();
  const initialColumnState = [];
  
  // Initialize expansion state - all columns start collapsed
  window.columnExpansionState.clear();
  
  allColumns.forEach(column => {
    const colId = column.getColId();
    
    // Always show model, rank, group_status
    if (['model', 'rank', 'group_status'].includes(colId)) {
      initialColumnState.push({ colId: colId, hide: false });
      return;
    }
    
    // Hide filtered_score initially
    if (colId === 'filtered_score') {
      initialColumnState.push({ colId: colId, hide: true });
      return;
    }
    
    // Show only top-level benchmark categories initially
    const topLevelCategories = ['average_vision_v0', 'neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0'];
    const shouldShow = topLevelCategories.includes(colId);
    
    initialColumnState.push({ colId: colId, hide: !shouldShow });
    
    // Initialize expansion state - ALL columns start collapsed (including top-level)
    window.columnExpansionState.set(colId, false);
  });
  
  // Apply initial column state
  window.globalGridApi.applyColumnState({
    state: initialColumnState
  });
}

// Main grid initialization function
function initializeGrid(rowData, columnDefs, benchmarkGroups) {
  window.originalRowData = rowData || [];

  // Initialize filtered scores
  if (typeof window.LeaderboardFilterCoordinator?.updateFilteredScores === 'function') {
    window.LeaderboardFilterCoordinator.updateFilteredScores(rowData || []);
  } else if (typeof updateFilteredScores === 'function') {
    updateFilteredScores(rowData || []);
  }
  
  // Handle empty data gracefully
  if (!rowData || rowData.length === 0) {
    console.warn('No row data provided - creating empty grid');
    rowData = [];
  }

  if (!columnDefs || columnDefs.length === 0) {
    console.warn('No column definitions provided - creating basic columns');
    columnDefs = [
      { headerName: 'Model', field: 'model', width: 200 },
      { headerName: 'No Data', field: 'no_data', width: 200 }
    ];
  }

  // Compute benchmark min/max stats for client-side color computation
  if (window.LeaderboardColorUtils?.computeBenchmarkMinMax) {
    window.benchmarkStats = window.LeaderboardColorUtils.computeBenchmarkMinMax(rowData, columnDefs);
  } else {
    console.warn('LeaderboardColorUtils.computeBenchmarkMinMax not available - colors may not display correctly');
    window.benchmarkStats = {};
  }

  columnDefs.forEach(col => {
    col.colId = col.field;

    if (col.field === 'model') {
      col.comparator = window.LeaderboardRenderers?.modelComparator || null;
    }

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

  // Add the group status column
  const groupStatusColumn = window.LeaderboardRenderers?.createGroupStatusColumn ?
    window.LeaderboardRenderers.createGroupStatusColumn() :
    { headerName: 'Group', field: 'group_status', width: 80 };

  // Add the filtered score column
  const filteredScoreColumn = {
    headerName: 'Filtered Score',
    field: 'filtered_score',
    colId: 'filtered_score',
    hide: true,
    lockPosition: true,
    suppressMovable: true,
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

  // Extract rank and model columns, then reconstruct with correct order: Rank, Model, Status
  const rankColumnIndex = columnDefs.findIndex(col => col.field === 'rank');
  const modelColumnIndex = columnDefs.findIndex(col => col.field === 'model');
  
  // Remove rank and model from their current positions (remove higher index first to preserve indices)
  let rankColumn = null;
  let modelColumn = null;
  
  if (rankColumnIndex !== -1 && modelColumnIndex !== -1) {
    // Remove in reverse order of indices to preserve positions
    if (rankColumnIndex > modelColumnIndex) {
      rankColumn = columnDefs.splice(rankColumnIndex, 1)[0];
      modelColumn = columnDefs.splice(modelColumnIndex, 1)[0];
    } else {
      modelColumn = columnDefs.splice(modelColumnIndex, 1)[0];
      rankColumn = columnDefs.splice(rankColumnIndex, 1)[0];
    }
    
    // Insert pinned columns at the beginning in correct order: Rank, Model, Status, Filtered Score
    columnDefs.unshift(filteredScoreColumn);
    columnDefs.unshift(groupStatusColumn);
    columnDefs.unshift(modelColumn);
    columnDefs.unshift(rankColumn);
  } else {
    // Fallback: just append the new columns
    columnDefs.push(groupStatusColumn, filteredScoreColumn);
  }

  const gridOptions = {
    rowData,
    columnDefs,
    headerHeight: 60,
    rowHeight: 60,
    tooltipShowDelay: 500,
    components: {
      modelCellRenderer: window.LeaderboardRenderers?.ModelCellRenderer,
      scoreCellRenderer: window.LeaderboardRenderers?.ScoreCellRenderer,
      groupStatusCellRenderer: window.LeaderboardRenderers?.GroupStatusCellRenderer,
      publicToggleCellRenderer: window.LeaderboardRenderers?.PublicToggleCellRenderer,
      expandableHeaderComponent: window.LeaderboardHeaderComponents?.ExpandableHeaderComponent,
      leafComponent: window.LeaderboardHeaderComponents?.LeafHeaderComponent,
    },
    suppressFieldDotNotation: true,

    // External filter for search only
    isExternalFilterPresent: () => {
      return window.currentSearchQuery !== null;
    },
    doesExternalFilterPass: (node) => {
      // Check search filter only
      if (window.currentSearchQuery) {
        if (!window.LeaderboardSearch?.getSearchableText || !window.LeaderboardSearch?.executeSearchQuery) {
          return false;
        }
        const searchableText = window.LeaderboardSearch.getSearchableText(node.data);
        if (!window.LeaderboardSearch.executeSearchQuery(window.currentSearchQuery, searchableText)) {
          return false;
        }
      }
      
      return true;
    },

    sortingOrder: ['desc', 'asc', null],
    defaultColDef: {
      sortable: true,
      resizable: false,
      unSortIcon: true,
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

      setInitialColumnState();

      // Set column visibility
      params.api.applyColumnState({
        state: [
          { colId: 'group_status', hide: false },
          { colId: 'filtered_score', hide: true },
          { colId: 'average_vision_v0', hide: false, sort: 'desc' }
        ]
      });

      // Fit grid to remaining viewport height
      resizeGridToViewport();
      window.addEventListener('resize', resizeGridToViewport);

      // Complete loading animation when grid is fully rendered,
      // then init the top scrollbar once AG Grid has settled.
      setTimeout(() => {
        if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.complete) {
          LoadingAnimation.complete();
        } else if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.hide) {
          LoadingAnimation.hide();
        }
        initTopScrollbar();
      }, 100);
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
  } else if (window.agGrid && typeof agGrid.Grid === 'function') {
    const grid = new agGrid.Grid(eGridDiv, gridOptions);
    gridApi = gridOptions.api;
    window.globalGridApi = gridApi;
  } else {
    console.error('AG Grid not found on window.agGrid');
  }

  // Search functionality is handled by the LeaderboardSearch module
  if (typeof window.LeaderboardSearch?.setupSearchHandlers === 'function') {
    window.LeaderboardSearch.setupSearchHandlers();
  }
}

// Sync a top scrollbar div with AG Grid's internal horizontal scroll.
// AG Grid uses a fake scrollbar (.ag-body-horizontal-scroll-viewport) for
// horizontal scrolling -- .ag-center-cols-viewport has overflow:hidden.
// We sync with the fake scrollbar and align position with the center viewport.
function initTopScrollbar(attempt) {
  attempt = attempt || 0;

  var topScrollbar = document.getElementById('topScrollbar');
  var topScrollbarInner = document.getElementById('topScrollbarInner');
  if (!topScrollbar || !topScrollbarInner) return;

  var gridEl = document.getElementById('leaderboardGrid');
  if (!gridEl) return;

  var agScrollViewport = gridEl.querySelector('.ag-body-horizontal-scroll-viewport');
  var agScrollContainer = gridEl.querySelector('.ag-body-horizontal-scroll-container');
  var centerViewport = gridEl.querySelector('.ag-center-cols-viewport');

  if (!agScrollViewport || !agScrollContainer || !centerViewport) {
    if (attempt < 20) {
      setTimeout(function () { initTopScrollbar(attempt + 1); }, 200);
    }
    return;
  }

  var syncing = false;

  function syncWidths() {
    var scrollWidth = agScrollContainer.scrollWidth;
    var clientWidth = agScrollViewport.clientWidth;
    topScrollbarInner.style.width = scrollWidth + 'px';
    topScrollbar.style.display = scrollWidth > clientWidth ? '' : 'none';

    // Align with the center viewport (offset past pinned columns)
    var gridRect = gridEl.getBoundingClientRect();
    var vpRect = centerViewport.getBoundingClientRect();
    topScrollbar.style.marginLeft = (vpRect.left - gridRect.left) + 'px';
    topScrollbar.style.width = vpRect.width + 'px';
  }

  syncWidths();

  topScrollbar.addEventListener('scroll', function () {
    if (syncing) return;
    syncing = true;
    agScrollViewport.scrollLeft = topScrollbar.scrollLeft;
    requestAnimationFrame(function () { syncing = false; });
  });

  agScrollViewport.addEventListener('scroll', function () {
    if (syncing) return;
    syncing = true;
    topScrollbar.scrollLeft = agScrollViewport.scrollLeft;
    requestAnimationFrame(function () { syncing = false; });
  });

  // Re-sync widths when columns change (expand/collapse)
  var mutObs = new MutationObserver(syncWidths);
  mutObs.observe(agScrollContainer, { attributes: true, childList: true, subtree: true });

  // Re-sync when the grid itself resizes (sidebar toggle, window resize, etc.)
  var resizeObs = new ResizeObserver(syncWidths);
  resizeObs.observe(gridEl);

  window.addEventListener('resize', syncWidths);

  // Expose syncWidths so resizeGridToViewport can re-sync after layout changes
  window._topScrollbarSyncWidths = syncWidths;
}

// Size the grid to fill the remaining viewport height
function resizeGridToViewport() {
  var grid = document.getElementById('leaderboardGrid');
  if (!grid) return;
  var top = grid.getBoundingClientRect().top;
  var available = window.innerHeight - top - 16;
  var height = Math.max(400, available);
  grid.style.height = height + 'px';

  // Match filters panel height to grid in sidebar mode
  var container = grid.closest('.leaderboard-container');
  var panel = document.getElementById('advancedFiltersPanel');
  if (panel) {
    if (container && container.classList.contains('sidebar-mode')) {
      panel.style.maxHeight = height + 'px';
    } else {
      panel.style.maxHeight = '';
    }
  }

  // Tell AG Grid to recalculate after container height change
  if (window.globalGridApi) {
    window.globalGridApi.resetRowHeights();
  }

  // Re-sync top scrollbar after grid resize settles
  // Use double-rAF to ensure AG Grid has finished its layout pass
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      if (window._topScrollbarSyncWidths) {
        window._topScrollbarSyncWidths();
      } else {
        initTopScrollbar();
      }
    });
  });
}

// Export functions for use by other modules
window.LeaderboardGridInitialization = {
  initializeGrid,
  setInitialColumnState
};

// Make main function globally available
window.initializeGrid = initializeGrid;
