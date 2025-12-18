// Filter coordination - main orchestrator for all filtering functionality

// Main function that applies all filters
function applyCombinedFilters(skipColumnToggle = false, skipAutoSort = false) {
  if (!window.globalGridApi || !window.originalRowData) return;


  if (typeof window.LeaderboardBenchmarkFilters?.updateBenchmarkFilters === 'function') {
    window.LeaderboardBenchmarkFilters.updateBenchmarkFilters();
  }

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

  // Get current filter values from dual-handle sliders
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

    // Multi-select filters
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

    // Range filters
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

  // Apply wayback timestamp filtering first
  let timestampFilteredData = filteredData;
  // Cache benchmarks hidden by wayback filtering (all X values set by wayback, not originally X)
  window.waybackHiddenBenchmarks = new Set();
  
  if (typeof applyWaybackTimestampFilter === 'function') {
    timestampFilteredData = applyWaybackTimestampFilter(filteredData);
    
    // Check if wayback filtering is actually active
    const minTimestamp = window.activeFilters?.min_wayback_timestamp;
    const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
    const ranges = window.filterOptions?.datetime_range;
    const fullRangeMin = ranges?.min_unix;
    const fullRangeMax = ranges?.max_unix;
    const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
    
    if (isWaybackActive && timestampFilteredData.length > 0) {
      // Collect all benchmark IDs from the data
      const allBenchmarkIds = new Set();
      timestampFilteredData.forEach(row => {
        Object.keys(row).forEach(key => {
          if (key !== 'id' && key !== 'metadata' && key !== 'filtered_score' && 
              row[key] && typeof row[key] === 'object' && row[key].value !== undefined) {
            allBenchmarkIds.add(key);
          }
        });
      });
      
      // Check which benchmarks have all X values that were SET BY wayback filtering
      // (not originally X values from model failures)
      // Compare against filteredData (input to wayback filtering) to see what wayback changed
      // This distinguishes between:
      // 1. X values set by wayback filtering (should hide column and exclude from aggregation)
      // 2. X values that were originally X (should NOT hide column, treat as 0 in aggregation)
      allBenchmarkIds.forEach(benchmarkId => {
        let hasAnyValues = false;
        let xCount = 0;
        let nonXCount = 0;
        
        // Iterate through ALL rows in filteredData (before wayback filtering) to ensure comprehensive check
        filteredData.forEach((beforeWaybackRow) => {
          // Find the corresponding row in timestampFilteredData (after wayback filtering) by ID
          const waybackFilteredRow = timestampFilteredData.find(row => row.id === beforeWaybackRow.id);
          if (!waybackFilteredRow) {
            // Row was removed by wayback filtering (model removal) - skip it
            // This happens when global score becomes X and model is removed
            return;
          }
          
          const beforeWaybackValue = beforeWaybackRow[benchmarkId]?.value;
          const waybackFilteredValue = waybackFilteredRow[benchmarkId]?.value;
          
          // Skip rows where the benchmark doesn't exist or has no value before wayback filtering
          if (beforeWaybackValue === null || beforeWaybackValue === undefined || beforeWaybackValue === '') {
            // Also check if wayback filtering set it to X (due to missing timestamp)
            if (waybackFilteredValue === 'X') {
              // Wayback filtering set a missing value to X - this counts as wayback-set X
              hasAnyValues = true;
              xCount++;
            }
            return;
          }
          
          // We have a value before wayback filtering - check what wayback did to it
          hasAnyValues = true;
          
          // If the wayback-filtered value is X, count it
          if (waybackFilteredValue === 'X') {
            xCount++;
          } else {
            // If wayback-filtered value is not X, then this benchmark shouldn't be hidden
            nonXCount++;
          }
        });
        
        // When wayback filtering is active, hide if ALL values are X (regardless of origin)
        // The distinction between originally X and wayback-set X only matters when wayback is NOT active
        // When wayback IS active, if all values are X, the column should be hidden
        const allValuesAreX = hasAnyValues && xCount > 0 && nonXCount === 0;
        
        if (hasAnyValues && allValuesAreX) {
          // All values are X - hide the column when wayback filtering is active
          window.waybackHiddenBenchmarks.add(benchmarkId);
        }
      });
    }
  } else {
    // No wayback filtering active, clear the cache
    window.waybackHiddenBenchmarks.clear();
  }

  // Initialize finalData
  let finalData = timestampFilteredData;

  // Update filtered scores
  if (typeof updateFilteredScores === 'function') {
    const updatedData = updateFilteredScores(timestampFilteredData);
    if (updatedData) {
      finalData = updatedData;
    }
  }

  // Additional pass: Remove models where global score is 'X'
  if (typeof applyGlobalScoreModelRemoval === 'function') {
    finalData = applyGlobalScoreModelRemoval(finalData);
  }

  // Recalculate colors for all benchmarks AFTER models are removed
  // This ensures colors reflect the correct min/max ranges from the final filtered dataset
  // Models with the same score will have the same color because min/max is calculated from the same dataset
  if (typeof window.LeaderboardColorUtils?.recalculateColorsForBenchmark === 'function' && window.benchmarkTree) {
    // Check if wayback filtering is actually active
    const minTimestamp = window.activeFilters?.min_wayback_timestamp;
    const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
    const ranges = window.filterOptions?.datetime_range;
    const fullRangeMin = ranges?.min_unix;
    const fullRangeMax = ranges?.max_unix;
    const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
    
    if (isWaybackActive) {
      // Build hierarchy map if not already cached
      if (!window.cachedHierarchyMap && typeof window.buildHierarchyFromTree === 'function') {
        window.cachedHierarchyMap = window.buildHierarchyFromTree(window.benchmarkTree);
      }
      const hierarchyMap = window.cachedHierarchyMap || new Map();
      
      // Cache root parent lookups to avoid repeated hierarchy traversal
      if (!window.rootParentCache || window.rootParentCache.size === 0) {
        window.rootParentCache = new Map();
        
        // Get all benchmark IDs
        const allBenchmarkIds = new Set();
        finalData.forEach(row => {
          Object.keys(row).forEach(key => {
            if (key !== 'id' && key !== 'metadata' && key !== 'filtered_score' && 
                row[key] && typeof row[key] === 'object' && row[key].value !== undefined) {
              allBenchmarkIds.add(key);
            }
          });
        });
        // Also include average_vision_v0
        allBenchmarkIds.add('average_vision_v0');
        
        // Build reverse lookup map (child -> parent) for efficient traversal
        const childToParentMap = new Map();
        for (const [parentId, children] of hierarchyMap.entries()) {
          children.forEach(childId => {
            childToParentMap.set(childId, parentId);
          });
        }
        
        // Find root parent for each benchmark
        allBenchmarkIds.forEach(benchmarkId => {
          let rootParent = null;
          let currentId = benchmarkId;
          const visited = new Set();
          
          // Traverse up the hierarchy using reverse lookup map
          while (currentId && !visited.has(currentId)) {
            visited.add(currentId);
            const parentId = childToParentMap.get(currentId);
            
            if (!parentId) {
              // This is a root
              rootParent = currentId;
              break;
            }
            currentId = parentId;
          }
          
          // Fallback: if we couldn't determine root parent, infer from benchmarkId
          if (!rootParent) {
            const checkId = benchmarkId.toLowerCase();
            if (checkId.includes('engineering')) {
              rootParent = 'engineering_vision_v0';
            } else {
              rootParent = 'neural_vision_v0';
            }
          }
          
          window.rootParentCache.set(benchmarkId, rootParent);
        });
      }
      
      // Get all unique benchmark IDs from the final filtered row data
      const benchmarkIds = new Set();
      finalData.forEach(row => {
        Object.keys(row).forEach(key => {
          // Skip non-benchmark fields
          if (key !== 'id' && key !== 'metadata' && key !== 'filtered_score' && 
              row[key] && typeof row[key] === 'object' && row[key].value !== undefined) {
            benchmarkIds.add(key);
          }
        });
      });
      
      // Recalculate colors for each benchmark using the final filtered dataset
      benchmarkIds.forEach(benchmarkId => {
        window.LeaderboardColorUtils.recalculateColorsForBenchmark(finalData, benchmarkId, hierarchyMap, window.rootParentCache);
      });
      
      // Also recalculate color for average_vision_v0
      window.LeaderboardColorUtils.recalculateColorsForBenchmark(finalData, 'average_vision_v0', hierarchyMap, window.rootParentCache);
    } else {
      // Wayback filtering not active, clear root parent cache to free memory
      window.rootParentCache = null;
    }
  }

  // Update grid with filtered data - preserving original data structure
  if (window.globalGridApi) {
    window.globalGridApi.setGridOption('rowData', finalData);
    window.globalGridApi.refreshCells({ force: true });
  }
  if (!skipColumnToggle && typeof toggleFilteredScoreColumn === 'function') {
    toggleFilteredScoreColumn(window.globalGridApi);
  }

  // Only update column visibility if we're not in the initial setup phase
  // During initial setup, setInitialColumnState() handles the column visibility
  if (typeof window.LeaderboardHeaderComponents?.updateColumnVisibility === 'function') {
    // Add a small delay to ensure AG-Grid has processed previous column state changes
    setTimeout(() => {
      window.LeaderboardHeaderComponents.updateColumnVisibility();
    }, 50);
  }

  setTimeout(() => {
    if (typeof window.updateAllCountBadges === 'function') {
      window.updateAllCountBadges();
    }
  }, 50);


  if (typeof window.LeaderboardURLState?.updateURLFromFilters === 'function') {
    window.LeaderboardURLState.updateURLFromFilters();
  }
}

function isColumnHiddenByWaybackFiltering(benchmarkId) {
  // Use cached Set of hidden benchmarks
  if (window.waybackHiddenBenchmarks && window.waybackHiddenBenchmarks.has(benchmarkId)) {
    return true;
  }
  return false;
}

function applyWaybackTimestampFilter(rowData) {
  // Check if wayback timestamp filters are set and not at full range
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;

  // Get the actual range limits from filter options
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;

  const isAtFullRange = (minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);

  if (!minTimestamp || !maxTimestamp || isAtFullRange) {
    return rowData; // No timestamp filtering active
  }

  const filteredWithValidModels = rowData.map(row => {
    const newRow = { ...row };

    Object.keys(row).forEach(key => {
      if (row[key] && typeof row[key] === "object" && row[key].value !== undefined) {
        const ts = row[key].timestamp;

        if (!ts) {
          newRow[key] = { ...row[key], value: "X", color: "#E0E1E2" };
        } else {
          try {
            const scoreTime = new Date(ts).getTime() / 1000; // Convert ISO string to Unix timestamp
            if (scoreTime < minTimestamp || scoreTime > maxTimestamp) {
              newRow[key] = { ...row[key], value: "X", color: "#E0E1E2" };
            }
          } catch (error) {
            newRow[key] = { ...row[key], value: "X", color: "#E0E1E2" };
          }
        }
      }
    });

    return newRow;
  });

  return filteredWithValidModels;
}

function applyGlobalScoreModelRemoval(rowData) {
  // Only apply this additional filtering if wayback timestamp filtering is active
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;

  // Get the actual range limits from filter options
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;

  const isAtFullRange = (minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);

  if (!minTimestamp || !maxTimestamp || isAtFullRange) {
    return rowData; // No wayback filtering active, don't remove any models
  }

  const originalCount = rowData.length;

  // Filter out models where average_vision_v0 is 'X'
  const filteredData = rowData.filter(row => {
    const globalScore = row.average_vision_v0?.value;
    return globalScore !== 'X';
  });

  return filteredData;
}

// Reset all filters to default state
function resetAllFilters() {
  // Clear caches when filters are reset
  window.waybackHiddenBenchmarks = new Set();
  window.rootParentCache = null;
  
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
    public_data_only: false,
    min_wayback_timestamp: null,
    max_wayback_timestamp: null
  };

  // Reset UI elements
  document.querySelectorAll('.filter-dropdown .filter-input').forEach(input => {
    if (input) {
      input.value = '';
      input.placeholder = input.getAttribute('placeholder') || 'Select...';
    }
  });

  document.querySelectorAll('.dropdown-option.selected').forEach(option => {
    if (option) {
      option.classList.remove('selected');
    }
  });

  // Reset dual-handle sliders to their correct max values from filterOptions
  const ranges = window.filterOptions || {};
  if (ranges.parameter_ranges?.max) {
    document.getElementById('paramCountMin').value = 0;
    document.getElementById('paramCountMax').value = ranges.parameter_ranges.max;
    const paramSliderContainer = document.querySelector('#paramCountMin')?.closest('.filter-group')?.querySelector('.slider-container');
    if (paramSliderContainer) {
      const minHandle = paramSliderContainer.querySelector('.handle-min');
      const maxHandle = paramSliderContainer.querySelector('.handle-max');
      const range = paramSliderContainer.querySelector('.slider-range');
      if (minHandle && maxHandle && range) {
        minHandle.style.left = '0%';
        maxHandle.style.left = '100%';
        range.style.left = '0%';
        range.style.width = '100%';
        minHandle.dataset.value = 0;
        maxHandle.dataset.value = ranges.parameter_ranges.max;
      }
    }
  }
  if (ranges.size_ranges?.max) {
    document.getElementById('modelSizeMin').value = 0;
    document.getElementById('modelSizeMax').value = ranges.size_ranges.max;
    const modelSizeSliderContainer = document.querySelector('#modelSizeMin')?.closest('.filter-group')?.querySelector('.slider-container');
    if (modelSizeSliderContainer) {
      const minHandle = modelSizeSliderContainer.querySelector('.handle-min');
      const maxHandle = modelSizeSliderContainer.querySelector('.handle-max');
      const range = modelSizeSliderContainer.querySelector('.slider-range');
      if (minHandle && maxHandle && range) {
        minHandle.style.left = '0%';
        maxHandle.style.left = '100%';
        range.style.left = '0%';
        range.style.width = '100%';
        minHandle.dataset.value = 0;
        maxHandle.dataset.value = ranges.size_ranges.max;
      }
    }
  }
  if (ranges.stimuli_ranges?.max) {
    document.getElementById('stimuliCountMin').value = 0;
    document.getElementById('stimuliCountMax').value = ranges.stimuli_ranges.max;
    const stimuliSliderContainer = document.querySelector('#stimuliCountMin')?.closest('.filter-group')?.querySelector('.slider-container');
    if (stimuliSliderContainer) {
      const minHandle = stimuliSliderContainer.querySelector('.handle-min');
      const maxHandle = stimuliSliderContainer.querySelector('.handle-max');
      const range = stimuliSliderContainer.querySelector('.slider-range');
      if (minHandle && maxHandle && range) {
        minHandle.style.left = '0%';
        maxHandle.style.left = '100%';
        range.style.left = '0%';
        range.style.width = '100%';
        minHandle.dataset.value = 0;
        maxHandle.dataset.value = ranges.stimuli_ranges.max;
      }
    }
  }

  // Reset wayback timestamp slider to full range
  if (ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
    const waybackSliderContainer = document.querySelector('#waybackTimestampFilter .slider-container');
    const waybackDateMin = document.getElementById('waybackDateMin');
    const waybackDateMax = document.getElementById('waybackDateMax');
    
    if (waybackSliderContainer && waybackDateMin && waybackDateMax) {
      const minHandle = waybackSliderContainer.querySelector('.handle-min');
      const maxHandle = waybackSliderContainer.querySelector('.handle-max');
      const range = waybackSliderContainer.querySelector('.slider-range');
      
      if (minHandle && maxHandle && range) {
        // Reset slider handles - min stays at minimum (frozen), max goes to maximum
        minHandle.style.left = '0%';
        maxHandle.style.left = '100%';
        range.style.left = '0%';
        range.style.width = '100%';
        
        // Update data attributes - min stays at minimum timestamp (frozen)
        minHandle.dataset.value = ranges.datetime_range.min_unix;
        maxHandle.dataset.value = ranges.datetime_range.max_unix;
        
        // Reset date input values - min stays at minimum if frozen, max goes to maximum
        const minDate = new Date(ranges.datetime_range.min_unix * 1000);
        const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
        waybackDateMin.value = minDate.toISOString().split('T')[0];
        // Ensure max doesn't exceed today's date
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        const maxDateStr = maxDate.toISOString().split('T')[0];
        waybackDateMax.value = maxDateStr > todayStr ? todayStr : maxDateStr;
        waybackDateMax.max = todayStr;
        
        // Ensure min input remains disabled if frozen
        if (waybackDateMin && typeof window.shouldFreezeMinHandle === 'function' && window.shouldFreezeMinHandle('waybackTimestamp')) {
          waybackDateMin.disabled = true;
          waybackDateMin.style.cursor = 'not-allowed';
          waybackDateMin.style.opacity = '0.6';
        } else if (waybackDateMin) {
          waybackDateMin.disabled = false;
          waybackDateMin.style.cursor = '';
          waybackDateMin.style.opacity = '';
        }
      }
    }
  }

  // Reset ALL benchmark checkboxes to checked
  const checkboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  checkboxes.forEach(cb => {
    if (cb) {
      cb.checked = true;
    }
  });

  // Reset benchmark metadata checkboxes
  document.querySelectorAll('.region-checkbox, .species-checkbox, .task-checkbox').forEach(checkbox => {
    if (checkbox) {
      checkbox.checked = false;
    }
  });

  const publicDataCheckbox = document.getElementById('publicDataFilter');
  if (publicDataCheckbox) {
    publicDataCheckbox.checked = false;
  }

  // Reset filtered benchmarks
  window.filteredOutBenchmarks = new Set();
  checkboxes.forEach(cb => {
    if (cb && !cb.checked) {
      window.filteredOutBenchmarks.add(cb.value);
    }
  });

  // Reset column expansion state to initial state (all collapsed)
  window.columnExpansionState.clear();
  const topLevelCategories = ['average_vision_v0', 'neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0'];
  topLevelCategories.forEach(colId => {
    window.columnExpansionState.set(colId, false);
  });

  // Reset column visibility to initial state
  if (typeof window.setInitialColumnState === 'function') {
    window.setInitialColumnState();
  }

  // Apply filters but skip auto-sort during reset (allow column visibility updates)
  applyCombinedFilters(false, true);

  // Reset sorting to original average_vision_v0 column when filters are reset
  if (window.globalGridApi) {
    setTimeout(() => {
      window.globalGridApi.applyColumnState({
        state: [
          { colId: 'average_vision_v0', sort: 'desc' },
          { colId: 'filtered_score', sort: null }
        ]
      });
    }, 100);
  }

  if (typeof window.LeaderboardURLState?.updateURLFromFilters === 'function') {
    window.LeaderboardURLState.updateURLFromFilters();
  }
}

// Update filtered scores based on current filters
function updateFilteredScores(rowData) {
  if (!window.originalRowData || !window.benchmarkTree) return;

  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  const hierarchyMap = window.buildHierarchyFromTree(window.benchmarkTree);

  // Deep copy the rowData to preserve wayback timestamp filtering changes
  const workingRowData = rowData.map(row => {
    const newRow = { ...row };
    // Deep copy all score objects to preserve wayback filtering changes
    Object.keys(row).forEach(key => {
      if (key !== 'model' && key !== 'rank' && key !== 'metadata' && row[key] && typeof row[key] === 'object') {
        newRow[key] = { ...row[key] };
      }
    });
    return newRow;
  });

  // Calculate depth levels once before processing rows
  function getDepthLevel(benchmarkId, visited = new Set()) {
    if (visited.has(benchmarkId)) return 0;
    visited.add(benchmarkId);

    const children = hierarchyMap.get(benchmarkId) || [];
    if (children.length === 0) return 0;

    const maxChildDepth = Math.max(...children.map(child => getDepthLevel(child, new Set(visited))));
    return maxChildDepth + 1;
  }

  const allBenchmarkIds = Array.from(hierarchyMap.keys());
  const benchmarksByDepth = allBenchmarkIds
    .map(id => ({ id, depth: getDepthLevel(id) }))
    .sort((a, b) => a.depth - b.depth);

  // Determine which benchmarks should be excluded from aggregation
  // Only exclude benchmarks that are hidden by wayback filtering (not benchmarks where all models failed)
  const benchmarksToExcludeFromAggregation = new Set();
  
  // Check if wayback filtering is active
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  // Only exclude benchmarks hidden by wayback filtering
  // When wayback filtering is NOT active, benchmarks with all "X" values should be treated as 0 (incomplete scores), not excluded
  if (isWaybackActive && window.waybackHiddenBenchmarks) {
    window.waybackHiddenBenchmarks.forEach(benchmarkId => {
      benchmarksToExcludeFromAggregation.add(benchmarkId);
    });
  }

  // Then process each row for filtering
  workingRowData.forEach((row) => {
    const originalRow = window.originalRowData.find(origRow => origRow.id === row.id);
    if (!originalRow) return;

    benchmarksByDepth.forEach(({ id: benchmarkId }) => {
      const children = hierarchyMap.get(benchmarkId) || [];

      if (children.length === 0) {
        if (excludedBenchmarks.has(benchmarkId)) {
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: 'X',
            color: '#e0e1e2'
          };
        }
      } else {
        const childScores = [];

        // First pass collect all children and determine if mixed valid/invalid scores
        const childInfo = [];
        children.forEach(childId => {
          if (!excludedBenchmarks.has(childId) && row[childId]) {
            // Skip benchmarks that are hidden by wayback filtering
            // These should be excluded entirely from aggregation, not treated as 0
            // Benchmarks where all models failed (originally "X") should NOT be excluded - treat as 0
            if (benchmarksToExcludeFromAggregation.has(childId)) {
              return; // Exclude this benchmark entirely
            }
            
            const childScore = row[childId].value;
            const hasValidScore = childScore !== null && childScore !== undefined &&
                                 childScore !== '' && childScore !== 'X' &&
                                 !isNaN(parseFloat(childScore));
            childInfo.push({ childId, childScore, hasValidScore });
          }
        });

        // Check if any valid scores among the children
        const hasAnyValidScores = childInfo.some(info => info.hasValidScore);

        // Second pass, build the scores array
        childInfo.forEach(({ childId, childScore, hasValidScore }) => {
          if (hasValidScore) {
            // Include valid numeric scores
            const numVal = parseFloat(childScore);
            childScores.push(numVal);
          } else if (hasAnyValidScores && (childScore === 'X' || childScore === '')) {
            // If we have some valid scores, treat X/empty as 0
            // (This handles cases where some models have valid scores but this model has X)
            childScores.push(0);
          }
          // If no valid scores exist at all, skip everything (childScores will be empty)
        });


        // Check if we should drop out this parent column
        let shouldDropOut = false;

        if (childScores.length === 0) {
          // No children available at all
          shouldDropOut = true;
        } else {
          // Check if all non-excluded children are X or 0
          let validChildrenCount = 0;
          let nonZeroChildrenCount = 0;

          children.forEach(childId => {
            if (!excludedBenchmarks.has(childId) && row[childId]) {
              validChildrenCount++;
              const childScore = row[childId].value;
              if (childScore !== null && childScore !== undefined && childScore !== '' && childScore !== 'X') {
                const numVal = typeof childScore === 'string' ? parseFloat(childScore) : childScore;
                if (!isNaN(numVal) && numVal > 0) {
                  nonZeroChildrenCount++;
                }
              }
            }
          });

          // Drop out if no valid children or all valid children are 0/X
          shouldDropOut = validChildrenCount === 0 || nonZeroChildrenCount === 0;
        }

        if (shouldDropOut) {
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: 'X',
            color: '#e0e1e2'
          };
        } else {
          const average = childScores.reduce((a, b) => a + b, 0) / childScores.length;
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: parseFloat(average.toFixed(3))
          };
        }
      }
    });

    // Calculate global filtered score AND update average_vision_v0
    const visionCategories = ['neural_vision_v0', 'behavior_vision_v0'];
    const categoryScores = [];
    let hasVisibleCategory = false;

    visionCategories.forEach(category => {
      const isExcluded = excludedBenchmarks.has(category);

      // Check if this column would be visible (not dropped out)
      let isColumnVisible = true;
      if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
        const leafCount = window.getFilteredLeafCount(category);
        if (leafCount === 0) {
          isColumnVisible = false; // Column is dropped out
        }
      }

      // Track if at least one category is visible
      if (!isExcluded && isColumnVisible && row[category]) {
        hasVisibleCategory = true;
      }

      // Only include in filtered score if column is visible and not excluded
      if (row[category] && !isExcluded && isColumnVisible) {
        const score = row[category].value;
        if (score !== null && score !== undefined && score !== '') {
          if (score === 'X') {
            // Treat X as 0 in filtered score calculation (but only if column is visible)
            categoryScores.push(0);
          } else {
            const numVal = typeof score === 'string' ? parseFloat(score) : score;
            if (!isNaN(numVal)) {
              categoryScores.push(numVal);
            } else {
              // Treat non-numeric values as 0
              categoryScores.push(0);
            }
          }
        }
      }
    });

    // Update average_vision_v0 (global score) to reflect the updated neural/behavior scores
    // Only update if at least one category is visible. If neither is visible, leave it unchanged.
    if (hasVisibleCategory) {
      if (categoryScores.length > 0) {
        // Check if both categories are X (both treated as 0, so average would be 0)
        // If so, check if model has all 0/X scores - if yes, set to 'X' to filter it out
        const neuralScore = row.neural_vision_v0?.value;
        const behaviorScore = row.behavior_vision_v0?.value;
        const bothAreX = (neuralScore === 'X' || neuralScore === null || neuralScore === undefined || neuralScore === '') &&
                         (behaviorScore === 'X' || behaviorScore === null || behaviorScore === undefined || behaviorScore === '');
        
        if (bothAreX && categoryScores.length === 2 && categoryScores.every(s => s === 0)) {
          // Both categories are X, check if model has all 0/X across all visible benchmarks
          let hasAnyValidNonZeroScore = false;
          allBenchmarkIds.forEach(benchmarkId => {
            if (excludedBenchmarks.has(benchmarkId)) return;
            if (benchmarksToExcludeFromAggregation.has(benchmarkId)) return;
            if (!row[benchmarkId]) return;
            
            // Check if this benchmark is visible (not dropped out)
            let isBenchmarkVisible = true;
            if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
              const leafCount = window.getFilteredLeafCount(benchmarkId);
              if (leafCount === 0) {
                isBenchmarkVisible = false;
              }
            }
            if (!isBenchmarkVisible) return;
            
            const score = row[benchmarkId].value;
            if (score !== null && score !== undefined && score !== '' && score !== 'X') {
              const numVal = typeof score === 'string' ? parseFloat(score) : score;
              if (!isNaN(numVal) && numVal !== 0) {
                hasAnyValidNonZeroScore = true;
              }
            }
          });

          if (!hasAnyValidNonZeroScore) {
            // Model has all 0/X scores, set to 'X' so it gets filtered out
            row.average_vision_v0 = {
              ...row.average_vision_v0,
              value: 'X',
              color: '#e0e1e2'
            };
            row._tempFilteredScore = null;
            return; // Skip the rest of the loop iteration
          }
        }
        
        // Normal case: calculate average
        const globalAverage = categoryScores.reduce((a, b) => a + b, 0) / categoryScores.length;
        row.average_vision_v0 = {
          ...row.average_vision_v0,
          value: parseFloat(globalAverage.toFixed(3))
        };
        row._tempFilteredScore = globalAverage;
      } else {
        // categoryScores.length === 0 means both categories are excluded or not visible
        // In this case, filtered_score should be 'X' because there are no valid scores
        row._tempFilteredScore = null;
        // Don't update average_vision_v0 - leave it as-is when both categories are excluded
      }
    } else {
      // Neither category is visible - filtered_score should be 'X'
      row._tempFilteredScore = null;
      // Don't update average_vision_v0 - leave it as-is when neither category is visible
    }
    // If neither category is visible, don't update average_vision_v0 (leave it as-is)
  });

  // Apply colors for recalculated benchmarks
  // Reuse allBenchmarkIds that was already calculated above
  const recalculatedBenchmarks = new Set();

  // Always recalculate average_vision_v0 since we update it from neural/behavior scores
  recalculatedBenchmarks.add('average_vision_v0');

  allBenchmarkIds.forEach(benchmarkId => {
    const children = hierarchyMap.get(benchmarkId) || [];

    if (children.length > 0) {
      const hasExcludedChildren = children.some(childId => excludedBenchmarks.has(childId));
      if (hasExcludedChildren) {
        recalculatedBenchmarks.add(benchmarkId);

        function markAncestorsRecalculated(targetId) {
          allBenchmarkIds.forEach(parentId => {
            const parentChildren = hierarchyMap.get(parentId) || [];
            if (parentChildren.includes(targetId)) {
              recalculatedBenchmarks.add(parentId);
              markAncestorsRecalculated(parentId);
            }
          });
        }
        markAncestorsRecalculated(benchmarkId);
      }
    }
  });

  // Apply blue coloring for recalculated benchmarks
  allBenchmarkIds.forEach(benchmarkId => {
    if (recalculatedBenchmarks.has(benchmarkId)) {
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
      workingRowData.forEach((row) => {
        // Find the original row by model ID instead of by index
        const originalRow = window.originalRowData.find(origRow => origRow.id === row.id);
        if (originalRow && originalRow[benchmarkId] && originalRow[benchmarkId].color) {
          if (row[benchmarkId] && row[benchmarkId].value !== 'X') {
            // Only restore original colors if the value is not 'X'
            row[benchmarkId].color = originalRow[benchmarkId].color;
          }
        }
      });
    }
  });

  // Handle global filtered score colors
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


  // Return the modified data instead of setting it on the grid
  // The caller will handle setting the grid data
  return workingRowData;
}

// Toggle filtered score column visibility
function toggleFilteredScoreColumn(gridApi) {
  if (!gridApi) return;

  const stimuliMin = parseInt(document.getElementById('stimuliCountMin')?.value || 0);
  const stimuliMax = parseInt(document.getElementById('stimuliCountMax')?.value || 1000);

  const stimuliContainer = document.querySelector('#stimuliCountMin')?.closest('.filter-group')?.querySelector('.slider-container');
  const stimuliRangeMin = parseInt(stimuliContainer?.dataset?.min || 0);
  const stimuliRangeMax = parseInt(stimuliContainer?.dataset?.max || 1000);

  const hasStimuliFiltering = (stimuliMin > stimuliRangeMin || stimuliMax < stimuliRangeMax);

  const hasBenchmarkMetadataFilters = (
    window.activeFilters.benchmark_regions.length > 0 ||
    window.activeFilters.benchmark_species.length > 0 ||
    window.activeFilters.benchmark_tasks.length > 0 ||
    window.activeFilters.public_data_only ||
    hasStimuliFiltering
  );

  const uncheckedCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]:not(:checked)');
  let hasNonEngineeringBenchmarkFilters = false;

  // Only check for non-engineering benchmark filters if the benchmark panel is ready
  const benchmarkPanel = document.getElementById('benchmarkFilterPanel');
  if (benchmarkPanel && benchmarkPanel.children.length > 0) {
    uncheckedCheckboxes.forEach(checkbox => {
      const engineeringNode = document.querySelector('input[value="engineering_vision_v0"]')?.closest('.benchmark-node');
      const isEngineeringChild = engineeringNode && engineeringNode.contains(checkbox);
      const isEngineeringParent = checkbox.value === 'engineering_vision_v0';

      if (!isEngineeringChild && !isEngineeringParent) {
        hasNonEngineeringBenchmarkFilters = true;
      }
    });
  }

  const shouldShowFilteredScore = hasNonEngineeringBenchmarkFilters || hasBenchmarkMetadataFilters;


  if (shouldShowFilteredScore) {
    // First, make column visible
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: false },
        { colId: 'average_vision_v0', hide: true }
      ]
    });

    // Then apply sort with a small delay to ensure AG-Grid has processed the visibility change
    setTimeout(() => {
      // Try to simulate a manual click on the column header
      const filteredScoreColumn = gridApi.getAllGridColumns().find(col => col.getColId() === 'filtered_score');
      if (filteredScoreColumn) {
        // First, try the programmatic approach
        gridApi.applyColumnState({
          state: [
            { colId: 'filtered_score', sort: 'desc' }
          ]
        });

        // Verify it worked, and if not, try to trigger sort via the column API
        setTimeout(() => {
          const currentSort = filteredScoreColumn.getSort();
          if (currentSort !== 'desc') {
            // Try alternative sorting method
            filteredScoreColumn.setSort('desc');
          }
        }, 50);
      }
    }, 25);
  } else {
    gridApi.applyColumnState({
      state: [
        { colId: 'filtered_score', hide: true },
        { colId: 'average_vision_v0', hide: false }
      ]
    });

    // Check if wayback filter is active - if so, sort by average_vision_v0 descending
    const minTimestamp = window.activeFilters?.min_wayback_timestamp;
    const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
    const ranges = window.filterOptions?.datetime_range;
    const fullRangeMin = ranges?.min_unix;
    const fullRangeMax = ranges?.max_unix;
    const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);

    if (isWaybackActive) {
      // Sort by average_vision_v0 descending when wayback filter is active
      setTimeout(() => {
        const averageVisionColumn = gridApi.getAllGridColumns().find(col => col.getColId() === 'average_vision_v0');
        if (averageVisionColumn) {
          gridApi.applyColumnState({
            state: [
              { colId: 'average_vision_v0', sort: 'desc' }
            ]
          });

          // Verify it worked, and if not, try to trigger sort via the column API
          setTimeout(() => {
            const currentSort = averageVisionColumn.getSort();
            if (currentSort !== 'desc') {
              averageVisionColumn.setSort('desc');
            }
          }, 50);
        }
      }, 25);
    }
  }

  // Ensure column visibility is updated after changing filtered score visibility
  setTimeout(() => {
    if (typeof window.LeaderboardHeaderComponents?.updateColumnVisibility === 'function') {
      window.LeaderboardHeaderComponents.updateColumnVisibility();
    }
  }, 100);
}

// Export functions for use by other modules
window.LeaderboardFilterCoordinator = {
  applyCombinedFilters,
  resetAllFilters,
  updateFilteredScores,
  toggleFilteredScoreColumn,
  isColumnHiddenByWaybackFiltering
};

// Make main functions globally available for compatibility
window.applyCombinedFilters = applyCombinedFilters;
window.resetAllFilters = resetAllFilters;
window.updateFilteredScores = updateFilteredScores;
window.toggleFilteredScoreColumn = toggleFilteredScoreColumn;
