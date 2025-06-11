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
  runnable_only: false
};

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
    resetAllFilters();
  });

  // Insert button at the top of the filter panel
  filterPanel.insertBefore(resetBtn, filterPanel.firstChild);
}

// Filter population and handling functions
function populateFilterDropdowns(filterOptions) {
  console.log('Populating filters with options:', filterOptions);

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

  // Populate Training Dataset dropdown
  const trainingDropdown = document.querySelector('#trainingDatasetFilter .dropdown-content');
  if (trainingDropdown && filterOptions.training_datasets) {
    trainingDropdown.innerHTML = '';
    filterOptions.training_datasets.forEach(dataset => {
      const option = document.createElement('div');
      option.className = 'dropdown-option';
      option.textContent = dataset || 'Unknown';
      option.addEventListener('click', () => selectFilterOption('training_dataset', dataset, option));
      trainingDropdown.appendChild(option);
    });
  }

  // Populate Task Specialization dropdown
  const taskDropdown = document.querySelector('#taskSpecFilter .dropdown-content');
  if (taskDropdown && filterOptions.task_specializations) {
    taskDropdown.innerHTML = '';
    filterOptions.task_specializations.forEach(spec => {
      const option = document.createElement('div');
      option.className = 'dropdown-option';
      option.textContent = spec || 'Unknown';
      option.addEventListener('click', () => selectFilterOption('task_specialization', spec, option));
      taskDropdown.appendChild(option);
    });
  }

  // **FIX: Set Parameter Count range based on actual data**
  if (filterOptions.parameter_ranges) {
    console.log('Setting parameter ranges:', filterOptions.parameter_ranges);

    const paramMin = document.getElementById('paramCountMin');
    const paramMax = document.getElementById('paramCountMax');
    const paramContainer = document.querySelector('#paramCountMin').closest('.filter-group').querySelector('.slider-container');

    if (paramMin && paramMax && paramContainer) {
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

      // Set handle values
      const minHandle = paramContainer.querySelector('.handle-min');
      const maxHandle = paramContainer.querySelector('.handle-max');
      if (minHandle && maxHandle) {
        minHandle.dataset.value = filterOptions.parameter_ranges.min;
        maxHandle.dataset.value = filterOptions.parameter_ranges.max;
      }
    }
  }

  // **FIX: Set Model Size range based on actual data**
  if (filterOptions.size_ranges) {
    console.log('Setting size ranges:', filterOptions.size_ranges);

    const sizeMin = document.getElementById('modelSizeMin');
    const sizeMax = document.getElementById('modelSizeMax');
    const sizeContainer = document.querySelector('#modelSizeMin').closest('.filter-group').querySelector('.slider-container');

    if (sizeMin && sizeMax && sizeContainer) {
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

  // Initialize score range (0-1) - this should always be 0-1
  const scoreMin = document.getElementById('scoreMin');
  const scoreMax = document.getElementById('scoreMax');
  const scoreContainer = document.querySelector('#scoreMin').closest('.filter-group').querySelector('.slider-container');

  if (scoreMin && scoreMax && scoreContainer) {
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

// Helper function to extract unique values from the data if not provided in filterOptions
function extractUniqueValues(field) {
  if (!window.originalRowData) return [];

  const values = new Set();
  window.originalRowData.forEach(row => {
    if (row.metadata && row.metadata[field]) {
      values.add(row.metadata[field]);
    }
  });

  return Array.from(values).sort();
}

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
  console.log('🖱️ Setting up dropdown handlers...');

  document.querySelectorAll('.filter-dropdown .filter-input').forEach(input => {
    console.log('📝 Adding handlers to:', input.placeholder);

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

  // Get current filter values from dual-handle sliders
  const modelSizeMin = parseInt(document.getElementById('modelSizeMin').value) || 0;
  const modelSizeMax = parseInt(document.getElementById('modelSizeMax').value) || 1000;
  const paramCountMin = parseInt(document.getElementById('paramCountMin').value) || 0;
  const paramCountMax = parseInt(document.getElementById('paramCountMax').value) || 100;
  const scoreMin = parseFloat(document.getElementById('scoreMin').value) || 0;
  const scoreMax = parseFloat(document.getElementById('scoreMax').value) || 1;

  window.activeFilters.min_model_size = modelSizeMin;
  window.activeFilters.max_model_size = modelSizeMax;
  window.activeFilters.min_param_count = paramCountMin * 1_000_000;
  window.activeFilters.max_param_count = paramCountMax * 1_000_000;
  window.activeFilters.min_score = scoreMin;
  window.activeFilters.max_score = scoreMax;

  const filteredData = window.originalRowData.filter(row => {
    const metadata = row.metadata || {};

    // Multi-select filters - check if ANY selected value matches
    if (window.activeFilters.architecture.length > 0) {
      // Split the model's architecture field and check if any match
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

    // Range filters remain the same
    const modelSize = metadata.model_size_mb || 0;
    if (modelSize < window.activeFilters.min_model_size ||
        modelSize > window.activeFilters.max_model_size) {
      return false;
    }

    const paramCount = metadata.total_parameter_count || 0;
    if (paramCount < window.activeFilters.min_param_count ||
        paramCount > window.activeFilters.max_param_count) {
      return false;
    }

    const avgScore = row.average_vision_v0?.value;
    if (typeof avgScore === 'number') {
      if (avgScore < window.activeFilters.min_score ||
          avgScore > window.activeFilters.max_score) {
        return false;
      }
    }

    return true;
  });

  window.globalGridApi.setGridOption('rowData', filteredData);
  updateFilteredScores(filteredData);
  toggleFilteredScoreColumn(window.globalGridApi);
}

function resetAllFilters() {
  console.log('🔄 Resetting all filters...');

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
    runnable_only: false
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

  // Reset ALL benchmark checkboxes to checked first
  const checkboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  checkboxes.forEach(cb => {
    if (cb) {
      cb.checked = true;  // Check everything first
    }
  });

  // Then uncheck only the engineering parent (this will trigger the event handler to uncheck children)
  const engineeringCheckbox = document.querySelector('input[value="engineering_vision_v0"]');
  if (engineeringCheckbox) {
    engineeringCheckbox.checked = false;

    // Manually uncheck engineering children since the event might not fire during reset
    const engineeringNode = engineeringCheckbox.closest('.benchmark-node');
    if (engineeringNode) {
      const childCheckboxes = engineeringNode.querySelectorAll('input[type="checkbox"]');
      childCheckboxes.forEach(cb => {
        if (cb !== engineeringCheckbox) {  // Don't double-process the parent
          cb.checked = false;
        }
      });
    }
  }

  // Set filtered benchmarks to only include engineering-related items
  window.filteredOutBenchmarks = new Set();
  checkboxes.forEach(cb => {
    if (cb && !cb.checked) {
      window.filteredOutBenchmarks.add(cb.value);
    }
  });

  console.log('🔍 After reset, filtered out benchmarks:', [...window.filteredOutBenchmarks]);

  // Reset grid to original data
  if (window.globalGridApi && window.originalRowData) {
    try {
      window.globalGridApi.setGridOption('rowData', window.originalRowData);
      updateFilteredScores(window.originalRowData);
      toggleFilteredScoreColumn(window.globalGridApi);  // Should now show Global Score with smart logic
      console.log('✅ Grid data reset successfully');
    } catch (error) {
      console.error('❌ Error resetting grid data:', error);
    }
  }

  console.log('✅ Filter reset complete - should show Global Score');
}

function updateFilteredScores(rowData) {
  // Capture the excluded state once at the start
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  // console.log('🔍 Excluded set when neural unchecked but V1 checked:', [...excludedBenchmarks]);

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

  // Check if there are meaningful filters beyond just engineering being excluded

  // Check parameter filters by comparing current values to min/max ranges
  const modelSizeMin = parseInt(document.getElementById('modelSizeMin')?.value || 0);
  const modelSizeMax = parseInt(document.getElementById('modelSizeMax')?.value || 1000);
  const paramCountMin = parseInt(document.getElementById('paramCountMin')?.value || 0);
  const paramCountMax = parseInt(document.getElementById('paramCountMax')?.value || 100);
  const scoreMin = parseFloat(document.getElementById('scoreMin')?.value || 0);
  const scoreMax = parseFloat(document.getElementById('scoreMax')?.value || 1);

  // Get the actual ranges from the slider containers
  const sizeContainer = document.querySelector('#modelSizeMin')?.closest('.filter-group')?.querySelector('.slider-container');
  const paramContainer = document.querySelector('#paramCountMin')?.closest('.filter-group')?.querySelector('.slider-container');
  const scoreContainer = document.querySelector('#scoreMin')?.closest('.filter-group')?.querySelector('.slider-container');

  const sizeRangeMin = parseInt(sizeContainer?.dataset?.min || 0);
  const sizeRangeMax = parseInt(sizeContainer?.dataset?.max || 1000);
  const paramRangeMin = parseInt(paramContainer?.dataset?.min || 0);
  const paramRangeMax = parseInt(paramContainer?.dataset?.max || 100);
  const scoreRangeMin = parseFloat(scoreContainer?.dataset?.min || 0);
  const scoreRangeMax = parseFloat(scoreContainer?.dataset?.max || 1);

  const hasParameterFilters = (
    modelSizeMin > sizeRangeMin ||
    modelSizeMax < sizeRangeMax ||
    paramCountMin > paramRangeMin ||
    paramCountMax < paramRangeMax ||
    scoreMin > scoreRangeMin ||
    scoreMax < scoreRangeMax
  );

  const hasModelPropertyFilters = (
    window.activeFilters.architecture.length > 0 ||
    window.activeFilters.model_family.length > 0 ||
    window.activeFilters.training_dataset.length > 0 ||
    window.activeFilters.task_specialization.length > 0 ||
    hasParameterFilters
  );

  // Check if there are benchmark filters beyond just engineering
  // We need to check if ONLY engineering-related benchmarks are filtered out
  const filteredBenchmarks = window.filteredOutBenchmarks || new Set();

  // Get all checkboxes that are currently unchecked
  const uncheckedCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]:not(:checked)');

  // Check if any unchecked items are NOT children of engineering
  let hasNonEngineeringBenchmarkFilters = false;
  uncheckedCheckboxes.forEach(checkbox => {
    const engineeringNode = document.querySelector('input[value="engineering_vision_v0"]')?.closest('.benchmark-node');
    const isEngineeringChild = engineeringNode && engineeringNode.contains(checkbox);
    const isEngineeringParent = checkbox.value === 'engineering_vision_v0';

    if (!isEngineeringChild && !isEngineeringParent) {
      hasNonEngineeringBenchmarkFilters = true;
    }
  });

  const hasFilters = hasModelPropertyFilters || hasNonEngineeringBenchmarkFilters;

  console.log('🔍 Toggle score column check:', {
    hasModelPropertyFilters,
    hasParameterFilters,
    hasNonEngineeringBenchmarkFilters,
    parameterValues: {
      modelSizeMin, modelSizeMax, sizeRangeMin, sizeRangeMax,
      paramCountMin, paramCountMax, paramRangeMin, paramRangeMax,
      scoreMin, scoreMax, scoreRangeMin, scoreRangeMax
    },
    filteredBenchmarks: [...filteredBenchmarks],
    uncheckedCount: uncheckedCheckboxes.length,
    hasFilters,
    willShow: hasFilters ? 'Filtered Score' : 'Global Score'
  });

  if (hasFilters) {
    // Show filtered score, hide global score
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: false },
        { colId: 'average_vision_v0', hide: true }
      ]
    });
    console.log('📊 Showing Filtered Score');
  } else {
    // Hide filtered score, show global score
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: true },
        { colId: 'average_vision_v0', hide: false }
      ]
    });
    console.log('🌍 Showing Global Score');
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
window.populateFilterDropdowns = populateFilterDropdowns;
window.setupDropdownHandlers = setupDropdownHandlers;
window.applyCombinedFilters = applyCombinedFilters;
window.resetAllFilters = resetAllFilters;
window.initializeDualHandleSliders = initializeDualHandleSliders;