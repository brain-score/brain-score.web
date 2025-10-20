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

    window.benchmarkIds = benchmarkIds;
    window.benchmarkStimuliMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkStimuliMetaMap);
    window.benchmarkDataMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkDataMetaMap);
    window.benchmarkMetricMetaMap = JSON.parse(window.DJANGO_DATA.benchmarkMetricMetaMap);

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
    
    // Initialize wayback timestamp filter if datetime_range data is available
    if (ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
      const waybackSection = document.getElementById('waybackTimestampSection');
      const waybackSliderContainer = document.querySelector('#waybackTimestampSection .slider-container');
      const waybackDateMin = document.getElementById('waybackDateMin');
      const waybackDateMax = document.getElementById('waybackDateMax');

      if (waybackSection && waybackSliderContainer && waybackDateMin && waybackDateMax) {
        // Show the wayback section
        waybackSection.style.display = 'block';

        // Set slider range using Unix timestamps
        waybackSliderContainer.dataset.min = ranges.datetime_range.min_unix;
        waybackSliderContainer.dataset.max = ranges.datetime_range.max_unix;

        // Set initial handle positions
        const minHandle = waybackSliderContainer.querySelector('.handle-min');
        const maxHandle = waybackSliderContainer.querySelector('.handle-max');
        if (minHandle && maxHandle) {
          minHandle.dataset.value = ranges.datetime_range.min_unix;
          maxHandle.dataset.value = ranges.datetime_range.max_unix;
        }

        // Set date input values
        const minDate = new Date(ranges.datetime_range.min_unix * 1000);
        const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
        waybackDateMin.value = minDate.toISOString().split('T')[0];
        waybackDateMax.value = maxDate.toISOString().split('T')[0];

        console.log('Wayback timestamp filter initialized:', {
          min_unix: ranges.datetime_range.min_unix,
          max_unix: ranges.datetime_range.max_unix,
          min_date: waybackDateMin.value,
          max_date: waybackDateMax.value
        });
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

    console.log('Excluded benchmarks after initialization:', [...window.filteredOutBenchmarks]);
  }, 20);
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
  setupWaybackPanel();
}

// Global variables for panel state management
let isPanelVisible = false;
let isWaybackPanelVisible = false;

function setupLayoutToggleHandlers() {
  const panel = document.getElementById('advancedFiltersPanel');
  const container = document.querySelector('.leaderboard-container');
  const advancedFilterBtn = document.getElementById('advancedFilterBtn');
  const layoutToggleBtn = document.getElementById('toggleLayoutBtn');

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

      // Close wayback panel if open
      const waybackPanel = document.getElementById('waybackPanel');
      if (waybackPanel && !waybackPanel.classList.contains('hidden')) {
        waybackPanel.classList.add('hidden');
        waybackPanel.style.display = '';
        isWaybackPanelVisible = false;
        
        // Update wayback button text
        const waybackBtn = document.getElementById('waybackBtn');
        const textWrapper = waybackBtn?.querySelector('.text-wrapper');
        if (textWrapper) {
          textWrapper.textContent = 'Wayback';
        }
      }

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

function setupWaybackPanel() {
  const waybackBtn = document.getElementById('waybackBtn');
  const waybackPanel = document.getElementById('waybackPanel');
  const advancedFiltersPanel = document.getElementById('advancedFiltersPanel');
  const advancedFilterBtn = document.getElementById('advancedFilterBtn');
  const waybackStartDate = document.getElementById('waybackStartDate');
  const waybackEndDate = document.getElementById('waybackEndDate');
  const applyBtn = document.getElementById('applyWaybackBtn');
  const resetBtn = document.getElementById('resetWaybackBtn');
  
  if (!waybackBtn || !waybackPanel) return;
  
  // Initialize date inputs with min/max from filterOptions
  const ranges = window.filterOptions || {};
  let minUnix, maxUnix;
  
  if (ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
    minUnix = ranges.datetime_range.min_unix;
    maxUnix = ranges.datetime_range.max_unix;
    
    const minDate = new Date(minUnix * 1000);
    const maxDate = new Date(maxUnix * 1000);
    
    waybackStartDate.value = minDate.toISOString().split('T')[0];
    waybackEndDate.value = maxDate.toISOString().split('T')[0];
    waybackStartDate.min = minDate.toISOString().split('T')[0];
    waybackStartDate.max = maxDate.toISOString().split('T')[0];
    waybackEndDate.min = minDate.toISOString().split('T')[0];
    waybackEndDate.max = maxDate.toISOString().split('T')[0];
  }
  
  // Wayback button click handler - toggle panel
  waybackBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Close Advanced Filters if open
    if (!advancedFiltersPanel.classList.contains('hidden')) {
      advancedFiltersPanel.classList.add('hidden');
      advancedFiltersPanel.style.display = '';
      isPanelVisible = false;
      
      const textWrapper = advancedFilterBtn?.querySelector('.text-wrapper');
      if (textWrapper) {
        textWrapper.textContent = 'Advanced Filters';
      }
    }
    
    // Toggle wayback panel
    isWaybackPanelVisible = !isWaybackPanelVisible;
    if (isWaybackPanelVisible) {
      waybackPanel.classList.remove('hidden');
      
      const textWrapper = waybackBtn.querySelector('.text-wrapper');
      if (textWrapper) {
        textWrapper.textContent = 'Hide Wayback';
      }
    } else {
      waybackPanel.classList.add('hidden');
      
      const textWrapper = waybackBtn.querySelector('.text-wrapper');
      if (textWrapper) {
        textWrapper.textContent = 'Wayback';
      }
    }
  });
  
  // Apply button - set wayback filter and trigger filtering
  applyBtn?.addEventListener('click', () => {
    const startDate = waybackStartDate.value;
    const endDate = waybackEndDate.value;
    
    if (!startDate || !endDate) {
      console.warn('Both start and end dates are required');
      return;
    }
    
    // Convert dates to Unix timestamps
    const startUnix = Math.floor(new Date(startDate).getTime() / 1000);
    const endUnix = Math.floor(new Date(endDate).getTime() / 1000);
    
    // Update window.activeFilters directly
    if (!window.activeFilters) {
      window.activeFilters = {};
    }
    window.activeFilters.min_wayback_timestamp = startUnix;
    window.activeFilters.max_wayback_timestamp = endUnix;
    
    // Set values in the hidden Advanced Filters wayback inputs (for sync)
    const waybackDateMin = document.getElementById('waybackDateMin');
    const waybackDateMax = document.getElementById('waybackDateMax');
    
    if (waybackDateMin && waybackDateMax) {
      waybackDateMin.value = startDate;
      waybackDateMax.value = endDate;
    }
    
    // Trigger the existing filter system
    if (typeof window.applyCombinedFilters === 'function') {
      window.applyCombinedFilters();
    }
    
    console.log(`Wayback filter applied: ${startDate} to ${endDate} (Unix: ${startUnix} to ${endUnix})`);
  });
  
  // Reset button - reset to full date range
  resetBtn?.addEventListener('click', () => {
    if (minUnix && maxUnix) {
      const minDate = new Date(minUnix * 1000);
      const maxDate = new Date(maxUnix * 1000);
      
      waybackStartDate.value = minDate.toISOString().split('T')[0];
      waybackEndDate.value = maxDate.toISOString().split('T')[0];
      
      // Update window.activeFilters to full range
      if (!window.activeFilters) {
        window.activeFilters = {};
      }
      window.activeFilters.min_wayback_timestamp = minUnix;
      window.activeFilters.max_wayback_timestamp = maxUnix;
      
      // Also reset the hidden Advanced Filters wayback inputs
      const waybackDateMin = document.getElementById('waybackDateMin');
      const waybackDateMax = document.getElementById('waybackDateMax');
      
      if (waybackDateMin && waybackDateMax) {
        waybackDateMin.value = minDate.toISOString().split('T')[0];
        waybackDateMax.value = maxDate.toISOString().split('T')[0];
      }
      
      // Trigger the existing filter system
      if (typeof window.applyCombinedFilters === 'function') {
        window.applyCombinedFilters();
      }
      
      console.log('Wayback filter reset to full range');
    }
  });
}

// Export for global access
window.LeaderboardTemplateInitialization = {
  initializeLeaderboardFromTemplate
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeLeaderboardFromTemplate);
