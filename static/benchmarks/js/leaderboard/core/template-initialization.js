// Template initialization
// This handles Django data parsing and initial setup

function initializeLeaderboardFromTemplate() {
  
  try {
    // Parse data from Django
    let rowData, columnDefs, benchmarkGroups, benchmarkTree, filterOptions;
    
    try {
      rowData = JSON.parse(window.DJANGO_DATA.row_data);
      columnDefs = JSON.parse(window.DJANGO_DATA.column_defs);
      benchmarkGroups = JSON.parse(window.DJANGO_DATA.benchmark_groups);
      benchmarkTree = JSON.parse(window.DJANGO_DATA.benchmark_tree);
      filterOptions = JSON.parse(window.DJANGO_DATA.filter_options);
      benchmarkMetadata = JSON.parse(window.DJANGO_DATA.benchmark_metadata);
      benchmarkIds = JSON.parse(window.DJANGO_DATA.benchmark_ids);

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
      return; // Stop if data parsing fails
    }
    
    // Make data globally available
    window.benchmarkTree = benchmarkTree;
    window.originalRowData = rowData;
    window.filterOptions = filterOptions;
    window.benchmarkMetadata = benchmarkMetadata;
    
    window.benchmarkIds = benchmarkIds;
    window.benchmarkStimuliMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkStimuliMetaMap);
    window.benchmarkDataMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkDataMetaMap);
    window.benchmarkMetricMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkMetricMetaMap);

    // Set up range sliders with correct max values
    const ranges = filterOptions || {};
    if (ranges.parameter_ranges?.max) {
      document.getElementById('paramCountMin').max = ranges.parameter_ranges.max;
      document.getElementById('paramCountMax').max = ranges.parameter_ranges.max;
      document.getElementById('paramCountMax').value = ranges.parameter_ranges.max;
      
      // Update slider container data attributes
      const paramSliderContainer = document.querySelector('#paramCountMin').closest('.filter-group')?.querySelector('.slider-container');
      if (paramSliderContainer) {
        paramSliderContainer.dataset.max = ranges.parameter_ranges.max;
        const maxHandle = paramSliderContainer.querySelector('.handle-max');
        if (maxHandle) {
          maxHandle.dataset.value = ranges.parameter_ranges.max;
        }
      }
    }
    if (ranges.size_ranges?.max) {
      document.getElementById('modelSizeMin').max = ranges.size_ranges.max;
      document.getElementById('modelSizeMax').max = ranges.size_ranges.max;
      document.getElementById('modelSizeMax').value = ranges.size_ranges.max;
      
      // Update slider container data attributes
      const modelSizeSliderContainer = document.querySelector('#modelSizeMin').closest('.filter-group')?.querySelector('.slider-container');
      if (modelSizeSliderContainer) {
        modelSizeSliderContainer.dataset.max = ranges.size_ranges.max;
        const maxHandle = modelSizeSliderContainer.querySelector('.handle-max');
        if (maxHandle) {
          maxHandle.dataset.value = ranges.size_ranges.max;
        }
      }
    }
    if (ranges.stimuli_ranges?.max) {
      document.getElementById('stimuliCountMin').max = ranges.stimuli_ranges.max;
      document.getElementById('stimuliCountMax').max = ranges.stimuli_ranges.max;
      document.getElementById('stimuliCountMax').value = ranges.stimuli_ranges.max;
      
      // Update slider container data attributes
      const stimuliSliderContainer = document.querySelector('#stimuliCountMin').closest('.filter-group')?.querySelector('.slider-container');
      if (stimuliSliderContainer) {
        stimuliSliderContainer.dataset.max = ranges.stimuli_ranges.max;
        const maxHandle = stimuliSliderContainer.querySelector('.handle-max');
        if (maxHandle) {
          maxHandle.dataset.value = ranges.stimuli_ranges.max;
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
  }
}

function setupUIComponents() {
  // Setup UI elements
  const panel = document.getElementById('advancedFiltersPanel');
  const treeContainer = document.getElementById('benchmarkFilterPanel');
  const container = document.querySelector('.leaderboard-container');
  const advancedFilterBtn = document.getElementById('advancedFilterBtn');
  const layoutToggleBtn = document.getElementById('toggleLayoutBtn');
  
  // Render benchmark tree
  if (typeof renderBenchmarkTree === 'function') {
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
  }, 100);
  
  // Initial badge count update
  setTimeout(() => {
    if (typeof window.updateAllCountBadges === 'function') {
      window.updateAllCountBadges();
    }
  }, 200);
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
  
    console.log('Excluded benchmarks after initialization:', [...window.filteredOutBenchmarks]);
  }, 200);
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
  }, 300);
  
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
  }, 500);
}

// Export for global access
window.LeaderboardTemplateInitialization = {
  initializeLeaderboardFromTemplate
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeLeaderboardFromTemplate);