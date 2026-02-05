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
    // Initialize wayback timestamp filter if datetime_range data is available and feature is enabled
    if (window.LeaderboardConstants?.ENABLE_WAYBACK_SLIDER && ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
      const waybackSection = document.getElementById('waybackTimestampSection');
      const waybackSliderContainer = document.querySelector('#waybackTimestampFilter .slider-container');
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
          // Disable min handle if frozen (check if function exists from range-filters.js)
          if (typeof window.shouldFreezeMinHandle === 'function' && window.shouldFreezeMinHandle('waybackTimestamp')) {
            minHandle.style.cursor = 'not-allowed';
            minHandle.style.opacity = '0.6';
            minHandle.classList.add('handle-disabled');
          }
        }

        // Set date input values and disable min input if frozen
        const minDate = new Date(ranges.datetime_range.min_unix * 1000);
        const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
        waybackDateMin.value = minDate.toISOString().split('T')[0];
        waybackDateMax.value = maxDate.toISOString().split('T')[0];
        // Set max attribute to today's date to prevent selecting future dates
        const today = new Date();
        waybackDateMax.max = today.toISOString().split('T')[0];
        // Disable min date input if frozen
        if (typeof window.shouldFreezeMinHandle === 'function' && window.shouldFreezeMinHandle('waybackTimestamp')) {
          waybackDateMin.disabled = true;
          waybackDateMin.style.cursor = 'not-allowed';
          waybackDateMin.style.opacity = '0.6';
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
