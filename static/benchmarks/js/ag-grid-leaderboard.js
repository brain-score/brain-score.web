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
  public_data_only: false
};

// Global state for tracking column expansion
window.columnExpansionState = new Map();

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
// This section handles the display of model code runnable status as colored
// circles in a dedicated Status column with tooltips explaining the status.
// Green = functional, Red = issues, Grey = unknown

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
    headerName: 'Status',
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

function LeafHeaderComponent() {}
LeafHeaderComponent.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'leaf-header';
  this.eGui.style.position = 'relative'; // Enable absolute positioning for click areas

  const label = document.createElement('span');
  label.className = 'leaf-header-label';
  label.textContent = params.displayName || params.colDef.headerName;

  // Add a tooltip for full text
  label.title = label.textContent;

  this.eGui.appendChild(label);

  // Add sort indicator using shared utility
  createSortIndicator(params, this.eGui);

  // NAVIGATION FUNCTIONALITY: Click on left 80% to navigate to benchmark page
  const navigationArea = document.createElement('div');
  navigationArea.className = 'navigation-area';
  navigationArea.style.position = 'absolute';
  navigationArea.style.top = '0';
  navigationArea.style.left = '0';
  navigationArea.style.width = '80%';  // Left 80% for navigation
  navigationArea.style.height = '100%';
  navigationArea.style.cursor = 'pointer';
  navigationArea.style.zIndex = '9';
  navigationArea.style.backgroundColor = 'transparent';
  
  this.eGui.appendChild(navigationArea);

  // Click handler for navigation
  navigationArea.addEventListener('click', (event) => {
    event.stopPropagation();
    
    // Get benchmark ID from the global mapping - use multiple fallbacks
    const colDef = params.column?.userProvidedColDef || params.column?.colDef || params.colDef || {};
    const benchmarkIdentifier = colDef.field || colDef.headerName || params.displayName;
    
    if (!benchmarkIdentifier) {
      console.warn('Could not determine benchmark identifier from params:', params);
      return;
    }
    
    const actualBenchmarkId = window.benchmarkIds && window.benchmarkIds[benchmarkIdentifier];
    if (actualBenchmarkId) {
      // Navigate to benchmark detail page
      const domain = 'vision'; // Default domain for vision benchmarks
      window.location.href = `/benchmark/${domain}/${actualBenchmarkId}`;
    } else {
      console.warn('No benchmark ID found for identifier:', benchmarkIdentifier);
      console.log('Available benchmark IDs:', window.benchmarkIds);
    }
  });

  // Sort handling is now managed by the shared createSortIndicator utility
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



  // Use the global getFilteredLeafCount function for initial count
  const leafFields = window.getFilteredLeafCount ? [colDef.field] : [];

  // Show count badge for number of leaf benchmarks
  if (leafFields.length > 0) {
    const count = document.createElement('span');
    count.className = 'benchmark-count';
    count.style.cursor = 'pointer';  // Make it clear it's clickable
    count.dataset.parentField = colDef.field;  // Store field for dynamic updates
    
    // Add expand/collapse icon and count
    const icon = document.createElement('i');
    icon.className = 'fa-solid fa-up-right-and-down-left-from-center';
    icon.style.marginRight = '4px';
    icon.style.fontSize = '10px';
    
    const countText = document.createElement('span');
    countText.className = 'count-value';
    countText.style.transition = 'all 0.2s ease';  // Smooth animation
    
    // Calculate initial filtered count using global function
    const initialCount = window.getFilteredLeafCount ? window.getFilteredLeafCount(colDef.field) : leafFields.length;
    countText.textContent = initialCount;
    
    count.appendChild(icon);
    count.appendChild(countText);
    this.eGui.appendChild(count);

    // EXPANSION FUNCTIONALITY: Click on count badge to expand/collapse children
    count.addEventListener('click', e => {
      e.stopPropagation();

      const columnId = colDef.field;
      const directChildren = getDirectChildren(columnId);
      const isCurrentlyExpanded = window.columnExpansionState.get(columnId) === true;
      const shouldExpand = !isCurrentlyExpanded;

      if (shouldExpand) {
        // Expanding: show only direct children
        const directChildIds = directChildren.map(c => c.getColId());
        
        // Update expansion state
        window.columnExpansionState.set(columnId, true);
        
        // Show direct children and position them
        params.api.setColumnsVisible(directChildIds, true);
        
        const allCols = params.api.getAllGridColumns();
        const parentIndex = allCols.findIndex(col => col.getColId() === columnId);
        if (parentIndex !== -1) {
          const insertIndex = parentIndex + 1;
          params.api.moveColumns(directChildIds, insertIndex);
        }
        
        // Ensure direct children are marked as collapsed (so they don't show their children)
        directChildIds.forEach(childId => {
          window.columnExpansionState.set(childId, false);
        });
        
        // Update icon to collapse state
        icon.className = 'fa-solid fa-down-left-and-up-right-to-center';
        
      } else {
        // Collapsing: hide all descendants
        const hierarchyMap = buildHierarchyFromTree(window.benchmarkTree || []);
        const allDescendantIds = getAllDescendantsFromHierarchy(columnId, hierarchyMap)
          .map(descendantId => allCols.find(col => col.getColId() === descendantId)?.getColId())
          .filter(Boolean);
        params.api.setColumnsVisible(allDescendantIds, false);
        
        // Update expansion state
        window.columnExpansionState.set(columnId, false);
        
        // Mark all descendants as collapsed
        allDescendantIds.forEach(descendantId => {
          window.columnExpansionState.set(descendantId, false);
        });
        
        // Update icon to expand state
        icon.className = 'fa-solid fa-up-right-and-down-left-from-center';
      }

      // Update toggle visual state if toggle exists
      const toggle = this.eGui.querySelector('.expand-toggle');
      if (toggle) {
        toggle.textContent = shouldExpand ? '▴' : '▾';
      }
      
      // Apply column visibility rules based on current filters
      updateColumnVisibility();
    });
  }

  // Don't show toggle for global score
  if (benchmarkId?.startsWith('average_')) {
    // Add sort indicator for global score using shared utility (larger font)
    createSortIndicator(params, this.eGui, '14px');
    return;
  }

  // Add toggle if children exist, but use it for sorting indication only
  const directChildren = getDirectChildren(colDef.field);
  if (directChildren.length > 0) {
    // Add sort indicator using shared utility
    createSortIndicator(params, this.eGui);

    // SORTING FUNCTIONALITY: Entire header clickable for parent headers (except count badge)
    this.eGui.style.position = 'relative';
    this.eGui.style.cursor = 'pointer';

    const handleSort = (event) => {
      // Don't sort if clicking on count badge or sort indicator itself
      if (event.target.closest('.benchmark-count') || event.target.closest('.sort-indicator')) {
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

    // Add click handler to entire header for parent benchmarks
    this.eGui.addEventListener('click', handleSort);
  }
};
ExpandableHeaderComponent.prototype.getGui = function() {
  return this.eGui;
};

// =====================================
// SEARCH FUNCTIONALITY
// =====================================
// Enhanced search with logical operators (OR, AND, NOT) for model names and submitters.
// Can be made to include model metadata fields.
// Does not support parentheses yet (e.g., "alexnet AND (imagenet OR ecoset)")

// Get searchable text from a row
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

// Parse search query with logical operators (OR, AND, NOT)
// Called in initializeGrid()
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

// Execute parsed search query against searchable text
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

// Global search state
let currentSearchQuery = null;

function setupBenchmarkCheckboxes(filterOptions) {
  // Populate task checkboxes dynamically (since tasks are variable)
  const taskContainer = document.getElementById('taskFilter');
  if (taskContainer && filterOptions.benchmark_tasks) {
    taskContainer.innerHTML = '';
    filterOptions.benchmark_tasks.forEach(task => {
      const label = document.createElement('label');
      label.className = 'checkbox-label';
      label.innerHTML = `
        <input type="checkbox" value="${task}" class="task-checkbox">
        <span>${task}</span>
      `;
      taskContainer.appendChild(label);
    });
  }

  // Add event listeners for ALL benchmark checkboxes
  document.querySelectorAll('.region-checkbox, .species-checkbox, .task-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      updateBenchmarkFilters();
      applyCombinedFilters();
    });
  });

  // Add event listener for public data checkbox
  const publicDataCheckbox = document.getElementById('publicDataFilter');
  if (publicDataCheckbox) {
    publicDataCheckbox.addEventListener('change', function() {
      updateBenchmarkFilters();
      applyCombinedFilters();
    });
  }
}

function addBenchmarksFilteredByMetadata() {
  if (!window.benchmarkMetadata) return;

  // Get stimuli range values
  const stimuliMin = parseInt(document.getElementById('stimuliCountMin')?.value || 0);
  const stimuliMax = parseInt(document.getElementById('stimuliCountMax')?.value || 1000);

  // Check each benchmark against the metadata filters
  window.benchmarkMetadata.forEach(benchmark => {
    let shouldExclude = false;

    // Check region filter
    if (window.activeFilters.benchmark_regions.length > 0) {
      if (!benchmark.region || !window.activeFilters.benchmark_regions.includes(benchmark.region)) {
        shouldExclude = true;
      }
    }

    // Check species filter
    if (window.activeFilters.benchmark_species.length > 0) {
      if (!benchmark.species || !window.activeFilters.benchmark_species.includes(benchmark.species)) {
        shouldExclude = true;
      }
    }

    // Check task filter
    if (window.activeFilters.benchmark_tasks.length > 0) {
      if (!benchmark.task || !window.activeFilters.benchmark_tasks.includes(benchmark.task)) {
        shouldExclude = true;
      }
    }

    // Check public data filter - only exclude explicitly false values, not null
    if (window.activeFilters.public_data_only) {
      if (benchmark.data_publicly_available === false) {
        shouldExclude = true;
      }
    }

    if (benchmark.num_stimuli !== null && benchmark.num_stimuli !== undefined) {
      if (benchmark.num_stimuli < stimuliMin || benchmark.num_stimuli > stimuliMax) {
        shouldExclude = true;
      }
    }

    if (shouldExclude) {
      window.filteredOutBenchmarks.add(benchmark.identifier);
    }
  });
}

function renderBenchmarkTree(container, tree) {
  const ul = document.createElement('ul');
  ul.classList.add('benchmark-tree');

  // First, create the overall "Vision Benchmarks" parent container
  const visionParentLi = document.createElement('li');
  visionParentLi.classList.add('benchmark-node', 'vision-parent');

  const visionParentHeader = document.createElement('div');
  visionParentHeader.classList.add('tree-node-header');

  // Create expand/collapse toggle for vision parent
  const visionToggle = document.createElement('span');
  visionToggle.classList.add('tree-toggle');
  visionToggle.textContent = '▼';  // Start expanded
  visionParentLi.classList.add('expanded');

  visionToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    visionParentLi.classList.toggle('collapsed');
    visionToggle.textContent = visionParentLi.classList.contains('collapsed') ? '▶' : '▼';
  });

  // Create label for vision parent (no checkbox)
  const visionLabel = document.createElement('span');
  visionLabel.className = 'vision-parent-label';
  visionLabel.textContent = 'Vision Benchmarks (Neural + Behavior)';

  visionParentHeader.appendChild(visionToggle);
  visionParentHeader.appendChild(visionLabel);
  visionParentLi.appendChild(visionParentHeader);

  // Create container for vision children
  const visionChildrenUl = document.createElement('ul');
  visionChildrenUl.classList.add('benchmark-tree');

  // Handle engineering separately with its own parent container
  let engineeringNode = null;
  
  tree.forEach((node, index) => {
    // Store engineering node for later processing
    if (node.id === 'engineering_vision_v0') {
      engineeringNode = node;
      return;
    }

    // Skip average_vision_v0 since it's represented by the parent container
    if (node.id === 'average_vision_v0') {
      return;
    }

    // Add neural and behavior to vision parent
    if (node.id === 'neural_vision_v0' || node.id === 'behavior_vision_v0') {
      const childLi = createBenchmarkNode(node);
      visionChildrenUl.appendChild(childLi);
    }
  });

  visionParentLi.appendChild(visionChildrenUl);
  ul.appendChild(visionParentLi);

  // Now create the engineering parent container
  if (engineeringNode) {
    // Add separator before engineering category
    const separator = document.createElement('div');
    separator.classList.add('benchmark-separator');
    separator.innerHTML = '<hr><span class="separator-label"></span>';
    ul.appendChild(separator);

    // Create engineering parent container
    const engineeringParentLi = document.createElement('li');
    engineeringParentLi.classList.add('benchmark-node', 'engineering-parent');

    const engineeringParentHeader = document.createElement('div');
    engineeringParentHeader.classList.add('tree-node-header');

    // Create expand/collapse toggle for engineering parent
    const engineeringToggle = document.createElement('span');
    engineeringToggle.classList.add('tree-toggle');
    engineeringToggle.textContent = '▼';  // Start expanded
    engineeringParentLi.classList.add('expanded');

    engineeringToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      engineeringParentLi.classList.toggle('collapsed');
      engineeringToggle.textContent = engineeringParentLi.classList.contains('collapsed') ? '▶' : '▼';
    });

    // Create label for engineering parent (no checkbox)
    const engineeringLabel = document.createElement('span');
    engineeringLabel.className = 'engineering-parent-label';
    engineeringLabel.textContent = 'Engineering Benchmarks (Not included in Global Score)';

    engineeringParentHeader.appendChild(engineeringToggle);
    engineeringParentHeader.appendChild(engineeringLabel);
    engineeringParentLi.appendChild(engineeringParentHeader);

    // Create container for engineering children
    const engineeringChildrenUl = document.createElement('ul');
    engineeringChildrenUl.classList.add('benchmark-tree');

    // Add the engineering node as a child
    const engineeringChildLi = createBenchmarkNode(engineeringNode);
    engineeringChildrenUl.appendChild(engineeringChildLi);

    engineeringParentLi.appendChild(engineeringChildrenUl);
    ul.appendChild(engineeringParentLi);
  }

  container.appendChild(ul);

  // Helper function to create a benchmark node
  function createBenchmarkNode(node) {
    const li = document.createElement('li');
    li.classList.add('benchmark-node');

    const header = document.createElement('div');
    header.classList.add('tree-node-header');

    // Checkbox
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = node.id;
    checkbox.checked = true; // All benchmarks start checked by default

    checkbox.addEventListener('change', (e) => {
      const isChecked = e.target.checked;

      if (!window.filteredOutBenchmarks) window.filteredOutBenchmarks = new Set();

      if (isChecked) {
        // When checking a box, auto-select all ancestors up to the root
        autoSelectAncestors(checkbox);
        // Also select all descendants of this node
        checkAllDescendants(li);
      } else {
        // When unchecking, uncheck all descendants
        uncheckAllDescendants(li);
      }

      // Update exclusions based on current tree state
      updateExclusions();

      // Apply combined filters (benchmark + model property filters)
      applyCombinedFilters();
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
      const childUl = document.createElement('ul');
      childUl.classList.add('benchmark-tree');
      
      node.children.forEach(childNode => {
        const childLi = createBenchmarkNode(childNode);
        childUl.appendChild(childLi);
      });
      
      li.appendChild(childUl);
    }

    return li;
  }

  // Function to auto-select ancestors when a descendant is selected
  function autoSelectAncestors(checkbox) {
    let currentElement = checkbox.closest('.benchmark-node');
    
    while (currentElement) {
      // Find the parent benchmark node
      const parentUl = currentElement.parentElement;
      const parentLi = parentUl?.closest('.benchmark-node');
      
      if (parentLi && !parentLi.classList.contains('vision-parent') && !parentLi.classList.contains('engineering-parent')) {
        // Find checkbox in parent and check it
        const parentCheckbox = parentLi.querySelector(':scope > .tree-node-header input[type="checkbox"]');
        if (parentCheckbox && !parentCheckbox.checked) {
          parentCheckbox.checked = true;
        }
        currentElement = parentLi;
      } else {
        break;
      }
    }
  }

  // Function to uncheck all descendants when parent is unchecked
  function uncheckAllDescendants(parentNode) {
    const descendantCheckboxes = parentNode.querySelectorAll('input[type="checkbox"]');
    descendantCheckboxes.forEach(cb => {
      cb.checked = false;
    });
  }

  // Function to check all descendants when parent is checked
  function checkAllDescendants(parentNode) {
    const descendantCheckboxes = parentNode.querySelectorAll('input[type="checkbox"]');
    descendantCheckboxes.forEach(cb => {
      cb.checked = true;
    });
  }

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
    
    // Then, add benchmarks that don't match metadata filters
    if (window.benchmarkMetadata) {
      addBenchmarksFilteredByMetadata();
    }
  }
}



// Filter population and handling functions
function populateFilterDropdowns(filterOptions) {
  // Populate Architecture dropdown
  const architectureDropdown = document.querySelector('#architectureFilter .dropdown-content');
  if (architectureDropdown && filterOptions.architectures) {
    architectureDropdown.innerHTML = '';
    filterOptions.architectures.forEach(arch => {
      const option = document.createElement('div');
      option.className = 'dropdown-option';
      option.textContent = arch || 'Unknown';
      option.addEventListener('click', () => selectFilterOption('architecture', arch, option));
      architectureDropdown.appendChild(option);
    });
  }

  // Populate Model Family dropdown
  const familyDropdown = document.querySelector('#modelFamilyFilter .dropdown-content');
  if (familyDropdown && filterOptions.model_families) {
    familyDropdown.innerHTML = '';
    filterOptions.model_families.forEach(family => {
      const option = document.createElement('div');
      option.className = 'dropdown-option';
      option.textContent = family || 'Unknown';
      option.addEventListener('click', () => selectFilterOption('model_family', family, option));
      familyDropdown.appendChild(option);
    });
  }

  // Set Parameter Count range based on actual data
  if (filterOptions.parameter_ranges) {

    const paramMin = document.getElementById('paramCountMin');
    const paramMax = document.getElementById('paramCountMax');

    if (paramMin && paramMax) {
      const paramContainer = paramMin.closest('.filter-group').querySelector('.slider-container');

      if (paramContainer) {
        // Set input ranges
        paramMin.min = filterOptions.parameter_ranges.min;
        paramMin.max = filterOptions.parameter_ranges.max;
        paramMin.value = filterOptions.parameter_ranges.min;

        paramMax.min = filterOptions.parameter_ranges.min;
        paramMax.max = filterOptions.parameter_ranges.max;
        paramMax.value = filterOptions.parameter_ranges.max;

        // Set container data attributes
        paramContainer.dataset.min = filterOptions.parameter_ranges.min;
        paramContainer.dataset.max = filterOptions.parameter_ranges.max;
        paramContainer.dataset.originalMax = filterOptions.parameter_ranges.max;

        // Set handle values
        const minHandle = paramContainer.querySelector('.handle-min');
        const maxHandle = paramContainer.querySelector('.handle-max');
        if (minHandle && maxHandle) {
          minHandle.dataset.value = filterOptions.parameter_ranges.min;
          maxHandle.dataset.value = filterOptions.parameter_ranges.max;
        }
      }
    }
  }

  // Set Model Size range based on actual data
  if (filterOptions.size_ranges) {
    const sizeMin = document.getElementById('modelSizeMin');
    const sizeMax = document.getElementById('modelSizeMax');

    if (sizeMin && sizeMax) {
      const sizeContainer = sizeMin.closest('.filter-group').querySelector('.slider-container');

      if (sizeContainer) {
        // Set input ranges
        sizeMin.min = filterOptions.size_ranges.min;
        sizeMin.max = filterOptions.size_ranges.max;
        sizeMin.value = filterOptions.size_ranges.min;

        sizeMax.min = filterOptions.size_ranges.min;
        sizeMax.max = filterOptions.size_ranges.max;
        sizeMax.value = filterOptions.size_ranges.max;

        // Set container data attributes
        sizeContainer.dataset.min = filterOptions.size_ranges.min;
        sizeContainer.dataset.max = filterOptions.size_ranges.max;

        // Set handle values
        const minHandle = sizeContainer.querySelector('.handle-min');
        const maxHandle = sizeContainer.querySelector('.handle-max');
        if (minHandle && maxHandle) {
          minHandle.dataset.value = filterOptions.size_ranges.min;
          maxHandle.dataset.value = filterOptions.size_ranges.max;
        }
      }
    }
  }

  if (filterOptions.stimuli_ranges) {
    const stimuliMin = document.getElementById('stimuliCountMin');
    const stimuliMax = document.getElementById('stimuliCountMax');

    if (stimuliMin && stimuliMax) {
      const stimuliContainer = stimuliMin.closest('.filter-group').querySelector('.slider-container');

      if (stimuliContainer) {
        // Set input ranges
        stimuliMin.min = filterOptions.stimuli_ranges.min;
        stimuliMin.max = filterOptions.stimuli_ranges.max;
        stimuliMin.value = filterOptions.stimuli_ranges.min;

        stimuliMax.min = filterOptions.stimuli_ranges.min;
        stimuliMax.max = filterOptions.stimuli_ranges.max;
        stimuliMax.value = filterOptions.stimuli_ranges.max;

        // Set container data attributes
        stimuliContainer.dataset.min = filterOptions.stimuli_ranges.min;
        stimuliContainer.dataset.max = filterOptions.stimuli_ranges.max;

        // Set handle values
        const minHandle = stimuliContainer.querySelector('.handle-min');
        const maxHandle = stimuliContainer.querySelector('.handle-max');
        if (minHandle && maxHandle) {
          minHandle.dataset.value = filterOptions.stimuli_ranges.min;
          maxHandle.dataset.value = filterOptions.stimuli_ranges.max;
        }
      }
    }
  }

  // OPTIONAL: Initialize score range (0-1) - only if elements exist
  const scoreMin = document.getElementById('scoreMin');
  const scoreMax = document.getElementById('scoreMax');

  if (scoreMin && scoreMax) {
    const scoreContainer = scoreMin.closest('.filter-group').querySelector('.slider-container');

    if (scoreContainer) {
      scoreMin.value = 0;
      scoreMax.value = 1;

      // Set container data attributes
      scoreContainer.dataset.min = 0;
      scoreContainer.dataset.max = 1;

      // Set handle values
      const minHandle = scoreContainer.querySelector('.handle-min');
      const maxHandle = scoreContainer.querySelector('.handle-max');
      if (minHandle && maxHandle) {
        minHandle.dataset.value = 0;
        maxHandle.dataset.value = 1;
      }
    }
  } else {
    console.log('Score range elements not found - skipping score range initialization');
  }
}

function initializeDualHandleSliders() {
  document.querySelectorAll('.range-filter.dual-handle').forEach(rangeFilter => {
    const container = rangeFilter.querySelector('.slider-container');

    // FIX: Look for inputs in the parent filter-group instead of inside range-filter
    const filterGroup = rangeFilter.closest('.filter-group');
    const minInput = filterGroup.querySelector('.range-input-min');
    const maxInput = filterGroup.querySelector('.range-input-max');

    const minHandle = container.querySelector('.handle-min');
    const maxHandle = container.querySelector('.handle-max');
    const range = container.querySelector('.slider-range');

    // Add null checks to prevent errors
    if (!container || !minInput || !maxInput || !minHandle || !maxHandle || !range) {
      console.warn('Missing slider elements, skipping initialization for:', rangeFilter);
      return;
    }

    const min = parseFloat(container.dataset.min);
    const max = parseFloat(container.dataset.max);
    const step = parseFloat(container.dataset.step) || 1;

    let activeHandle = null;

    function updateRange() {
      const minVal = parseFloat(minHandle.dataset.value);
      const maxVal = parseFloat(maxHandle.dataset.value);

      const minPercent = ((minVal - min) / (max - min)) * 100;
      const maxPercent = ((maxVal - min) / (max - min)) * 100;

      // Update handle positions
      minHandle.style.left = `${minPercent}%`;
      maxHandle.style.left = `${maxPercent}%`;

      // Update the colored range
      range.style.left = `${minPercent}%`;
      range.style.width = `${maxPercent - minPercent}%`;

      // Update inputs
      minInput.value = step < 1 ? minVal.toFixed(2) : minVal;
      maxInput.value = step < 1 ? maxVal.toFixed(2) : maxVal;
    }

    function setHandleValue(handle, value) {
      value = Math.max(min, Math.min(max, value));

      // Prevent handles from crossing
      if (handle === minHandle) {
        const maxVal = parseFloat(maxHandle.dataset.value);
        value = Math.min(value, maxVal);
      } else {
        const minVal = parseFloat(minHandle.dataset.value);
        value = Math.max(value, minVal);
      }

      // Snap to step
      value = Math.round(value / step) * step;

      handle.dataset.value = value;
      updateRange();
    }

    function handleMouseDown(e, handle) {
      e.preventDefault();
      activeHandle = handle;
      document.body.style.cursor = 'grabbing';
      handle.classList.add('active');

      const containerRect = container.getBoundingClientRect();

      function handleMouseMove(e) {
        if (!activeHandle) return;

        const x = e.clientX - containerRect.left;
        const percent = Math.max(0, Math.min(100, (x / containerRect.width) * 100));
        const value = min + (percent / 100) * (max - min);

        setHandleValue(activeHandle, value);
        applyCombinedFilters();
      }

      function handleMouseUp() {
        if (activeHandle) {
          activeHandle.classList.remove('active');
          activeHandle = null;
          document.body.style.cursor = '';
        }
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        
        // Update count badges when stimuli range changes
        if (container.closest('.filter-group').querySelector('#stimuliCountMin, #stimuliCountMax')) {
          setTimeout(() => {
            if (typeof updateAllCountBadges === 'function') {
              updateAllCountBadges();
            }
          }, 100);
        }
      }

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    // Handle click on track
    container.addEventListener('click', (e) => {
      if (e.target.classList.contains('slider-handle')) return;

      const containerRect = container.getBoundingClientRect();
      const x = e.clientX - containerRect.left;
      const percent = (x / containerRect.width) * 100;
      const value = min + (percent / 100) * (max - min);

      // Move the closest handle
      const minVal = parseFloat(minHandle.dataset.value);
      const maxVal = parseFloat(maxHandle.dataset.value);

      if (Math.abs(value - minVal) < Math.abs(value - maxVal)) {
        setHandleValue(minHandle, value);
      } else {
        setHandleValue(maxHandle, value);
      }

      applyCombinedFilters();
    });

    // Handle dragging
    minHandle.addEventListener('mousedown', (e) => handleMouseDown(e, minHandle));
    maxHandle.addEventListener('mousedown', (e) => handleMouseDown(e, maxHandle));

    // Handle input changes
    minInput.addEventListener('change', () => {
      const value = parseFloat(minInput.value) || min;
      setHandleValue(minHandle, value);
      applyCombinedFilters();
    });

    maxInput.addEventListener('change', () => {
      const value = parseFloat(maxInput.value) || max;
      setHandleValue(maxHandle, value);
      applyCombinedFilters();
    });

    // Initialize positions
    updateRange();
  });
}

// Removed unused extractUniqueValues function

function selectFilterOption(filterType, value, optionElement) {
  const dropdown = optionElement.closest('.filter-dropdown');
  const input = dropdown.querySelector('.filter-input');

  // Toggle selection
  optionElement.classList.toggle('selected');

  // Update filter state
  if (optionElement.classList.contains('selected')) {
    // Add to array if not already present
    if (!window.activeFilters[filterType].includes(value)) {
      window.activeFilters[filterType].push(value);
    }
  } else {
    // Remove from array
    window.activeFilters[filterType] = window.activeFilters[filterType].filter(v => v !== value);
  }

  // Update input display to show selected values
  if (window.activeFilters[filterType].length > 0) {
    input.value = window.activeFilters[filterType].join(', ');
  } else {
    input.value = '';
  }

  // Don't hide dropdown on selection (allow multiple selections)
  // Apply filters immediately
  applyCombinedFilters();
}


function setupDropdownHandlers() {
  document.querySelectorAll('.filter-dropdown .filter-input').forEach(input => {
    const originalPlaceholder = input.placeholder;

    input.addEventListener('click', (e) => {
      e.stopPropagation();
      const dropdown = e.target.closest('.filter-dropdown');
      const content = dropdown.querySelector('.dropdown-content');

      // Close other dropdowns
      document.querySelectorAll('.filter-dropdown').forEach(other => {
        if (other !== dropdown) {
          other.classList.remove('active');
          other.querySelector('.dropdown-content').classList.add('hidden');
        }
      });

      dropdown.classList.add('active');
      content.classList.remove('hidden');

      // Clear placeholder to allow typing
      input.placeholder = '';

      // Ensure proper positioning
      content.style.transform = 'none';
      content.style.left = '0';
      content.style.width = '100%';
    });

    input.addEventListener('focus', (e) => {
      if (e.target.value && e.target.value !== e.target.placeholder) {
        e.target.select();
      }
    });

    input.addEventListener('input', (e) => {
      const searchTerm = e.target.value.toLowerCase();
      const dropdown = e.target.closest('.filter-dropdown');
      const content = dropdown.querySelector('.dropdown-content');
      const options = content.querySelectorAll('.dropdown-option');

      if (content.classList.contains('hidden')) {
        dropdown.classList.add('active');
        content.classList.remove('hidden');
      }

      // Filter options based on search
      let visibleCount = 0;
      options.forEach(option => {
        const text = option.textContent.toLowerCase();
        // Check if option matches search and isn't already in the input
        const currentValues = window.activeFilters[dropdown.id.replace('Filter', '')
          .replace(/([A-Z])/g, '_$1').toLowerCase().substring(1)] || [];
        const isSelected = option.classList.contains('selected');

        if (text.includes(searchTerm) || isSelected) {
          option.style.display = 'block';
          visibleCount++;
        } else {
          option.style.display = 'none';
        }
      });

      let noResultsMsg = content.querySelector('.no-results');
      if (visibleCount === 0) {
        if (!noResultsMsg) {
          noResultsMsg = document.createElement('div');
          noResultsMsg.className = 'no-results';
          noResultsMsg.textContent = 'No results found';
          content.appendChild(noResultsMsg);
        }
        noResultsMsg.style.display = 'block';
      } else if (noResultsMsg) {
        noResultsMsg.style.display = 'none';
      }
    });

    input.addEventListener('blur', (e) => {
      setTimeout(() => {
        const dropdown = e.target.closest('.filter-dropdown');
        if (!dropdown.classList.contains('active')) {
          if (!e.target.value) {
            e.target.placeholder = originalPlaceholder;
          }
        }
      }, 200);
    });
  });

  // Prevent dropdown from closing when clicking inside
  document.querySelectorAll('.dropdown-content').forEach(content => {
    content.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  });

  // Close dropdowns when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.filter-dropdown')) {
      document.querySelectorAll('.filter-dropdown').forEach(dropdown => {
        dropdown.classList.remove('active');
        const content = dropdown.querySelector('.dropdown-content');
        content.classList.add('hidden');

        const input = dropdown.querySelector('.filter-input');
        // Don't clear value for multi-select
        if (!input.value && window.activeFilters) {
          const filterType = dropdown.id.replace('Filter', '')
            .replace(/([A-Z])/g, '_$1').toLowerCase().substring(1);
          if (window.activeFilters[filterType] && window.activeFilters[filterType].length > 0) {
            input.value = window.activeFilters[filterType].join(', ');
          }
        }

        if (!input.value) {
          input.placeholder = input.getAttribute('placeholder') || 'Select...';
        }

        content.querySelectorAll('.dropdown-option').forEach(opt => {
          opt.style.display = 'block';
        });

        const noResults = content.querySelector('.no-results');
        if (noResults) {
          noResults.style.display = 'none';
        }
      });
    }
  });
}

function applyCombinedFilters() {
  if (!window.globalGridApi || !window.originalRowData) return;

  updateBenchmarkFilters();

  // Get benchmark checkbox values
  const selectedRegions = Array.from(document.querySelectorAll('.region-checkbox:checked')).map(cb => cb.value);
  const selectedSpecies = Array.from(document.querySelectorAll('.species-checkbox:checked')).map(cb => cb.value);
  const selectedTasks = Array.from(document.querySelectorAll('.task-checkbox:checked')).map(cb => cb.value);
  const publicDataOnly = document.getElementById('publicDataFilter')?.checked || false;

  // Update activeFilters
  window.activeFilters.benchmark_regions = selectedRegions;
  window.activeFilters.benchmark_species = selectedSpecies;
  window.activeFilters.benchmark_tasks = selectedTasks;
  window.activeFilters.public_data_only = publicDataOnly;

  // Get current filter values from dual-handle sliders - with null checks
  const modelSizeMinEl = document.getElementById('modelSizeMin');
  const modelSizeMaxEl = document.getElementById('modelSizeMax');
  const paramCountMinEl = document.getElementById('paramCountMin');
  const paramCountMaxEl = document.getElementById('paramCountMax');
  const scoreMinEl = document.getElementById('scoreMin');
  const scoreMaxEl = document.getElementById('scoreMax');

  const modelSizeMin = modelSizeMinEl ? parseInt(modelSizeMinEl.value) || 0 : 0;
  const modelSizeMax = modelSizeMaxEl ? parseInt(modelSizeMaxEl.value) || 1000 : 1000;
  const paramCountMin = paramCountMinEl ? parseInt(paramCountMinEl.value) || 0 : 0;
  const paramCountMax = paramCountMaxEl ? parseInt(paramCountMaxEl.value) || 100 : 100;
  const scoreMin = scoreMinEl ? parseFloat(scoreMinEl.value) || 0 : 0;
  const scoreMax = scoreMaxEl ? parseFloat(scoreMaxEl.value) || 1 : 1;

  window.activeFilters.min_model_size = modelSizeMin;
  window.activeFilters.max_model_size = modelSizeMax;
  window.activeFilters.min_param_count = paramCountMin;
  window.activeFilters.max_param_count = paramCountMax;
  window.activeFilters.min_score = scoreMin;
  window.activeFilters.max_score = scoreMax;

  const filteredData = window.originalRowData.filter(row => {
    const metadata = row.metadata || {};

    // Multi-select filters - check if ANY selected value matches
    if (window.activeFilters.architecture.length > 0) {
      const modelArchitectures = metadata.architecture ?
        metadata.architecture.split(',').map(a => a.trim()) : [];
      const hasMatch = modelArchitectures.some(arch =>
        window.activeFilters.architecture.includes(arch)
      );
      if (!hasMatch) return false;
    }

    if (window.activeFilters.model_family.length > 0) {
      const modelFamilies = metadata.model_family ?
        metadata.model_family.split(',').map(f => f.trim()) : [];
      const hasMatch = modelFamilies.some(fam =>
        window.activeFilters.model_family.includes(fam)
      );
      if (!hasMatch) return false;
    }

    if (window.activeFilters.training_dataset.length > 0) {
      const modelDatasets = metadata.training_dataset ?
        metadata.training_dataset.split(',').map(d => d.trim()) : [];
      const hasMatch = modelDatasets.some(ds =>
        window.activeFilters.training_dataset.includes(ds)
      );
      if (!hasMatch) return false;
    }

    if (window.activeFilters.task_specialization.length > 0) {
      const modelSpecs = metadata.task_specialization ?
        metadata.task_specialization.split(',').map(s => s.trim()) : [];
      const hasMatch = modelSpecs.some(spec =>
        window.activeFilters.task_specialization.includes(spec)
      );
      if (!hasMatch) return false;
    }

    // Range filters - only apply if elements exist
    if (modelSizeMinEl && modelSizeMaxEl) {
      const modelSize = metadata.model_size_mb || 0;
      if (modelSize < window.activeFilters.min_model_size ||
          modelSize > window.activeFilters.max_model_size) {
        return false;
      }
    }

    if (paramCountMinEl && paramCountMaxEl) {
      const paramCountInMillions = (metadata.total_parameter_count || 0) / 1_000_000;
      if (paramCountInMillions < window.activeFilters.min_param_count ||
          paramCountInMillions > window.activeFilters.max_param_count) {
        return false;
      }
    }

    if (scoreMinEl && scoreMaxEl) {
      const avgScore = row.average_vision_v0?.value;
      if (typeof avgScore === 'number') {
        if (avgScore < window.activeFilters.min_score ||
            avgScore > window.activeFilters.max_score) {
          return false;
        }
      }
    }

    return true;
  });

  window.globalGridApi.setGridOption('rowData', filteredData);

  // Only call these if the functions exist
  if (typeof updateFilteredScores === 'function') {
    updateFilteredScores(filteredData);
  }
  if (typeof toggleFilteredScoreColumn === 'function') {
    toggleFilteredScoreColumn(window.globalGridApi);
  }
  
  // Update column visibility based on current filters and expansion state
  updateColumnVisibility();

  // Update count badges to reflect filtered benchmarks
  setTimeout(() => {
    updateAllCountBadges();
  }, 50); // Small delay to ensure DOM is updated

  // update URL
  updateURLFromFilters();
}

function resetAllFilters() {
  // Clear model property filter state
  window.activeFilters = {
    architecture: [],
    model_family: [],
    training_dataset: [],
    task_specialization: [],
    min_param_count: null,
    max_param_count: null,
    min_model_size: null,
    max_model_size: null,
    min_score: null,
    max_score: null,
    runnable_only: false,
    benchmark_regions: [],
    benchmark_species: [],
    benchmark_tasks: [],
    public_data_only: false
  };

  // Reset UI elements
  document.querySelectorAll('.filter-dropdown .filter-input').forEach(input => {
    if (input) {
      input.value = '';
      input.placeholder = input.getAttribute('placeholder') || 'Select...';
    }
  });

  // Clear all selected states
  document.querySelectorAll('.dropdown-option.selected').forEach(option => {
    if (option) {
      option.classList.remove('selected');
    }
  });

  // Reset dual-handle sliders with null checks
  document.querySelectorAll('.range-filter.dual-handle').forEach(rangeFilter => {
    if (!rangeFilter) return;

    const container = rangeFilter.querySelector('.slider-container');
    if (!container) return;

    const filterGroup = rangeFilter.closest('.filter-group');
    if (!filterGroup) return;

    const minInput = filterGroup.querySelector('.range-input-min');
    const maxInput = filterGroup.querySelector('.range-input-max');
    const minHandle = container.querySelector('.handle-min');
    const maxHandle = container.querySelector('.handle-max');
    const range = container.querySelector('.slider-range');

    if (!minInput || !maxInput || !minHandle || !maxHandle || !range) {
      console.warn('⚠️ Missing slider elements during reset, skipping');
      return;
    }

    const min = parseFloat(container.dataset.min) || 0;
    const max = parseFloat(container.dataset.max) || 100;

    try {
      minInput.value = min;
      maxInput.value = max;
      minHandle.dataset.value = min;
      maxHandle.dataset.value = max;
      minHandle.style.left = '0%';
      maxHandle.style.left = '100%';
      range.style.left = '0%';
      range.style.width = '100%';
    } catch (error) {
      console.error('❌ Error resetting slider:', error);
    }
  });

  // Reset ALL benchmark checkboxes to checked (include everything by default)
  const checkboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  checkboxes.forEach(cb => {
    if (cb) {
      cb.checked = true;  // Check everything including engineering
    }
  });

  // Reset benchmark metadata checkboxes (regions, species, tasks, public data)
  document.querySelectorAll('.region-checkbox, .species-checkbox, .task-checkbox').forEach(checkbox => {
    if (checkbox) {
      checkbox.checked = false;  // Uncheck all benchmark metadata filters
    }
  });

  // Reset public data filter
  const publicDataCheckbox = document.getElementById('publicDataFilter');
  if (publicDataCheckbox) {
    publicDataCheckbox.checked = false;
  }

  // Set filtered benchmarks to only include engineering-related items
  window.filteredOutBenchmarks = new Set();
  checkboxes.forEach(cb => {
    if (cb && !cb.checked) {
      window.filteredOutBenchmarks.add(cb.value);
    }
  });

  // Apply combined filters to properly reset everything
  applyCombinedFilters();
  
  updateURLFromFilters();
}

function updateFilteredScores(rowData) {
  // Use original data as source of truth, never modify it
  if (!window.originalRowData || !window.benchmarkTree) return;
  
  // Capture the excluded state once at the start
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);

  const hierarchyMap = buildHierarchyFromTree(window.benchmarkTree);
  
  // Step 1: Create working copy of data (never modify original)
  const workingRowData = rowData.map(row => ({ ...row }));
  
  // Step 2: For each row, calculate all benchmark scores from scratch
  workingRowData.forEach((row, rowIndex) => {
    const originalRow = window.originalRowData[rowIndex];
    if (!originalRow) return;
    
    // Copy ALL original benchmark scores to working row
    Object.keys(originalRow).forEach(key => {
      if (key !== 'model' && key !== 'rank' && originalRow[key] && typeof originalRow[key] === 'object') {
        row[key] = { ...originalRow[key] }; // Deep copy the score object
      }
    });
    
    // Step 3: Calculate scores bottom-up using topological sort
    function getDepthLevel(benchmarkId, visited = new Set()) {
      if (visited.has(benchmarkId)) return 0; // Avoid cycles
      visited.add(benchmarkId);
      
      const children = hierarchyMap.get(benchmarkId) || [];
      if (children.length === 0) return 0; // Leaf node
      
      const maxChildDepth = Math.max(...children.map(child => getDepthLevel(child, new Set(visited))));
      return maxChildDepth + 1;
    }
    
    // Get all benchmark IDs and sort by depth (deepest first for bottom-up)
    const allBenchmarkIds = Array.from(hierarchyMap.keys());
    const benchmarksByDepth = allBenchmarkIds
      .map(id => ({ id, depth: getDepthLevel(id) }))
      .sort((a, b) => a.depth - b.depth); // Process leaves first (depth 0), then parents
    
    // Step 4: Calculate each benchmark score in bottom-up order
    benchmarksByDepth.forEach(({ id: benchmarkId }) => {
      const children = hierarchyMap.get(benchmarkId) || [];
      
      if (children.length === 0) {
        // LEAF NODE: Use original score, but check if excluded
        if (excludedBenchmarks.has(benchmarkId)) {
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: 'X',
            color: '#e0e1e2'
          };
        }
        // else: keep original score from originalRowData (already copied above)
      } else {
        // PARENT NODE: Calculate from direct children only
        const childScores = [];
        
        children.forEach(childId => {
          if (!excludedBenchmarks.has(childId) && row[childId]) {
            const childScore = row[childId].value;
            if (childScore !== null && childScore !== undefined && childScore !== '' && childScore !== 'X') {
              const numVal = typeof childScore === 'string' ? parseFloat(childScore) : childScore;
              if (!isNaN(numVal)) {
                childScores.push(numVal);
              } else {
                childScores.push(0); // Treat invalid as 0
              }
            } else {
              childScores.push(0); // Treat X/null as 0
            }
          }
        });
        
        if (childScores.length > 0) {
          // Calculate average of included children
          const average = childScores.reduce((a, b) => a + b, 0) / childScores.length;
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: parseFloat(average.toFixed(3))
          };
        } else {
          // No valid children - mark as unavailable
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: 'X',
            color: '#e0e1e2'
          };
        }
      }
    });
    
         // Step 5: Calculate global filtered score from vision categories only (exclude engineering)
     const visionCategories = ['neural_vision_v0', 'behavior_vision_v0'];
     const categoryScores = [];
     
     visionCategories.forEach(category => {
       if (row[category] && !excludedBenchmarks.has(category)) {
         const score = row[category].value;
         if (score !== null && score !== undefined && score !== '' && score !== 'X') {
           const numVal = typeof score === 'string' ? parseFloat(score) : score;
           if (!isNaN(numVal)) {
             categoryScores.push(numVal);
           }
         }
       }
     });
    
    if (categoryScores.length > 0) {
      const globalAverage = categoryScores.reduce((a, b) => a + b, 0) / categoryScores.length;
      row._tempFilteredScore = globalAverage;
    } else {
      row._tempFilteredScore = null;
    }
  });

  // Step 6: Calculate colors - preserve original colors for unaffected benchmarks, use blue for recalculated ones
  const allBenchmarkIds = Array.from(hierarchyMap.keys());
  const recalculatedBenchmarks = new Set(); // Track which benchmarks were recalculated
  
  // First, identify which benchmarks were recalculated due to filtering
  allBenchmarkIds.forEach(benchmarkId => {
    const children = hierarchyMap.get(benchmarkId) || [];
    
    if (children.length > 0) {
      // This is a parent - check if any children were excluded
      const hasExcludedChildren = children.some(childId => excludedBenchmarks.has(childId));
      if (hasExcludedChildren) {
        recalculatedBenchmarks.add(benchmarkId);
        
        // Also mark all ancestors as recalculated
        function markAncestorsRecalculated(targetId) {
          allBenchmarkIds.forEach(parentId => {
            const parentChildren = hierarchyMap.get(parentId) || [];
            if (parentChildren.includes(targetId)) {
              recalculatedBenchmarks.add(parentId);
              markAncestorsRecalculated(parentId); // Recursively mark ancestors
            }
          });
        }
        markAncestorsRecalculated(benchmarkId);
      }
    }
  });
  
  // Apply colors based on whether benchmark was recalculated
  allBenchmarkIds.forEach(benchmarkId => {
    if (recalculatedBenchmarks.has(benchmarkId)) {
      // Use blue coloring for recalculated benchmarks
      const scores = [];
      workingRowData.forEach(row => {
        if (row[benchmarkId] && row[benchmarkId].value !== 'X' && row[benchmarkId].value !== null) {
          const val = row[benchmarkId].value;
          const numVal = typeof val === 'string' ? parseFloat(val) : val;
          if (!isNaN(numVal)) {
            scores.push(numVal);
          }
        }
      });
      
      if (scores.length > 0) {
        const minScore = Math.min(...scores);
        const maxScore = Math.max(...scores);
        const scoreRange = maxScore - minScore;
        
        workingRowData.forEach(row => {
          if (row[benchmarkId] && row[benchmarkId].value !== 'X') {
            const val = row[benchmarkId].value;
            const numVal = typeof val === 'string' ? parseFloat(val) : val;
            if (!isNaN(numVal)) {
              const intensity = scoreRange > 0 ? (numVal - minScore) / scoreRange : 0.5;
              const baseBlue = 255;
              const green = Math.round(173 + (105 * (1 - intensity)));
              const red = Math.round(216 * (1 - intensity));
              const color = `rgba(${red}, ${green}, ${baseBlue}, 0.6)`;
              
              row[benchmarkId].color = color;
            }
          }
        });
      }
    } else {
      // Preserve original colors for unaffected benchmarks
      workingRowData.forEach((row, rowIndex) => {
        const originalRow = window.originalRowData[rowIndex];
        if (originalRow && originalRow[benchmarkId] && originalRow[benchmarkId].color) {
          if (row[benchmarkId]) {
            row[benchmarkId].color = originalRow[benchmarkId].color;
          }
        }
      });
    }
  });

  // Step 7: Handle global filtered score colors
  const globalFilteredScores = workingRowData
    .map(row => row._tempFilteredScore)
    .filter(score => score !== null);
    
  const globalMinScore = globalFilteredScores.length > 0 ? Math.min(...globalFilteredScores) : 0;
  const globalMaxScore = globalFilteredScores.length > 0 ? Math.max(...globalFilteredScores) : 1;
  const globalScoreRange = globalMaxScore - globalMinScore;

  workingRowData.forEach((row) => {
    const mean = row._tempFilteredScore;
    delete row._tempFilteredScore;

    if (mean !== null) {
      const intensity = globalScoreRange > 0 ? (mean - globalMinScore) / globalScoreRange : 0.5;
      const baseBlue = 255;
      const green = Math.round(173 + (105 * (1 - intensity)));
      const red = Math.round(216 * (1 - intensity));
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

  // Step 8: Update the grid with calculated data (original data remains untouched)
  if (window.globalGridApi) {
    window.globalGridApi.setGridOption('rowData', workingRowData);
    window.globalGridApi.refreshCells();
  }
}

function updateBenchmarkFilters() {
  // Update activeFilters with current checkbox states
  window.activeFilters.benchmark_regions = Array.from(document.querySelectorAll('.region-checkbox:checked')).map(cb => cb.value);
  window.activeFilters.benchmark_species = Array.from(document.querySelectorAll('.species-checkbox:checked')).map(cb => cb.value);
  window.activeFilters.benchmark_tasks = Array.from(document.querySelectorAll('.task-checkbox:checked')).map(cb => cb.value);
  window.activeFilters.public_data_only = document.getElementById('publicDataFilter')?.checked || false;

  // Add stimuli range to activeFilters for tracking
  const stimuliMin = parseInt(document.getElementById('stimuliCountMin')?.value || 0);
  const stimuliMax = parseInt(document.getElementById('stimuliCountMax')?.value || 1000);
  window.activeFilters.min_stimuli_count = stimuliMin;
  window.activeFilters.max_stimuli_count = stimuliMax;

  // Recalculate which benchmarks should be excluded
  if (!window.filteredOutBenchmarks) window.filteredOutBenchmarks = new Set();

  // Clear and rebuild the filtered set
  window.filteredOutBenchmarks.clear();

  // Add unchecked benchmarks from tree
  const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  allCheckboxes.forEach(cb => {
    if (!cb.checked) {
      window.filteredOutBenchmarks.add(cb.value);
    }
  });

  // Add benchmarks filtered by metadata
  addBenchmarksFilteredByMetadata();
}

function toggleFilteredScoreColumn(gridApi) {
  if (!gridApi) return;

  // Check for benchmark metadata filters
  const stimuliMin = parseInt(document.getElementById('stimuliCountMin')?.value || 0);
  const stimuliMax = parseInt(document.getElementById('stimuliCountMax')?.value || 1000);

  // Get the actual stimuli ranges from the slider container
  const stimuliContainer = document.querySelector('#stimuliCountMin')?.closest('.filter-group')?.querySelector('.slider-container');
  const stimuliRangeMin = parseInt(stimuliContainer?.dataset?.min || 0);
  const stimuliRangeMax = parseInt(stimuliContainer?.dataset?.max || 1000);

  const hasStimuliFiltering = (stimuliMin > stimuliRangeMin || stimuliMax < stimuliRangeMax);

  // Check for benchmark metadata filters
  const hasBenchmarkMetadataFilters = (
    window.activeFilters.benchmark_regions.length > 0 ||
    window.activeFilters.benchmark_species.length > 0 ||
    window.activeFilters.benchmark_tasks.length > 0 ||
    window.activeFilters.public_data_only ||
    hasStimuliFiltering
  );

  // Check if there are benchmark filters beyond just engineering (since engineering doesn't affect global score)
  const uncheckedCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]:not(:checked)');
  let hasNonEngineeringBenchmarkFilters = false;
  uncheckedCheckboxes.forEach(checkbox => {
    const engineeringNode = document.querySelector('input[value="engineering_vision_v0"]')?.closest('.benchmark-node');
    const isEngineeringChild = engineeringNode && engineeringNode.contains(checkbox);
    const isEngineeringParent = checkbox.value === 'engineering_vision_v0';

    if (!isEngineeringChild && !isEngineeringParent) {
      hasNonEngineeringBenchmarkFilters = true;
    }
  });

  // ONLY benchmark-related filters should trigger filtered score (engineering filters don't count)
  const shouldShowFilteredScore = hasNonEngineeringBenchmarkFilters || hasBenchmarkMetadataFilters;

  if (shouldShowFilteredScore) {
    // Show filtered score, hide global score
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: false },
        { colId: 'average_vision_v0', hide: true }
      ]
    });

    // Auto-sort by filtered score when switching to it
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', sort: 'desc' }
      ],
      defaultState: { sort: null }
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

function parseURLFilters() {
  const params = new URLSearchParams(window.location.search);

  function setArrayFilter(filterKey, elementId) {
    const raw = params.get(filterKey);
    if (!raw) return;
    const values = raw.split(',');
    const dropdown = document.querySelector(`#${elementId} .dropdown-content`);
    values.forEach(val => {
      const match = [...dropdown.querySelectorAll('.dropdown-option')].find(opt => opt.textContent === val);
      if (match) match.classList.add('selected');
    });
    window.activeFilters[filterKey] = values;
    const input = document.querySelector(`#${elementId} .filter-input`);
    if (input) input.value = values.join(', ');
  }

  setArrayFilter('architecture', 'architectureFilter');
  setArrayFilter('model_family', 'modelFamilyFilter');

  // Regions / Species / Tasks checkboxes
  ['benchmark_regions', 'benchmark_species', 'benchmark_tasks'].forEach(key => {
    const raw = params.get(key);
    if (!raw) return;
    const values = raw.split(',');
    values.forEach(val => {
      const checkbox = document.querySelector(`.${key.slice(10)}-checkbox[value="${val}"]`);
      if (checkbox) checkbox.checked = true;
    });
    window.activeFilters[key] = values;
  });

  // Public Data
  const publicOnly = params.get('public_data_only');
  if (publicOnly === 'true') {
    document.getElementById('publicDataFilter').checked = true;
    window.activeFilters.public_data_only = true;
  }

  // HELPER FUNCTION TO SYNC HANDLE POSITIONS
  function syncSliderHandle(id, value) {
    const input = document.getElementById(id);
    if (!input) return;

    const filterGroup = input.closest('.filter-group');
    const container = filterGroup?.querySelector('.slider-container');
    const handle = filterGroup?.querySelector(
      id.includes('Min') ? '.handle-min' : '.handle-max'
    );

    if (handle && container && value !== null) {
      // Update data attribute
      handle.dataset.value = value;

      // Calculate position
      const min = parseFloat(container.dataset.min);
      const max = parseFloat(container.dataset.max);
      const percent = ((value - min) / (max - min)) * 100;

      // Update handle position
      handle.style.left = `${percent}%`;

      // Update range bar
      const range = container.querySelector('.slider-range');
      const minHandle = container.querySelector('.handle-min');
      const maxHandle = container.querySelector('.handle-max');

      if (range && minHandle && maxHandle) {
        const minPercent = parseFloat(minHandle.style.left) || 0;
        const maxPercent = parseFloat(maxHandle.style.left) || 100;

        range.style.left = `${minPercent}%`;
        range.style.width = `${maxPercent - minPercent}%`;
      }
    }
  }

  // --- Slider ranges ---
  function setRange(idMin, idMax, filterMinKey, filterMaxKey) {
    const min = params.get(filterMinKey);
    const max = params.get(filterMaxKey);
    const minInput = document.getElementById(idMin);
    const maxInput = document.getElementById(idMax);

    const container = minInput?.closest('.filter-group')?.querySelector('.slider-container');

    if (minInput && min !== null) {
      minInput.value = min;
      window.activeFilters[filterMinKey] = parseFloat(min);
      syncSliderHandle(idMin, parseFloat(min));  // ✅ sync min handle
    }

    if (maxInput && max !== null) {
      maxInput.value = max;
      window.activeFilters[filterMaxKey] = parseFloat(max);
      syncSliderHandle(idMax, parseFloat(max));  // ✅ sync max handle
    }

    // Optional: reset dataset.max back to original (only if you've stored one)
    if (container && container.dataset.originalMax) {
      container.dataset.max = container.dataset.originalMax;
    }
  }

  setRange('paramCountMin', 'paramCountMax', 'min_param_count', 'max_param_count');
  setRange('modelSizeMin', 'modelSizeMax', 'min_model_size', 'max_model_size');
  setRange('stimuliCountMin', 'stimuliCountMax', 'min_stimuli_count', 'max_stimuli_count');
  setRange('scoreMin', 'scoreMax', 'min_score', 'max_score');

  setTimeout(() => {
    // Trigger the dual handle slider initialization to ensure visual sync
    if (typeof initializeDualHandleSliders === 'function') {
      initializeDualHandleSliders();
    }
  }, 150);

  // Parse benchmark exclusions from URL
  const excludedBenchmarksParam = params.get('excluded_benchmarks');
  if (excludedBenchmarksParam) {
    // Decode the hierarchical exclusions
    const decodedExclusions = decodeBenchmarkFilters(excludedBenchmarksParam);
    window.filteredOutBenchmarks = decodedExclusions;
    
    // Update UI checkboxes to reflect the exclusions
    const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
      cb.checked = !decodedExclusions.has(cb.value);
    });
  }

  updateBenchmarkFilters();
  applyCombinedFilters();
}

// Shared utility function to get all descendants recursively
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
  indicator.className = 'sort-indicator ag-icon';  // Use AG Grid icon classes
  indicator.style.cursor = 'pointer';
  indicator.style.marginLeft = '4px';
  indicator.style.fontSize = '16px';  // AG Grid default icon size
  indicator.style.opacity = '0.87';  // AG Grid's default icon opacity
  
  const updateSortIndicator = () => {
    const column = params.column;
    const currentSort = column.getSort();
    
    // Remove all AG Grid sort icon classes
    indicator.classList.remove('ag-icon-asc', 'ag-icon-desc', 'ag-icon-none');
    
    if (currentSort === 'asc') {
      indicator.classList.add('ag-icon-asc');
      indicator.style.opacity = '1';
    } else if (currentSort === 'desc') {
      indicator.classList.add('ag-icon-desc');
      indicator.style.opacity = '1';
    } else {
      indicator.classList.add('ag-icon-none');
      indicator.style.opacity = '0.54';  // AG Grid's opacity for inactive icons
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

// Function to encode benchmark filters using hierarchical exclusion-based approach
function encodeBenchmarkFilters() {
  if (!window.filteredOutBenchmarks || window.filteredOutBenchmarks.size === 0) {
    return null; // All benchmarks included
  }
  
  const excluded = Array.from(window.filteredOutBenchmarks);
  const hierarchyMap = window.benchmarkTree ? buildHierarchyFromTree(window.benchmarkTree) : new Map();
  
  // Group excluded items and compress hierarchically
  const compressed = [];
  const processed = new Set();
  
  // Check each excluded item
  excluded.forEach(excludedId => {
    if (processed.has(excludedId)) return;
    
    // Check if this is a parent whose ALL children are also excluded
    const allDescendants = getAllDescendantsFromHierarchy(excludedId, hierarchyMap);
    const allDescendantsExcluded = allDescendants.length > 0 && 
      allDescendants.every(descendantId => excluded.includes(descendantId));
    
    if (allDescendantsExcluded) {
      // Entire subtree is excluded, just use the parent
      compressed.push(excludedId);
      processed.add(excludedId);
      allDescendants.forEach(id => processed.add(id));
    } else {
      // Individual exclusion or partial subtree
      compressed.push(excludedId);
      processed.add(excludedId);
    }
  });
  
  return compressed.join(',');
}

// Function to decode benchmark filters from URL parameter
function decodeBenchmarkFilters(excludedParam) {
  if (!excludedParam) {
    return new Set(); // No exclusions
  }
  
  const excludedList = excludedParam.split(',');
  const allExcluded = new Set();
  const hierarchyMap = window.benchmarkTree ? buildHierarchyFromTree(window.benchmarkTree) : new Map();
  
  excludedList.forEach(excludedId => {
    // Add the item itself
    allExcluded.add(excludedId);
    
    // Add all its descendants (for hierarchical exclusion)
    const descendants = getAllDescendantsFromHierarchy(excludedId, hierarchyMap);
    descendants.forEach(descendantId => allExcluded.add(descendantId));
  });
  
  return allExcluded;
}

function updateURLFromFilters() {
  const params = new URLSearchParams();

  const addList = (key) => {
    if (window.activeFilters[key]?.length > 0) {
      params.set(key, window.activeFilters[key].join(','));
    }
  };

  addList('architecture');
  addList('model_family');
  addList('benchmark_regions');
  addList('benchmark_species');
  addList('benchmark_tasks');

  if (window.activeFilters.public_data_only) {
    params.set('public_data_only', 'true');
  }

  // Add benchmark exclusions using hierarchical encoding
  const excludedBenchmarks = encodeBenchmarkFilters();
  if (excludedBenchmarks) {
    params.set('excluded_benchmarks', excludedBenchmarks);
  }

  const setRange = (key) => {
    if (window.activeFilters[key] != null) {
      params.set(key, window.activeFilters[key]);
    }
  };

  [
    'min_param_count', 'max_param_count',
    'min_model_size', 'max_model_size',
    'min_stimuli_count', 'max_stimuli_count',
    'min_score', 'max_score'
  ].forEach(setRange);

  const newURL = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState({}, '', newURL);
}

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
      
      // Header components
      expandableHeaderComponent: ExpandableHeaderComponent,
      leafComponent: LeafHeaderComponent,
    },
    suppressFieldDotNotation: true,

    // External filter for logical search
    isExternalFilterPresent: () => {
      return currentSearchQuery !== null;
    },
    // If search query is present, filter the grid based on the search query
    doesExternalFilterPass: (node) => {
      if (!currentSearchQuery) return true;
      const searchableText = getSearchableText(node.data);
      return executeSearchQuery(currentSearchQuery, searchableText);
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
      
      // Ensure filtered score column starts hidden (clean initial state)
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
    // Connect the search input with logical operators
    const searchInput = document.getElementById('modelSearchInput');
    if (searchInput) {
      // Remove any existing listeners
      const newInput = searchInput.cloneNode(true);
      searchInput.parentNode.replaceChild(newInput, searchInput);

      newInput.addEventListener('input', function () {
        const searchText = this.value;
        // Parse search query with logical operators (OR, AND, NOT)
        currentSearchQuery = parseSearchQuery(searchText);
        
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

// Helper function to build hierarchy map from benchmark tree
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

// Function to update all count badges with filtered counts
function updateAllCountBadges() {
  // Find all count badges and update them
  document.querySelectorAll('.benchmark-count').forEach(badge => {
    const parentField = badge.dataset.parentField;
    if (!parentField) return;
    
    const countText = badge.querySelector('.count-value');
    if (!countText) return;
    
    // Calculate new filtered count
    const newCount = getFilteredLeafCount(parentField);
    const currentCount = parseInt(countText.textContent) || 0;
    
    // Only update if count changed
    if (newCount !== currentCount) {
      // Smooth animation when count changes
      countText.style.transform = 'scale(1.1)';
      countText.style.fontWeight = 'bold';
      
      setTimeout(() => {
        countText.textContent = newCount;
        
        // Visual feedback for empty counts
        if (newCount === 0) {
          badge.style.opacity = '0.5';
          badge.style.filter = 'grayscale(50%)';
        } else {
          badge.style.opacity = '1';
          badge.style.filter = 'none';
        }
        
        setTimeout(() => {
          countText.style.transform = 'scale(1)';
          countText.style.fontWeight = '600';
        }, 100);
      }, 100);
    }
  });
}

// Function to get filtered leaf count (needs to be global for count badges)
function getFilteredLeafCount(parentField) {
  if (!window.globalGridApi) return 0;
  
  const allCols = window.globalGridApi.getAllGridColumns();
  
  function getLeafFieldsGlobal(parentField) {
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
      return field ? getLeafFieldsGlobal(field) : [];
    });
  }
  
  const allLeafFields = getLeafFieldsGlobal(parentField);
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  
  // Count only non-filtered leaf benchmarks
  const visibleLeafFields = allLeafFields.filter(field => {
    return !excludedBenchmarks.has(field);
  });
  
  return visibleLeafFields.length;
}

// Make functions available globally
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
    
         // Check if this is a top-level category (always show if not excluded)
     const topLevelCategories = ['average_vision_v0', 'neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0'];
     if (topLevelCategories.includes(benchmarkId)) {
       return true;
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
  
  allColumns.forEach(column => {
    const colId = column.getColId();
    
    // Skip non-benchmark columns (including runnable status)
    if (['model', 'rank', 'runnable_status', 'filtered_score', 'average_vision_v0'].includes(colId)) {
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

// Function to copy bibtex to clipboard with user feedback
function copyBibtexToClipboard() {
  const bibtexList = collectBenchmarkBibtex();
  
  if (bibtexList.length === 0) {
    showTooltip('copyBibtexBtn', 'No citations found for selected benchmarks', 'warning');
    return;
  }
  
  // Format as a single string with double line breaks between entries
  const formattedBibtex = bibtexList.join('\n\n');
  
  // Copy to clipboard
  navigator.clipboard.writeText(formattedBibtex).then(() => {
    const count = bibtexList.length;
    const message = `Copied ${count} citation${count === 1 ? '' : 's'} to clipboard`;
    showTooltip('copyBibtexBtn', message, 'success');
  }).catch(err => {
    console.error('Failed to copy to clipboard:', err);
    showTooltip('copyBibtexBtn', 'Failed to copy to clipboard', 'error');
  });
}

// Function to collect unique bibtex citations for benchmarks that are not excluded
function collectBenchmarkBibtex() {
  if (!window.originalRowData || window.originalRowData.length === 0) {
    return [];
  }

  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  const hierarchyMap = window.benchmarkTree ? buildHierarchyFromTree(window.benchmarkTree) : new Map();
  const bibtexSet = new Set();
  
  // Helper function to determine if a benchmark is a leaf (has no children)
  function isLeafBenchmark(benchmarkId) {
    const children = hierarchyMap.get(benchmarkId) || [];
    return children.length === 0;
  }
  
  // Use first model as reference for benchmark structure
  // Assumes first model has no missing scores. leaderboard.py only creates fields for benchmarks where the model has scores.
  // leaderboard.py serializes (i.e., flattens) the scores object, so the benchmark data is available at the top level.
  const firstModel = window.originalRowData[0];
  
  // Go through each field in the model data
  Object.keys(firstModel).forEach(fieldName => {
    // Skip non-benchmark fields
    if (fieldName === 'id' || fieldName === 'rank' || fieldName === 'model' || fieldName === 'metadata') {
      return;
    }
    
    const scoreData = firstModel[fieldName];
    
    // Check if this is a leaf benchmark with bibtex data
    if (scoreData && 
        typeof scoreData === 'object' && 
        scoreData.benchmark && 
        scoreData.benchmark.bibtex &&
        isLeafBenchmark(fieldName)) {
      
      // Check if this benchmark is excluded using multiple patterns
      // Assumes string format is benchmarkName_v{version_number}
      const baseFieldName = fieldName.replace(/_v\d+$/, '');
      const benchmarkTypeId = scoreData.benchmark.benchmark_type_id;
      
      // Makes sure that we do not include benchmarks that we have excluded.
      const isExcluded = excludedBenchmarks.has(fieldName) ||
                        excludedBenchmarks.has(baseFieldName) ||
                        excludedBenchmarks.has(benchmarkTypeId);
      
      if (!isExcluded) {
        const bibtex = scoreData.benchmark.bibtex.trim();
        
        // Add to set if valid (Set automatically handles duplicates)
        if (bibtex && bibtex !== 'null') {
          bibtexSet.add(bibtex);
        }
      }
    }
  });
  
  return Array.from(bibtexSet);
}

