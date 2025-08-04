// Benchmark filtering functionality for leaderboard

// Updates the benchmark filters based on current checkbox states
function updateBenchmarkFilters() {
  window.activeFilters.benchmark_regions = Array.from(document.querySelectorAll('.region-checkbox:checked')).map(cb => cb.value);
  window.activeFilters.benchmark_species = Array.from(document.querySelectorAll('.species-checkbox:checked')).map(cb => cb.value);
  window.activeFilters.benchmark_tasks = Array.from(document.querySelectorAll('.task-checkbox:checked')).map(cb => cb.value);
  window.activeFilters.public_data_only = document.getElementById('publicDataFilter')?.checked || false;

  const stimuliMin = parseInt(document.getElementById('stimuliCountMin')?.value || 0);
  const stimuliMax = parseInt(document.getElementById('stimuliCountMax')?.value || 1000);
  window.activeFilters.min_stimuli_count = stimuliMin;
  window.activeFilters.max_stimuli_count = stimuliMax;

  if (!window.filteredOutBenchmarks) window.filteredOutBenchmarks = new Set();

  window.filteredOutBenchmarks.clear();

  const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  allCheckboxes.forEach(cb => {
    if (!cb.checked) {
      window.filteredOutBenchmarks.add(cb.value);
    }
  });

  addBenchmarksFilteredByMetadata();
}

// Sets up benchmark checkboxes and their event listeners
function setupBenchmarkCheckboxes(filterOptions) {
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

  document.querySelectorAll('.region-checkbox, .species-checkbox, .task-checkbox').forEach(checkbox => {
    checkbox.addEventListener('change', function() {
      updateBenchmarkFilters();
      if (typeof window.applyCombinedFilters === 'function') {
        window.applyCombinedFilters();
      }
    });
  });

  const publicDataCheckbox = document.getElementById('publicDataFilter');
  if (publicDataCheckbox) {
    publicDataCheckbox.addEventListener('change', function() {
      updateBenchmarkFilters();
      if (typeof window.applyCombinedFilters === 'function') {
        window.applyCombinedFilters();
      }
    });
  }
}

// Filters benchmarks based on metadata criteria
function addBenchmarksFilteredByMetadata() {
  if (!window.benchmarkMetadata || !window.benchmarkTree) return;
  
  // Prevent recursive calls during manual checkbox interactions
  if (window.updatingCheckboxes || window.processingManualTreeChange) return;
  window.updatingCheckboxes = true;

  const hierarchyMap = window.buildHierarchyFromTree(window.benchmarkTree);
  
  const stimuliMin = parseInt(document.getElementById('stimuliCountMin')?.value || 0);
  const stimuliMax = parseInt(document.getElementById('stimuliCountMax')?.value || 1000);
  
  // Get the actual range limits to detect if stimuli filter is at full range
  const stimuliContainer = document.querySelector('#stimuliCountMin')?.closest('.filter-group')?.querySelector('.slider-container');
  const stimuliRangeMin = parseInt(stimuliContainer?.dataset?.min || 0);
  const stimuliRangeMax = parseInt(stimuliContainer?.dataset?.max || 1000);
  
  // Check if stimuli filter is effectively disabled (at full range)
  const isStimuliFilterActive = stimuliMin > stimuliRangeMin || stimuliMax < stimuliRangeMax;

  // Check if any metadata filters are active
  const hasMetadataFilters = (
    window.activeFilters.benchmark_regions.length > 0 ||
    window.activeFilters.benchmark_species.length > 0 ||
    window.activeFilters.benchmark_tasks.length > 0 ||
    window.activeFilters.public_data_only ||
    isStimuliFilterActive
  );

  // Don't preserve any manual unchecks - let metadata filtering completely control the tree
  // Manual tree interactions should be independent and not interfere with metadata filtering
  
  // Reset all checkboxes to checked state
  const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  allCheckboxes.forEach(checkbox => {
    checkbox.checked = true;
  });
  
  // Clear previous exclusions and rebuild from scratch
  window.filteredOutBenchmarks.clear();
  
  // If no metadata filters are active, we're done (everything should be checked)
  if (!hasMetadataFilters) {
    window.updatingCheckboxes = false;
    return;
  }

  window.benchmarkMetadata.forEach(benchmark => {
    let shouldExclude = false;

    const children = hierarchyMap.get(benchmark.identifier) || [];
    const isParentBenchmark = children.length > 0;

    // Apply metadata filters only to leaf benchmarks (parent benchmarks don't have region metadata)
    if (!isParentBenchmark) {
      if (window.activeFilters.benchmark_regions.length > 0) {
        if (!window.activeFilters.benchmark_regions.includes(benchmark.region)) {
          shouldExclude = true;
        }
      }

      if (window.activeFilters.benchmark_species.length > 0) {
        if (!window.activeFilters.benchmark_species.includes(benchmark.species)) {
          shouldExclude = true;
        }
      }

      if (window.activeFilters.benchmark_tasks.length > 0) {
        if (!window.activeFilters.benchmark_tasks.includes(benchmark.task)) {
          shouldExclude = true;
        }
      }

      if (window.activeFilters.public_data_only) {
        if (benchmark.data_publicly_available === false) {
          shouldExclude = true;
        }
      }

      // Only apply stimuli count filter to leaf benchmarks
      if (isStimuliFilterActive && benchmark.num_stimuli !== null && benchmark.num_stimuli !== undefined) {
        if (benchmark.num_stimuli < stimuliMin || benchmark.num_stimuli > stimuliMax) {
          shouldExclude = true;
        }
      }
    }

    if (shouldExclude) {
      window.filteredOutBenchmarks.add(benchmark.identifier);
      
      // Also uncheck the corresponding checkbox in the benchmark tree
      const checkbox = document.querySelector(`#benchmarkFilterPanel input[value="${benchmark.identifier}"]`);
      if (checkbox) {
        checkbox.checked = false;
      }
    }
  });
  
  // After updating leaf checkboxes, update parent checkboxes based on their children
  updateParentCheckboxes();
  
  // Reset the flag
  window.updatingCheckboxes = false;
}

// Helper function to update parent checkboxes based on their children's state
function updateParentCheckboxes() {
  // Update checkboxes from bottom up (deepest first)
  const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  
  // Process multiple times to ensure all levels are updated
  for (let i = 0; i < 3; i++) {
    allCheckboxes.forEach(parentCheckbox => {
      const parentNode = parentCheckbox.closest('.benchmark-node');
      
      // Get immediate children only (not all descendants)
      const immediateChildren = [];
      const childUl = parentNode.querySelector(':scope > ul');
      if (childUl) {
        const immediateChildNodes = childUl.querySelectorAll(':scope > .benchmark-node');
        immediateChildNodes.forEach(childNode => {
          const childCheckbox = childNode.querySelector(':scope > .tree-node-header input[type="checkbox"]');
          if (childCheckbox) {
            immediateChildren.push(childCheckbox);
          }
        });
      }
      
      // Update parent based on immediate children (if it has any)
      if (immediateChildren.length > 0) {
        const allChildrenUnchecked = immediateChildren.every(cb => !cb.checked);
        const allChildrenChecked = immediateChildren.every(cb => cb.checked);
        
        if (allChildrenUnchecked) {
          parentCheckbox.checked = false;
          window.filteredOutBenchmarks.add(parentCheckbox.value);
        } else if (allChildrenChecked) {
          parentCheckbox.checked = true;
          window.filteredOutBenchmarks.delete(parentCheckbox.value);
        }
        // For mixed state, keep current state but ensure parent is checked
        else {
          parentCheckbox.checked = true;
          window.filteredOutBenchmarks.delete(parentCheckbox.value);
        }
      }
    });
  }
}

// Renders the benchmark tree structure with checkboxes
function renderBenchmarkTree(container, tree) {
  const ul = document.createElement('ul');
  ul.classList.add('benchmark-tree');

  const visionParentLi = document.createElement('li');
  visionParentLi.classList.add('benchmark-node', 'vision-parent');

  const visionParentHeader = document.createElement('div');
  visionParentHeader.classList.add('tree-node-header');

  const visionToggle = document.createElement('span');
  visionToggle.classList.add('tree-toggle');
  visionToggle.textContent = '▼';
  visionParentLi.classList.add('expanded');

  visionToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    visionParentLi.classList.toggle('collapsed');
    visionToggle.textContent = visionParentLi.classList.contains('collapsed') ? '▶' : '▼';
  });

  const visionLabel = document.createElement('span');
  visionLabel.className = 'vision-parent-label';
  visionLabel.textContent = 'Vision Benchmarks (Neural + Behavior)';

  visionParentHeader.appendChild(visionToggle);
  visionParentHeader.appendChild(visionLabel);
  visionParentLi.appendChild(visionParentHeader);

  const visionChildrenUl = document.createElement('ul');
  visionChildrenUl.classList.add('benchmark-tree');

  let engineeringNode = null;
  
  tree.forEach((node, index) => {
    if (node.id === 'engineering_vision_v0') {
      engineeringNode = node;
      return;
    }

    if (node.id === 'average_vision_v0') {
      return;
    }

    if (node.id === 'neural_vision_v0' || node.id === 'behavior_vision_v0') {
      const childLi = createBenchmarkNode(node);
      visionChildrenUl.appendChild(childLi);
    }
  });

  visionParentLi.appendChild(visionChildrenUl);
  ul.appendChild(visionParentLi);

  if (engineeringNode) {
    const separator = document.createElement('div');
    separator.classList.add('benchmark-separator');
    separator.innerHTML = '<hr><span class="separator-label"></span>';
    ul.appendChild(separator);

    const engineeringParentLi = document.createElement('li');
    engineeringParentLi.classList.add('benchmark-node', 'engineering-parent');

    const engineeringParentHeader = document.createElement('div');
    engineeringParentHeader.classList.add('tree-node-header');

    const engineeringToggle = document.createElement('span');
    engineeringToggle.classList.add('tree-toggle');
    engineeringToggle.textContent = '▼';
    engineeringParentLi.classList.add('expanded');

    engineeringToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      engineeringParentLi.classList.toggle('collapsed');
      engineeringToggle.textContent = engineeringParentLi.classList.contains('collapsed') ? '▶' : '▼';
    });

    const engineeringLabel = document.createElement('span');
    engineeringLabel.className = 'engineering-parent-label';
    engineeringLabel.textContent = 'Engineering Benchmarks (Not included in Global Score)';

    engineeringParentHeader.appendChild(engineeringToggle);
    engineeringParentHeader.appendChild(engineeringLabel);
    engineeringParentLi.appendChild(engineeringParentHeader);

    const engineeringChildrenUl = document.createElement('ul');
    engineeringChildrenUl.classList.add('benchmark-tree');

    const engineeringChildLi = createBenchmarkNode(engineeringNode);
    engineeringChildrenUl.appendChild(engineeringChildLi);

    engineeringParentLi.appendChild(engineeringChildrenUl);
    ul.appendChild(engineeringParentLi);
  }

  container.appendChild(ul);

  function createBenchmarkNode(node) {
    const li = document.createElement('li');
    li.classList.add('benchmark-node');

    const header = document.createElement('div');
    header.classList.add('tree-node-header');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.value = node.id;
    checkbox.checked = true;

    checkbox.addEventListener('change', (e) => {
      // Don't process manual clicks if we're in the middle of metadata filtering
      if (window.updatingCheckboxes) {
        return;
      }
      
      // Set flag to prevent metadata filtering from interfering with manual changes
      window.processingManualTreeChange = true;
      
      const isChecked = e.target.checked;

      if (!window.filteredOutBenchmarks) window.filteredOutBenchmarks = new Set();

      if (isChecked) {
        autoSelectAncestors(checkbox);
        checkAllDescendants(li);
      } else {
        uncheckAllDescendants(li);
      }

      updateExclusionsFromTreeOnly();

      if (typeof window.applyCombinedFilters === 'function') {
        window.applyCombinedFilters();
      }
      
      // Reset flag
      window.processingManualTreeChange = false;
    });

    const label = document.createElement('label');
    label.appendChild(checkbox);
    label.append(` ${node.label}`);

    let toggle = null;
    if (node.children?.length) {
      toggle = document.createElement('span');
      toggle.classList.add('tree-toggle');
      toggle.textContent = '▶';
      li.classList.add('collapsed');

      toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        li.classList.toggle('collapsed');
        toggle.textContent = li.classList.contains('collapsed') ? '▶' : '▼';
      });

      header.appendChild(toggle);
    } else {
      const spacer = document.createElement('span');
      spacer.classList.add('tree-toggle');
      spacer.textContent = ' ';
      header.appendChild(spacer);
    }

    header.appendChild(label);
    li.appendChild(header);

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

  function autoSelectAncestors(checkbox) {
    let currentElement = checkbox.closest('.benchmark-node');
    
    while (currentElement) {
      const parentUl = currentElement.parentElement;
      const parentLi = parentUl?.closest('.benchmark-node');
      
      if (parentLi && !parentLi.classList.contains('vision-parent') && !parentLi.classList.contains('engineering-parent')) {
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

  function uncheckAllDescendants(parentNode) {
    const descendantCheckboxes = parentNode.querySelectorAll('input[type="checkbox"]');
    descendantCheckboxes.forEach(cb => {
      cb.checked = false;
    });
  }

  function checkAllDescendants(parentNode) {
    const descendantCheckboxes = parentNode.querySelectorAll('input[type="checkbox"]');
    descendantCheckboxes.forEach(cb => {
      cb.checked = true;
    });
  }

  function updateExclusions() {
    window.filteredOutBenchmarks.clear();

    const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
      if (!cb.checked) {
        window.filteredOutBenchmarks.add(cb.value);
      }
    });
    
    if (window.benchmarkMetadata) {
      addBenchmarksFilteredByMetadata();
    }
    
    // Update count badges after changing exclusions
    if (typeof window.updateAllCountBadges === 'function') {
      window.updateAllCountBadges();
    }
  }
  
  function updateExclusionsFromTreeOnly() {
    window.filteredOutBenchmarks.clear();

    const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
      if (!cb.checked) {
        window.filteredOutBenchmarks.add(cb.value);
      }
    });
    
    // Update count badges after changing exclusions
    if (typeof window.updateAllCountBadges === 'function') {
      window.updateAllCountBadges();
    }
  }
}

// Export functions for use by other modules
window.LeaderboardBenchmarkFilters = {
  updateBenchmarkFilters,
  setupBenchmarkCheckboxes,
  addBenchmarksFilteredByMetadata,
  renderBenchmarkTree
};