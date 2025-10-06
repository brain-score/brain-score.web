// Header components for leaderboard grid

// Helper function to build hierarchy map from benchmark tree
function buildHierarchyFromTree(tree, hierarchyMap = new Map()) {
  tree.forEach(node => {
    const nodeId = node.id || node.identifier || node.field || node.name;
    const children = node.children ?
      node.children.map(child => child.id || child.identifier || child.field || child.name).filter(Boolean) :
      [];
    if (nodeId) {
      hierarchyMap.set(nodeId, children);
      if (node.children && node.children.length > 0) {
        buildHierarchyFromTree(node.children, hierarchyMap);
      }
    }
  });
  return hierarchyMap;
}

// Get all descendants recursively
function getAllDescendantsFromHierarchy(parentId, hierarchyMap) {
  const children = hierarchyMap.get(parentId) || [];
  let descendants = [...children];
  children.forEach(childId => {
    descendants.push(...getAllDescendantsFromHierarchy(childId, hierarchyMap));
  });
  return descendants;
}

// Shared utility to create and manage sort indicators
function createSortIndicator(params, element, fontSize = '12px') {
  const indicator = document.createElement('span');
  indicator.className = 'sort-indicator ag-icon';
  indicator.style.cursor = 'pointer';
  indicator.style.marginLeft = '4px';
  indicator.style.fontSize = '16px';
  indicator.style.opacity = '0.87';

  const updateSortIndicator = () => {
    const column = params.column;
    const currentSort = column.getSort();

    indicator.classList.remove('ag-icon-asc', 'ag-icon-desc', 'ag-icon-none');

    if (currentSort === 'asc') {
      indicator.classList.add('ag-icon-asc');
      indicator.style.opacity = '1';
    } else if (currentSort === 'desc') {
      indicator.classList.add('ag-icon-desc');
      indicator.style.opacity = '1';
    } else {
      indicator.classList.add('ag-icon-none');
      indicator.style.opacity = '0.54';
    }
  };

  const handleSort = (event) => {
    event.stopPropagation();

    const column = params.column;
    const colId = column.getColId();
    const currentSort = column.getSort();
    const nextSort = currentSort === 'desc' ? 'asc' : (currentSort === 'asc' ? null : 'desc');

    if (params.api && typeof params.api.applyColumnState === 'function') {
      params.api.applyColumnState({
        state: [{ colId, sort: nextSort }],
        defaultState: { sort: null }
      });
    }

    setTimeout(updateSortIndicator, 10);
  };

  indicator.addEventListener('click', handleSort);
  updateSortIndicator();

  if (params.api) {
    params.api.addEventListener('sortChanged', updateSortIndicator);
  }

  element.appendChild(indicator);
  return { indicator, updateSortIndicator, handleSort };
}

// Update column visibility based on filtering state
function updateColumnVisibility() {
  if (!window.globalGridApi || !window.benchmarkTree) return;

  const hierarchyMap = buildHierarchyFromTree(window.benchmarkTree);
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);

  // Get all columns
  const allColumns = window.globalGridApi.getAllGridColumns();
  const columnsToUpdate = [];

  // Determine which columns should be visible based on:
  // 1. Current filter state (excluded benchmarks)
  // 2. Current expansion state (what the user has expanded)
  function shouldColumnBeVisible(benchmarkId) {
    // If this benchmark is explicitly excluded, hide it
    if (excludedBenchmarks.has(benchmarkId)) {
      return false;
    }

    // Check if this is the global score column and filtered score is active
    if (benchmarkId === 'average_vision_v0') {
      // Hide global score when filtered score is visible
      const filteredScoreColumn = window.globalGridApi?.getAllGridColumns()?.find(col => col.getColId() === 'filtered_score');
      if (filteredScoreColumn && filteredScoreColumn.isVisible()) {
        return false;
      }
      return true; // Show global score when filtered score is not active
    }

    // Check if this is a top-level category
    const domain = (window.DJANGO_DATA && window.DJANGO_DATA.domain) || 'vision';
    const topLevelCategories = [`neural_${domain}_v0`, `behavior_${domain}_v0`, `engineering_${domain}_v0`];
    if (topLevelCategories.includes(benchmarkId)) {
      // Hide main column if it has no valid children left
      if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
        const leafCount = window.getFilteredLeafCount(benchmarkId);
        if (leafCount === 0) {
          return false;
        }
      }
      return true;
    }

    // Determine if this is a leaf column or parent column (use cached hierarchy)
    if (!window.cachedHierarchyMap) {
      window.cachedHierarchyMap = buildHierarchyFromTree(window.benchmarkTree || []);
    }
    const hierarchyMap = window.cachedHierarchyMap;
    const children = hierarchyMap.get(benchmarkId) || [];
    const isLeafColumn = children.length === 0;

    if (isLeafColumn) {
      // For leaf columns: hide if all values are X's or 0's
      if (shouldHideColumnWithAllXsOrZeros(benchmarkId)) {
        return false;
      }
    } else {
      // For parent columns: hide if they have 0 leaf descendants
      if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
        const leafCount = window.getFilteredLeafCount(benchmarkId);
        if (leafCount === 0) {
          return false;
        }
      }

      // For wayback filtering, also hide parent columns if all their values are 'X'
      if (shouldHideColumnWithAllXsOrZeros(benchmarkId)) {
        return false;
      }
    }

    // For non-top-level benchmarks, check expansion state
    // Find the parent of this benchmark
    let parentId = null;
    for (const [parent, children] of hierarchyMap.entries()) {
      if (children.includes(benchmarkId)) {
        parentId = parent;
        break;
      }
    }

    if (!parentId) {
      // No parent found, treat as top-level
      return true;
    }

    // Parent must be expanded and visible for this to be visible
    const isParentExpanded = window.columnExpansionState.get(parentId) === true;
    const isParentVisible = shouldColumnBeVisible(parentId);

    return isParentExpanded && isParentVisible;
  }

  function shouldHideColumnWithAllXsOrZeros(benchmarkId) {
    // Get current row data (filtered data)
    const rowData = [];
    if (window.globalGridApi) {
      window.globalGridApi.forEachNode(node => {
        if (node.data) {
          rowData.push(node.data);
        }
      });
    }

    if (rowData.length === 0) {
      return false;
    }

    // Check if all values in this column are X or 0
    const values = rowData.map(row => {
      const cellData = row[benchmarkId];
      return cellData && typeof cellData === 'object' ? cellData.value : cellData;
    }).filter(val => val !== null && val !== undefined && val !== '');

    if (values.length === 0) {
      return false; // Don't hide if no values
    }

    // Check if wayback timestamp filtering is active
    const minTimestamp = window.activeFilters?.min_wayback_timestamp;
    const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
    const ranges = window.filterOptions?.datetime_range;
    const fullRangeMin = ranges?.min_unix;
    const fullRangeMax = ranges?.max_unix;
    const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);

    if (isWaybackActive) {
      // For wayback filtering: hide only if ALL values are 'X' (not 0s, since 0s are legitimate scores)
      const allXs = values.every(val => val === 'X');

      // Determine if this is a parent or leaf column for better logging
      const hierarchyMap = window.cachedHierarchyMap || new Map();
      const children = hierarchyMap.get(benchmarkId) || [];
      const columnType = children.length === 0 ? 'leaf' : 'parent';

      // console.log(`Column visibility check for ${columnType} ${benchmarkId}:`, {
      //   columnType,
      //   totalValues: values.length,
      //   allXs,
      //   sampleValues: values.slice(0, 5),
      //   isWaybackActive,
      //   willHide: allXs
      // });
      return allXs;
    }

    // Check if all values are 'X' or 0
    const allXsOrZeros = values.every(val => val === 'X' || val === 0);


    return allXsOrZeros;
  }

  allColumns.forEach(column => {
    const colId = column.getColId();

    // Skip non-benchmark columns (including runnable status)
    if (['model', 'rank', 'runnable_status', 'filtered_score'].includes(colId)) {
      return;
    }

    const shouldShow = shouldColumnBeVisible(colId);
    const isCurrentlyVisible = column.isVisible();

    if (shouldShow !== isCurrentlyVisible) {
      columnsToUpdate.push({ colId, hide: !shouldShow });
    }
  });

  // Apply column visibility changes
  if (columnsToUpdate.length > 0) {
    window.globalGridApi.applyColumnState({
      state: columnsToUpdate
    });
  }
}

// LeafHeaderComponent - for leaf benchmark columns
function LeafHeaderComponent() {}

LeafHeaderComponent.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'leaf-header';
  this.eGui.style.position = 'relative';

  const label = document.createElement('span');
  label.className = 'leaf-header-label';
  label.textContent = params.displayName || params.colDef.headerName;
  label.title = label.textContent;

  this.eGui.appendChild(label);
  createSortIndicator(params, this.eGui);

  // Navigation functionality
  const navigationArea = document.createElement('div');
  navigationArea.className = 'navigation-area';
  navigationArea.style.position = 'absolute';
  navigationArea.style.top = '0';
  navigationArea.style.left = '0';
  navigationArea.style.width = `${window.LeaderboardConstants.NAVIGATION_CLICK_AREA * 100}%`;
  navigationArea.style.height = '100%';
  navigationArea.style.cursor = 'pointer';
  navigationArea.style.zIndex = '9';
  navigationArea.style.backgroundColor = 'transparent';

  this.eGui.appendChild(navigationArea);

  navigationArea.addEventListener('click', (event) => {
    event.stopPropagation();

    const colDef = params.column?.userProvidedColDef || params.column?.colDef || params.colDef || {};
    const benchmarkIdentifier = colDef.field || colDef.headerName || params.displayName;

    if (!benchmarkIdentifier) {
      console.warn('Could not determine benchmark identifier from params:', params);
      return;
    }

    const actualBenchmarkId = window.benchmarkIds && window.benchmarkIds[benchmarkIdentifier];
    if (actualBenchmarkId) {
      const domain = 'vision';
      window.location.href = `/benchmark/${domain}/${actualBenchmarkId}`;
    } else {
      console.warn('No benchmark ID found for identifier:', benchmarkIdentifier);
    }
  });
};

LeafHeaderComponent.prototype.getGui = function() {
  return this.eGui;
};

// ExpandableHeaderComponent - for parent benchmark columns
function ExpandableHeaderComponent() {}

ExpandableHeaderComponent.prototype.init = function(params) {
  this.params = params;

  const colDef = params.column?.userProvidedColDef || params.column?.colDef || {};
  const benchmarkId = colDef.benchmarkId || colDef.field || colDef.headerName;
  const nameMap = {
    average_vision_v0: 'Global Score',
    neural_vision_v0: 'Neural',
    behavior_vision_v0: 'Behavior',
    engineering_vision_v0: 'Engineering',
    average_language_v0: 'Global Score',
    neural_language_v0: 'Neural',
    behavior_language_v0: 'Behavior',
    engineering_language_v0: 'Engineering'
  };
  const displayName = nameMap[benchmarkId] || params.displayName || benchmarkId;

  this.eGui = document.createElement('div');
  const type = benchmarkId.split('_')[0];
  this.eGui.className = `expandable-header ${type}`;
  this.eGui.style.display = 'flex';
  this.eGui.style.alignItems = 'center';

  const labelContainer = document.createElement('div');
  labelContainer.className = 'expandable-header-label-container';

  const title = document.createElement('span');
  title.className = 'expandable-header-label';
  title.textContent = displayName;
  title.title = displayName;

  labelContainer.appendChild(title);
  this.eGui.appendChild(labelContainer);

  if (!benchmarkId || !params.api?.getAllGridColumns) return;
  const allCols = params.api.getAllGridColumns();

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

  // Check if this is a parent column that should have a count badge
  const directChildren = getDirectChildren(colDef.field);
  const hasChildren = directChildren.length > 0;
  const domain = (window.DJANGO_DATA && window.DJANGO_DATA.domain) || 'vision';
  const isTopLevelCategory = [`average_${domain}_v0`, `neural_${domain}_v0`, `behavior_${domain}_v0`, `engineering_${domain}_v0`].includes(colDef.field);

  if (hasChildren || isTopLevelCategory) {
    const count = document.createElement('span');
    count.className = 'benchmark-count';
    count.style.cursor = 'pointer';
    count.dataset.parentField = colDef.field;

    const icon = document.createElement('i');
    icon.className = 'fa-solid fa-up-right-and-down-left-from-center';
    icon.style.marginRight = '4px';
    icon.style.fontSize = '10px';

    const countText = document.createElement('span');
    countText.className = 'count-value';
    countText.style.transition = 'all 0.2s ease';

    // Calculate initial count
    let initialCount = 0;
    if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
      initialCount = window.getFilteredLeafCount(colDef.field);
    } else if (isTopLevelCategory) {
      // Fallback for top-level categories - assume reasonable counts
      const fallbackCounts = {
        [`average_${domain}_v0`]: 50,
        [`neural_${domain}_v0`]: 25,
        [`behavior_${domain}_v0`]: 25,
        [`engineering_${domain}_v0`]: 5
      };
      initialCount = fallbackCounts[colDef.field] || 0;
    } else {
      // For other parent columns, use the number of direct children as fallback
      initialCount = directChildren.length;
    }

    countText.textContent = initialCount;

    count.appendChild(icon);
    count.appendChild(countText);
    this.eGui.appendChild(count);

    count.addEventListener('click', e => {
      e.stopPropagation();

      const columnId = colDef.field;
      const directChildren = getDirectChildren(columnId);
      const isCurrentlyExpanded = window.columnExpansionState.get(columnId) === true;
      const shouldExpand = !isCurrentlyExpanded;

      if (shouldExpand) {
        const directChildIds = directChildren.map(c => c.getColId());

        window.columnExpansionState.set(columnId, true);
        const showState = directChildIds.map(id => ({ colId: id, hide: false }));
        params.api.applyColumnState({ state: showState });

        const allCols = params.api.getAllGridColumns();
        const parentIndex = allCols.findIndex(col => col.getColId() === columnId);
        if (parentIndex !== -1) {
          const insertIndex = parentIndex + 1;
          params.api.moveColumns(directChildIds, insertIndex);
        }

        directChildIds.forEach(childId => {
          window.columnExpansionState.set(childId, false);
        });

        icon.className = 'fa-solid fa-down-left-and-up-right-to-center';

      } else {
        // Collapse: hide ALL descendants recursively
        const allCols = params.api.getAllGridColumns();
        const allDescendantIds = getAllDescendantsFromHierarchy(columnId, buildHierarchyFromTree(window.benchmarkTree || []))
          .map(id => allCols.find(col => col.getColId() === id))
          .filter(Boolean)
          .map(col => col.getColId());

        // Use applyColumnState
        const hideState = allDescendantIds.map(id => ({ colId: id, hide: true }));
        params.api.applyColumnState({ state: hideState });

        // Update expansion state
        window.columnExpansionState.set(columnId, false);

        // Mark all descendants as collapsed
        allDescendantIds.forEach(descendantId => {
          window.columnExpansionState.set(descendantId, false);
        });

        icon.className = 'fa-solid fa-up-right-and-down-left-from-center';
      }

      const toggle = this.eGui.querySelector('.expand-toggle');
      if (toggle) {
        toggle.textContent = shouldExpand ? '▴' : '▾';
      }

      // Debounced column visibility update after expand/collapse
      if (window.expandCollapseUpdateTimeout) {
        clearTimeout(window.expandCollapseUpdateTimeout);
      }
      window.expandCollapseUpdateTimeout = setTimeout(() => {
        if (typeof window.LeaderboardHeaderComponents?.updateColumnVisibility === 'function') {
          window.LeaderboardHeaderComponents.updateColumnVisibility();
        }
      }, 100);
    });
  }

  if (benchmarkId?.startsWith('average_')) {
    createSortIndicator(params, this.eGui, '14px');
    return;
  }

  const childColumns = getDirectChildren(colDef.field);
  if (childColumns.length > 0) {
    createSortIndicator(params, this.eGui);

    this.eGui.style.position = 'relative';
    this.eGui.style.cursor = 'pointer';

    const handleSort = (event) => {
      if (event.target.closest('.expandable-header .benchmark-count') || event.target.closest('.sort-indicator')) {
        return;
      }

      event.stopPropagation();

      const column = params.column;
      const colId = column.getColId();
      const currentSort = column.getSort();
      const nextSort = currentSort === 'desc' ? 'asc' : (currentSort === 'asc' ? null : 'desc');

      if (params.api && typeof params.api.applyColumnState === 'function') {
        params.api.applyColumnState({
          state: [{ colId, sort: nextSort }],
          defaultState: { sort: null }
        });
      }
    };

    this.eGui.addEventListener('click', handleSort);
  }
};

ExpandableHeaderComponent.prototype.getGui = function() {
  return this.eGui;
};

// Export functions for use by other modules
window.LeaderboardHeaderComponents = {
  LeafHeaderComponent,
  ExpandableHeaderComponent,
  createSortIndicator,
  updateColumnVisibility
};
