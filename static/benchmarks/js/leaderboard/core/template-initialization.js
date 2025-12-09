// Template initialization
// This handles Django data parsing and initial setup

function initializeLeaderboardFromTemplate() {
  
  try {
    // Parse data from Django
    let rowData, columnDefs, benchmarkGroups, benchmarkTree, filterOptions, excludedBenchmarks;
    
    try {
      rowData = JSON.parse(window.DJANGO_DATA.row_data);
      columnDefs = JSON.parse(window.DJANGO_DATA.column_defs);
      benchmarkGroups = JSON.parse(window.DJANGO_DATA.benchmark_groups);
      benchmarkTree = JSON.parse(window.DJANGO_DATA.benchmark_tree);
      filterOptions = JSON.parse(window.DJANGO_DATA.filter_options);
      benchmarkMetadata = JSON.parse(window.DJANGO_DATA.benchmark_metadata);
      benchmarkIds = JSON.parse(window.DJANGO_DATA.benchmark_ids);
      excludedBenchmarks = JSON.parse(window.DJANGO_DATA.excluded_benchmarks || '[]');

      let modelMetadataMap, benchmarkMetadataMap;
      try {
        modelMetadataMap = JSON.parse(window.DJANGO_DATA.model_metadata_map);
      } catch (e) {
        console.warn('No model_metadata_map provided:', e);
        modelMetadataMap = {};
      }
      benchmarkMetadataMap = {};
      benchmarkMetadata.forEach(entry => {
        benchmarkMetadataMap[entry.identifier] = entry;
      });
      window.modelMetadataMap = modelMetadataMap;
      window.benchmarkMetadataMap = benchmarkMetadataMap;

    } catch (e) {
      console.error('Error parsing data:', e);
      // Hide loading animation on error
      if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.hide) {
        LoadingAnimation.hide();
      }
      return; // Stop if data parsing fails
    }
    
    // Clear URL parameters for language domain to ensure clean state
    const domain = window.DJANGO_DATA?.domain || 'vision';
    if (domain === 'language' && window.location.search) {
      const newURL = window.location.pathname;
      window.history.replaceState({}, '', newURL);
    }
    
    // Make data globally available
    window.benchmarkTree = benchmarkTree;
    window.originalRowData = rowData;
    window.filterOptions = filterOptions;
    window.benchmarkMetadata = benchmarkMetadata;
    
    // Expand excluded benchmarks to include all descendants
    // This ensures parent benchmarks and all their children are treated the same
    const expandedExcluded = new Set(excludedBenchmarks);
    function addDescendants(nodes, shouldAdd) {
      if (!nodes) return;
      nodes.forEach(node => {
        if (shouldAdd || excludedBenchmarks.includes(node.id)) {
          expandedExcluded.add(node.id);
          // All descendants of an excluded node should also be marked excluded
          if (node.children) {
            addDescendants(node.children, true);
          }
        } else if (node.children) {
          addDescendants(node.children, false);
        }
      });
    }
    addDescendants(benchmarkTree, false);
    window.excludedBenchmarks = expandedExcluded;
    
    window.benchmarkIds = benchmarkIds;
    window.benchmarkStimuliMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkStimuliMetaMap);
    window.benchmarkDataMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkDataMetaMap);
    window.benchmarkMetricMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkMetricMetaMap);
    window.benchmarkBibtexMap = JSON.parse(window.DJANGO_DATA.benchmark_bibtex_map);

    // Set up range sliders with correct max values
    const ranges = filterOptions || {};
    if (ranges.parameter_ranges?.max) {
      // Without advanced filters in language, these getElementByIds will be null resulting in console errors
      const paramCountMin = document.getElementById('paramCountMin');
      const paramCountMax = document.getElementById('paramCountMax');
      // Here, and subsequent if statements, we perform a null check to avoid console errors
      // `if (variable)` is a null check.
      if (paramCountMin) paramCountMin.max = ranges.parameter_ranges.max;
      if (paramCountMax) {
        paramCountMax.max = ranges.parameter_ranges.max;
        paramCountMax.value = ranges.parameter_ranges.max;
      }
      
      // Update slider container data attributes
      if (paramCountMin) {
        const paramSliderContainer = paramCountMin.closest('.filter-group')?.querySelector('.slider-container');
        if (paramSliderContainer) {
          paramSliderContainer.dataset.max = ranges.parameter_ranges.max;
          const maxHandle = paramSliderContainer.querySelector('.handle-max');
          if (maxHandle) {
            maxHandle.dataset.value = ranges.parameter_ranges.max;
          }
        }
      }
    }
    if (ranges.size_ranges?.max) {
      const modelSizeMin = document.getElementById('modelSizeMin');
      const modelSizeMax = document.getElementById('modelSizeMax');
      if (modelSizeMin) modelSizeMin.max = ranges.size_ranges.max;
      if (modelSizeMax) {
        modelSizeMax.max = ranges.size_ranges.max;
        modelSizeMax.value = ranges.size_ranges.max;
      }
      
      // Update slider container data attributes
      if (modelSizeMin) {
        const modelSizeSliderContainer = modelSizeMin.closest('.filter-group')?.querySelector('.slider-container');
        if (modelSizeSliderContainer) {
          modelSizeSliderContainer.dataset.max = ranges.size_ranges.max;
          const maxHandle = modelSizeSliderContainer.querySelector('.handle-max');
          if (maxHandle) {
            maxHandle.dataset.value = ranges.size_ranges.max;
          }
        }
      }
    }
    if (ranges.stimuli_ranges?.max) {
      const stimuliCountMin = document.getElementById('stimuliCountMin');
      const stimuliCountMax = document.getElementById('stimuliCountMax');
      if (stimuliCountMin) stimuliCountMin.max = ranges.stimuli_ranges.max;
      if (stimuliCountMax) {
        stimuliCountMax.max = ranges.stimuli_ranges.max;
        stimuliCountMax.value = ranges.stimuli_ranges.max;
      }
      
      // Update slider container data attributes
      if (stimuliCountMin) {
        const stimuliSliderContainer = stimuliCountMin.closest('.filter-group')?.querySelector('.slider-container');
        if (stimuliSliderContainer) {
          stimuliSliderContainer.dataset.max = ranges.stimuli_ranges.max;
          const maxHandle = stimuliSliderContainer.querySelector('.handle-max');
          if (maxHandle) {
            maxHandle.dataset.value = ranges.stimuli_ranges.max;
          }
        }
      }
    }
    
    // Initialize grid
    if (typeof initializeGrid === 'function') {
      initializeGrid(rowData, columnDefs, benchmarkGroups);
    }
    
    setupUIComponents();
    setupFilters();
    setupEventHandlers();
    
    // Setup report issue functionality
    if (typeof window.LeaderboardReportIssue?.setupReportIssue === 'function') {
      window.LeaderboardReportIssue.setupReportIssue();
    }
    
  } catch (error) {
    console.error('Error during grid initialization:', error);
    // Hide loading animation on error
    if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.hide) {
      LoadingAnimation.hide();
    }
  }
}

function setupUIComponents() {
  // Setup UI elements
  const panel = document.getElementById('advancedFiltersPanel');
  const treeContainer = document.getElementById('benchmarkFilterPanel');
  const container = document.querySelector('.leaderboard-container');
  const advancedFilterBtn = document.getElementById('advancedFilterBtn');
  const layoutToggleBtn = document.getElementById('toggleLayoutBtn');
  
  // Render benchmark tree (only if elements exist - they don't exist for language domain)
  if (typeof renderBenchmarkTree === 'function' && treeContainer) {
    renderBenchmarkTree(treeContainer, window.benchmarkTree);
  }
  
  if (typeof populateFilterDropdowns === 'function') {
    populateFilterDropdowns(window.filterOptions);
  }
  
  if (typeof setupDropdownHandlers === 'function') {
    setupDropdownHandlers();
  }
  
  if (typeof setupBenchmarkCheckboxes === 'function') {
    setupBenchmarkCheckboxes(window.filterOptions);
  }
  
  setTimeout(() => {
    initializeDualHandleSliders();
  }, 10);
  
  // Initial badge count update
  setTimeout(() => {
    if (typeof window.updateAllCountBadges === 'function') {
      window.updateAllCountBadges();
    }
  }, 20);
}

function setupFilters() {
  // Initialize benchmark filters from URL or use defaults
  setTimeout(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const hasExplicitBenchmarks = urlParams.has('benchmark_regions') ||
                                   urlParams.has('benchmark_species') ||
                                   urlParams.has('benchmark_tasks') ||
                                   urlParams.has('public_data_only') ||
                                   urlParams.has('excluded_benchmarks');
  
    // Parse URL filters first (this will set checkbox states if URL params exist)
    if (typeof parseURLFilters === 'function') {
      parseURLFilters();
    }
    
    // Always rebuild exclusion set based on current checkbox states
    window.filteredOutBenchmarks = new Set();
    const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
    allCheckboxes.forEach(cb => {
      if (!cb.checked) {
        window.filteredOutBenchmarks.add(cb.value);
      }
    });
    
    // Recalculate baseline scores to exclude the default-excluded benchmarks
    // This ensures the Global Score on initial load correctly excludes these benchmarks
    if (window.excludedBenchmarks && window.excludedBenchmarks.size > 0) {
      setTimeout(() => {
        recalculateBaselineScores();
      }, 50);
    }
  }, 20);
}

// Recalculate baseline scores to properly exclude the default-excluded benchmarks
// This modifies originalRowData so that the "baseline" Global Score is correct
// It also preserves the true original values so they can be restored when benchmarks are re-added
function recalculateBaselineScores() {
  if (!window.originalRowData || !window.benchmarkTree || !window.excludedBenchmarks) return;
  
  const hierarchyMap = window.buildHierarchyFromTree(window.benchmarkTree);
  const excludedBenchmarks = window.filteredOutBenchmarks || new Set();
  
  // Store the true original values BEFORE modifying (for restoring when benchmarks are re-added)
  // Only do this once on initial load
  if (!window.trueOriginalRowData) {
    window.trueOriginalRowData = JSON.parse(JSON.stringify(window.originalRowData));
  }
  
  // Recalculate scores for each row
  window.originalRowData.forEach(row => {
    // Process benchmarks from leaves up to parents (using shared utility)
    const allBenchmarkIds = Array.from(hierarchyMap.keys());
    const benchmarksByDepth = allBenchmarkIds
      .map(id => ({ id, depth: window.LeaderboardHierarchyUtils.getDepthLevel(id, hierarchyMap) }))
      .sort((a, b) => a.depth - b.depth);
    
    benchmarksByDepth.forEach(({ id: benchmarkId }) => {
      const children = hierarchyMap.get(benchmarkId) || [];
      
      if (children.length === 0) {
        // Leaf benchmark: mark as X if excluded
        if (excludedBenchmarks.has(benchmarkId) && row[benchmarkId]) {
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: 'X',
            color: '#e0e1e2'
          };
        }
      } else {
        // Parent benchmark: recalculate average from non-excluded children (using shared utility)
        const childScores = [];
        const childInfo = [];
        
        children.forEach(childId => {
          // Skip if child is explicitly excluded OR if its entire subtree is excluded
          if (excludedBenchmarks.has(childId) || window.LeaderboardHierarchyUtils.isFullyExcluded(childId, hierarchyMap, excludedBenchmarks)) return;
          
          if (row[childId]) {
            const childScore = row[childId].value;
            const hasValidScore = childScore !== null && childScore !== undefined && 
                                 childScore !== '' && childScore !== 'X' &&
                                 !isNaN(parseFloat(childScore));
            childInfo.push({ childId, childScore, hasValidScore });
          }
        });
        
        const hasAnyValidScores = childInfo.some(info => info.hasValidScore);
        
        childInfo.forEach(({ childScore, hasValidScore }) => {
          if (hasValidScore) {
            childScores.push(parseFloat(childScore));
          } else if (hasAnyValidScores && (childScore === 'X' || childScore === '')) {
            // Treat X as 0 only if there are other valid scores (normal X, not fully excluded)
            childScores.push(0);
          }
        });
        
        // Determine if this column should be dropped out
        let shouldDropOut = childScores.length === 0 || !hasAnyValidScores;
        
        if (shouldDropOut) {
          if (row[benchmarkId]) {
            row[benchmarkId] = {
              ...row[benchmarkId],
              value: 'X',
              color: '#e0e1e2'
            };
          }
        } else if (row[benchmarkId]) {
          const average = childScores.reduce((a, b) => a + b, 0) / childScores.length;
          row[benchmarkId] = {
            ...row[benchmarkId],
            value: parseFloat(average.toFixed(3))
          };
        }
      }
    });
    
    // Recalculate average_vision_v0 (Global Score) from neural and behavior (using shared utility)
    const visionCategories = ['neural_vision_v0', 'behavior_vision_v0'];
    const categoryScores = [];
    
    visionCategories.forEach(category => {
      // Skip if explicitly excluded OR if its entire subtree is excluded
      if (excludedBenchmarks.has(category) || window.LeaderboardHierarchyUtils.isFullyExcluded(category, hierarchyMap, excludedBenchmarks)) return;
      
      if (row[category]) {
        const score = row[category].value;
        if (score !== null && score !== undefined && score !== '') {
          if (score === 'X') {
            // Treat X as 0 (normal X, model has no data)
            categoryScores.push(0);
          } else {
            const numVal = typeof score === 'string' ? parseFloat(score) : score;
            if (!isNaN(numVal)) {
              categoryScores.push(numVal);
            } else {
              categoryScores.push(0);
            }
          }
        }
      }
    });
    
    if (row['average_vision_v0']) {
      if (categoryScores.length > 0) {
        const globalAverage = categoryScores.reduce((a, b) => a + b, 0) / categoryScores.length;
        row['average_vision_v0'] = {
          ...row['average_vision_v0'],
          value: parseFloat(globalAverage.toFixed(3))
        };
      } else {
        // All categories are excluded - mark global score as X
        row['average_vision_v0'] = {
          ...row['average_vision_v0'],
          value: 'X',
          color: '#e0e1e2'
        };
      }
    }
  });
  
  // Recalculate colors for parent benchmarks based on NEW score distribution
  // This ensures colors reflect the new min/max ranges after exclusions
  const allBenchmarkIds = Array.from(hierarchyMap.keys());
  const parentBenchmarkIds = allBenchmarkIds.filter(bid => {
    const children = hierarchyMap.get(bid) || [];
    return children.length > 0;  // Only parent benchmarks
  });
  
  // Also include global score (average_vision_v0) if it exists
  const globalScoreId = 'average_vision_v0';
  if (!parentBenchmarkIds.includes(globalScoreId) && 
      window.originalRowData.length > 0 && 
      window.originalRowData[0][globalScoreId]) {
    parentBenchmarkIds.push(globalScoreId);
  }
  
  // Recalculate colors for each parent benchmark
  parentBenchmarkIds.forEach(benchmarkId => {
    if (window.LeaderboardColorUtils && window.LeaderboardColorUtils.recalculateColorsForBenchmark) {
      window.LeaderboardColorUtils.recalculateColorsForBenchmark(
        window.originalRowData,
        benchmarkId,
        hierarchyMap
      );
    }
  });
  
  // Recalculate ranks based on the new global scores
  recalculateRanks(window.originalRowData);
  
  // Update the grid with recalculated data
  if (window.globalGridApi) {
    window.globalGridApi.setGridOption('rowData', window.originalRowData);
    window.globalGridApi.refreshCells({ force: true });
  }
}

// Recalculate ranks based on the current global scores (average_vision_v0)
// This ensures ranks reflect the recalculated scores after excluding benchmarks
function recalculateRanks(rowData) {
  if (!rowData || rowData.length === 0) return;
  
  // Extract global scores for each model
  const modelScores = rowData.map(row => {
    const globalScore = row.average_vision_v0;
    let score = null;
    let isX = false;
    
    if (globalScore) {
      const val = globalScore.value;
      if (val === 'X' || val === '' || val === null || val === undefined) {
        isX = true;
      } else {
        const numVal = typeof val === 'string' ? parseFloat(val) : val;
        if (!isNaN(numVal)) {
          score = numVal;
        } else {
          isX = true;
        }
      }
    } else {
      isX = true;
    }
    
    return { row, score, isX, modelName: row.model?.name || row.id || '' };
  });
  
  // Sort: valid scores descending, then X at the bottom
  modelScores.sort((a, b) => {
    // X values go to the bottom
    if (a.isX && !b.isX) return 1;
    if (!a.isX && b.isX) return -1;
    if (a.isX && b.isX) return a.modelName.localeCompare(b.modelName);
    
    // Sort by score descending
    if (b.score !== a.score) return b.score - a.score;
    
    // Tiebreaker: model name
    return a.modelName.localeCompare(b.modelName);
  });
  
  // Assign ranks based on rounded scores (2 decimal places, matching display)
  let currentRank = 1;
  let previousRoundedScore = null;
  let tiedCount = 0;
  
  modelScores.forEach((item, index) => {
    if (item.isX) {
      // All X get the same rank (last valid rank + tied count + 1)
      return;
    }
    
    // Round to 2 decimal places for comparison (matching display format)
    const roundedScore = Math.round(item.score * 100) / 100;
    
    // Compare rounded scores for tie detection
    if (index === 0 || roundedScore !== previousRoundedScore) {
      if (tiedCount > 0) {
        currentRank += tiedCount;
      }
      tiedCount = 1;
      item.row.rank = currentRank;
    } else {
      // Tie - same rounded score, use same rank as previous
      tiedCount++;
      item.row.rank = modelScores[index - 1].row.rank;
    }
    
    previousRoundedScore = roundedScore;
  });
  
  // Assign rank to all X models (after all valid ones)
  const xRank = currentRank + tiedCount;
  modelScores.forEach(item => {
    if (item.isX) {
      item.row.rank = xRank;
    }
  });
  
  console.log('[recalculateRanks] Recalculated ranks for', rowData.length, 'models');
}

function setupEventHandlers() {
  // Setup filter action buttons
  const resetBtn = document.getElementById('resetAllFiltersBtn');
  
  if (resetBtn && typeof resetAllFilters === 'function') {
    resetBtn.addEventListener('click', () => {
      resetAllFilters();
    });
  }
  
  // Setup CSV export functionality
  if (typeof window.LeaderboardCSVExport?.setupCSVExport === 'function') {
    window.LeaderboardCSVExport.setupCSVExport();
  }
  
  // Setup citation export functionality
  if (typeof window.LeaderboardCitationExport?.setupCitationExport === 'function') {
    window.LeaderboardCitationExport.setupCitationExport();
  }
  
  // Setup model search functionality
  if (typeof window.LeaderboardSearch?.setupSearchHandlers === 'function') {
    window.LeaderboardSearch.setupSearchHandlers();
  }
  
  // Setup the reset benchmarks link
  setTimeout(() => {
    const resetLink = document.getElementById('resetBenchmarksLink');
    if (resetLink) {
      resetLink.addEventListener('click', (e) => {
        e.preventDefault();
        
        // Check all checkboxes (include all benchmarks by default)
        const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
        allCheckboxes.forEach(cb => {
          cb.checked = true;  // Check everything including engineering
        });
        
        // Rebuild the exclusion set
        window.filteredOutBenchmarks = new Set();
        allCheckboxes.forEach(cb => {
          if (!cb.checked) {
            window.filteredOutBenchmarks.add(cb.value);
          }
        });
        
        // Trigger update
        if (typeof applyCombinedFilters === 'function') {
          applyCombinedFilters();
        }
      });
    }
  }, 30);
  
  setupLayoutToggleHandlers();
}

function setupLayoutToggleHandlers() {
  const panel = document.getElementById('advancedFiltersPanel');
  const container = document.querySelector('.leaderboard-container');
  const advancedFilterBtn = document.getElementById('advancedFilterBtn');
  const layoutToggleBtn = document.getElementById('toggleLayoutBtn');
  
  // Enhanced layout toggle functionality
  let isPanelVisible = false;
  
  // Check for saved preference and set initial state
  const savedLayout = localStorage.getItem('leaderboardLayout');
  if (savedLayout === 'sidebar') {
    container.classList.add('sidebar-mode');
    panel.classList.add('hidden');
    panel.style.display = '';
    isPanelVisible = false;
    updateToggleButton('sidebar');
  } else {
    container.classList.remove('sidebar-mode');
    panel.classList.add('hidden');
    panel.style.display = '';
    isPanelVisible = false;
    updateToggleButton('horizontal');
  }
  
  // Function to update toggle button text and icon
  function updateToggleButton(mode) {
    const toggleText = layoutToggleBtn?.querySelector('.toggle-text');
    
    if (toggleText) {
      if (mode === 'sidebar') {
        toggleText.textContent = 'Full Width Mode';
      } else {
        toggleText.textContent = 'Sidebar Mode';
      }
    }
  }
  
  // Function to position panel correctly
  function positionPanel(mode) {
    if (mode === 'horizontal') {
      const breadcrumb = document.querySelector('.leaderboard-breadcrumb');
      if (breadcrumb && breadcrumb.nextSibling !== panel) {
        breadcrumb.insertAdjacentElement('afterend', panel);
      }
    } else {
      if (container.lastElementChild !== panel) {
        container.appendChild(panel);
      }
    }
  }
  
  // Set initial position
  positionPanel(savedLayout === 'sidebar' ? 'sidebar' : 'horizontal');
  
  layoutToggleBtn?.addEventListener('click', () => {
    const isSidebar = container.classList.toggle('sidebar-mode');
    
    if (isSidebar) {
      positionPanel('sidebar');
      panel.classList.remove('hidden');
      panel.style.display = 'block';
      isPanelVisible = true;
      updateToggleButton('sidebar');
      localStorage.setItem('leaderboardLayout', 'sidebar');
      container.classList.remove('filters-hidden');
    } else {
      positionPanel('horizontal');
      panel.classList.remove('hidden');
      panel.style.display = 'block';
      isPanelVisible = true;
      updateToggleButton('horizontal');
      localStorage.setItem('leaderboardLayout', 'horizontal');
      container.classList.remove('filters-hidden');
    }
  });
  
  // Advanced filter button
  if (advancedFilterBtn) {
    const newAdvancedFilterBtn = advancedFilterBtn.cloneNode(true);
    advancedFilterBtn.parentNode.replaceChild(newAdvancedFilterBtn, advancedFilterBtn);
    
    newAdvancedFilterBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      
      if (!container.classList.contains('sidebar-mode')) {
        isPanelVisible = !isPanelVisible;
        if (isPanelVisible) {
          panel.classList.remove('hidden');
          panel.style.display = 'block';
          panel.style.visibility = 'visible';
          panel.style.opacity = '1';
          panel.style.border = '';
          panel.style.zIndex = '';
        } else {
          panel.classList.add('hidden');
          panel.style.display = '';
          panel.style.visibility = '';
          panel.style.opacity = '';
        }
      } else {
        isPanelVisible = !isPanelVisible;
        if (isPanelVisible) {
          panel.classList.remove('hidden');
          panel.style.display = 'block';
          container.classList.remove('filters-hidden');
        } else {
          panel.classList.add('hidden');
          panel.style.display = '';
          container.classList.add('filters-hidden');
        }
      }
    });
  }
  
  // Final URL parsing with delay to avoid conflicts
  setTimeout(() => {
    if (typeof parseURLFilters === 'function') {
      parseURLFilters();
      if (!container.classList.contains('sidebar-mode') && !isPanelVisible) {
        panel.classList.add('hidden');
      }
    }
  }, 50);
}

// Export for global access
window.LeaderboardTemplateInitialization = {
  initializeLeaderboardFromTemplate
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeLeaderboardFromTemplate);