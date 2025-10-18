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
  if (typeof applyWaybackTimestampFilter === 'function') {
    timestampFilteredData = applyWaybackTimestampFilter(filteredData);
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
  // Only check for wayback filtering if it's active
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);

  if (!isWaybackActive) {
    return false; // No wayback filtering, column not hidden
  }

  // Get current row data from the grid
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

  // Check if all values in this column are 'X'
  const values = rowData.map(row => {
    const cellData = row[benchmarkId];
    return cellData && typeof cellData === 'object' ? cellData.value : cellData;
  }).filter(val => val !== null && val !== undefined && val !== '');

  if (values.length === 0) {
    return false; // Don't hide if no values
  }

  const allXs = values.every(val => val === 'X');
  return allXs;
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

  console.log('Applying wayback timestamp filter:', {
    minTimestamp,
    maxTimestamp,
    minDate: new Date(minTimestamp * 1000).toISOString(),
    maxDate: new Date(maxTimestamp * 1000).toISOString()
  });

  // Stats counters
  let totalScoresProcessed = 0;
  let scoresWithTimestamps = 0;
  let scoresWithoutTimestamps = 0;
  let scoresFilteredOut = 0;

  const filteredWithValidModels = rowData.map(row => {
    const newRow = { ...row };

    Object.keys(row).forEach(key => {
      if (row[key] && typeof row[key] === "object" && row[key].value !== undefined) {
        totalScoresProcessed++;


        const ts = row[key].timestamp;


        if (!ts) {
          scoresWithoutTimestamps++;
          newRow[key] = { ...row[key], value: "X", color: "#E0E1E2" };
        } else {
          try {
            const scoreTime = new Date(ts).getTime() / 1000; // Convert ISO string to Unix timestamp
            if (scoreTime < minTimestamp || scoreTime > maxTimestamp) {
              scoresFilteredOut++;
              newRow[key] = { ...row[key], value: "X", color: "#E0E1E2" };
            } else {
              scoresWithTimestamps++;
            }
          } catch (error) {
            scoresWithoutTimestamps++;
            newRow[key] = { ...row[key], value: "X", color: "#E0E1E2" };
          }
        }
      }
    });

    return newRow;
  });

  console.log("Wayback timestamp filtering results:", {
    originalRows: rowData.length,
    filteredRows: filteredWithValidModels.length,
    totalScoresProcessed,
    scoresWithTimestamps,
    scoresWithoutTimestamps,
    scoresFilteredOut,
    percentageScoresWithTimestamps:
      ((scoresWithTimestamps / Math.max(1, totalScoresProcessed)) * 100).toFixed(1) + "%",
    percentageScoresFilteredOut:
      ((scoresFilteredOut / Math.max(1, totalScoresProcessed)) * 100).toFixed(1) + "%"
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

  const removedCount = originalCount - filteredData.length;

  console.log('Global score model removal:', {
    originalModels: originalCount,
    modelsWithXGlobalScore: removedCount,
    remainingModels: filteredData.length,
    removedModels: removedCount > 0 ? rowData.filter(row => row.average_vision_v0?.value === 'X').slice(0, 3).map(row => row.model?.name || 'Unknown') : []
  });

  return filteredData;
}

// Reset all filters to default state
function resetAllFilters() {
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

  console.log('updateFilteredScores called - checking for wayback timestamp changes...');

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

  // Then process each row for filtering
  workingRowData.forEach((row) => {
    const originalRow = window.originalRowData.find(origRow => origRow.id === row.id);
    if (!originalRow) return;

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

    // Calculate global filtered score
    const visionCategories = ['neural_vision_v0', 'behavior_vision_v0'];
    const categoryScores = [];

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


    if (categoryScores.length > 0) {
      const globalAverage = categoryScores.reduce((a, b) => a + b, 0) / categoryScores.length;
      row._tempFilteredScore = globalAverage;
    } else {
      row._tempFilteredScore = null;
    }
  });

  // Apply colors for recalculated benchmarks
  const allBenchmarkIds = Array.from(hierarchyMap.keys());
  const recalculatedBenchmarks = new Set();

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
  toggleFilteredScoreColumn
};

// Make main functions globally available for compatibility
window.applyCombinedFilters = applyCombinedFilters;
window.resetAllFilters = resetAllFilters;
window.updateFilteredScores = updateFilteredScores;
window.toggleFilteredScoreColumn = toggleFilteredScoreColumn;
