// Leaderboard initialization script
// This module handles the initialization of the leaderboard with all its components

document.addEventListener('DOMContentLoaded', function() {
  console.log('🚀 DOM loaded, starting leaderboard initialization...');
  
  try {
    // Parse data from Django template
    let rowData, columnDefs, benchmarkGroups, benchmarkTree, filterOptions;
    
    try {
      const rowDataEl = document.getElementById('rowData');
      const columnDefsEl = document.getElementById('columnDefs');
      const benchmarkGroupsEl = document.getElementById('benchmarkGroups');
      const benchmarkTreeEl = document.getElementById('benchmarkTree');
      const filterOptionsEl = document.getElementById('filterOptions');
      const benchmarkMetadataEl = document.getElementById('benchmarkMetadata');
      const benchmarkIdsEl = document.getElementById('benchmarkIds');
      
      // Parse required data with error handling
      // Handle Django's escapejs filter which double-escapes JSON
      const unescapeEscapedJson = (text) => {
        if (!text) return '';
        // Unescape the JavaScript-escaped JSON
        try {
          return JSON.parse(`"${text}"`);
        } catch (e) {
          return text;
        }
      };
      
      const rowDataText = rowDataEl ? unescapeEscapedJson(rowDataEl.textContent.trim()) : '';
      const columnDefsText = columnDefsEl ? unescapeEscapedJson(columnDefsEl.textContent.trim()) : '';
      const benchmarkGroupsText = benchmarkGroupsEl ? unescapeEscapedJson(benchmarkGroupsEl.textContent.trim()) : '';
      const benchmarkTreeText = benchmarkTreeEl ? unescapeEscapedJson(benchmarkTreeEl.textContent.trim()) : '';
      const filterOptionsText = filterOptionsEl ? unescapeEscapedJson(filterOptionsEl.textContent.trim()) : '';
      
      console.log('Raw JSON data lengths:', {
        rowData: rowDataText.length,
        columnDefs: columnDefsText.length,
        benchmarkGroups: benchmarkGroupsText.length,
        benchmarkTree: benchmarkTreeText.length,
        filterOptions: filterOptionsText.length
      });
      
      console.log('First 200 chars of rowData:', JSON.stringify(rowDataText.substring(0, 200)));
      console.log('First 200 chars of columnDefs:', JSON.stringify(columnDefsText.substring(0, 200)));
      
      // Check if elements exist
      console.log('Elements found:', {
        rowDataEl: !!rowDataEl,
        columnDefsEl: !!columnDefsEl,
        benchmarkGroupsEl: !!benchmarkGroupsEl,
        benchmarkTreeEl: !!benchmarkTreeEl,
        filterOptionsEl: !!filterOptionsEl
      });
      
      // Safe JSON parsing with fallbacks
      try {
        rowData = rowDataText && rowDataText !== '' ? JSON.parse(rowDataText) : [];
      } catch (e) {
        console.warn('Failed to parse rowData:', e);
        rowData = [];
      }
      
      try {
        columnDefs = columnDefsText && columnDefsText !== '' ? JSON.parse(columnDefsText) : [];
      } catch (e) {
        console.warn('Failed to parse columnDefs:', e);
        columnDefs = [];
      }
      
      try {
        benchmarkGroups = benchmarkGroupsText && benchmarkGroupsText !== '' ? JSON.parse(benchmarkGroupsText) : {};
      } catch (e) {
        console.warn('Failed to parse benchmarkGroups:', e);
        benchmarkGroups = {};
      }
      
      try {
        benchmarkTree = benchmarkTreeText && benchmarkTreeText !== '' ? JSON.parse(benchmarkTreeText) : [];
      } catch (e) {
        console.warn('Failed to parse benchmarkTree:', e);
        benchmarkTree = [];
      }
      
      try {
        filterOptions = filterOptionsText && filterOptionsText !== '' ? JSON.parse(filterOptionsText) : {};
      } catch (e) {
        console.warn('Failed to parse filterOptions:', e);
        filterOptions = {};
      }
      
      let benchmarkMetadata = [];
      let benchmarkIds = {};
      
      try {
        const benchmarkMetadataText = benchmarkMetadataEl ? unescapeEscapedJson(benchmarkMetadataEl.textContent.trim()) : '';
        benchmarkMetadata = benchmarkMetadataText && benchmarkMetadataText !== '' ? JSON.parse(benchmarkMetadataText) : [];
      } catch (e) {
        console.warn('Failed to parse benchmarkMetadata:', e);
        benchmarkMetadata = [];
      }
      
      try {
        const benchmarkIdsText = benchmarkIdsEl ? unescapeEscapedJson(benchmarkIdsEl.textContent.trim()) : '';
        benchmarkIds = benchmarkIdsText && benchmarkIdsText !== '' ? JSON.parse(benchmarkIdsText) : {};
      } catch (e) {
        console.warn('Failed to parse benchmarkIds:', e);
        benchmarkIds = {};
      }
      
      // Optional data with fallbacks
      let modelMetadataMap = {};
      try {
        const modelMetadataMapEl = document.getElementById('modelMetadataMap');
        if (modelMetadataMapEl && modelMetadataMapEl.textContent.trim()) {
          const modelMetadataMapText = unescapeEscapedJson(modelMetadataMapEl.textContent.trim());
          modelMetadataMap = modelMetadataMapText ? JSON.parse(modelMetadataMapText) : {};
        }
      } catch (e) {
        console.warn('No model_metadata_map provided:', e);
        modelMetadataMap = {};
      }
      
      benchmarkMetadataMap = {};
      benchmarkMetadata.forEach(entry => {
        benchmarkMetadataMap[entry.identifier] = entry;
      });
      
      // Set global variables
      window.benchmarkTree = benchmarkTree;
      window.originalRowData = rowData;
      window.filterOptions = filterOptions;
      window.benchmarkMetadata = benchmarkMetadata;
      window.benchmarkIds = benchmarkIds;
      window.modelMetadataMap = modelMetadataMap;
      window.benchmarkMetadataMap = benchmarkMetadataMap;
      
      // Debug the benchmark tree structure
      console.log('🌳 BenchmarkTree structure:', {
        length: benchmarkTree?.length,
        firstFew: benchmarkTree?.slice(0, 3)?.map(node => ({
          id: node.id || node.identifier,
          name: node.name,
          childrenCount: node.children?.length || 0,
          firstChildIds: node.children?.slice(0, 3)?.map(child => child.id || child.identifier)
        }))
      });
      
      // Debug: Look for average_vision_v0 specifically
      const avgVisionNode = benchmarkTree?.find(node => 
        (node.id === 'average_vision_v0' || node.identifier === 'average_vision_v0')
      );
      console.log('🎯 Found average_vision_v0 node:', avgVisionNode);
      
      // Initialize global state objects early
      if (!window.activeFilters) {
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
      }
      
      if (!window.filteredOutBenchmarks) {
        window.filteredOutBenchmarks = new Set();
      }
      
      if (!window.columnExpansionState) {
        window.columnExpansionState = new Map();
      }
      
      // Set additional metadata maps with fallbacks
      window.benchmarkStimuliMetaMap = {};
      window.benchmarkDataMetaMap = {};
      window.benchmarkMetricMetaMap = {};
      
      try {
        const stimuliEl = document.getElementById('benchmarkStimuliMetaMap');
        const stimuliText = stimuliEl ? unescapeEscapedJson(stimuliEl.textContent.trim()) : '';
        window.benchmarkStimuliMetaMap = stimuliText && stimuliText !== '' ? JSON.parse(stimuliText) : {};
      } catch (e) {
        console.warn('Failed to parse benchmarkStimuliMetaMap:', e);
        window.benchmarkStimuliMetaMap = {};
      }
      
      try {
        const dataEl = document.getElementById('benchmarkDataMetaMap');
        const dataText = dataEl ? unescapeEscapedJson(dataEl.textContent.trim()) : '';
        window.benchmarkDataMetaMap = dataText && dataText !== '' ? JSON.parse(dataText) : {};
      } catch (e) {
        console.warn('Failed to parse benchmarkDataMetaMap:', e);
        window.benchmarkDataMetaMap = {};
      }
      
      try {
        const metricEl = document.getElementById('benchmarkMetricMetaMap');
        const metricText = metricEl ? unescapeEscapedJson(metricEl.textContent.trim()) : '';
        window.benchmarkMetricMetaMap = metricText && metricText !== '' ? JSON.parse(metricText) : {};
      } catch (e) {
        console.warn('Failed to parse benchmarkMetricMetaMap:', e);
        window.benchmarkMetricMetaMap = {};
      }
      
      // Calculate actual max values from the data if parameter_ranges are missing or wrong
      let calculatedRanges = {
        max_param_count: 100,
        max_model_size: 1000,
        max_stimuli_count: 1000
      };
      
      if (rowData && rowData.length > 0) {
        let maxParamCount = 0;
        let maxModelSize = 0;
        
        rowData.forEach(row => {
          if (row.metadata) {
            // Parameter count is usually in millions, so convert from raw count
            const paramCountMillions = (row.metadata.total_parameter_count || 0) / 1_000_000;
            if (paramCountMillions > maxParamCount) {
              maxParamCount = paramCountMillions;
            }
            
            // Model size in MB
            const modelSizeMB = row.metadata.model_size_mb || 0;
            if (modelSizeMB > maxModelSize) {
              maxModelSize = modelSizeMB;
            }
          }
        });
        
        // Round up to reasonable increments and add some buffer
        calculatedRanges.max_param_count = Math.ceil(maxParamCount / 10) * 10 + 10;
        calculatedRanges.max_model_size = Math.ceil(maxModelSize / 100) * 100 + 100;
        
        console.log('📊 Calculated ranges from data:', calculatedRanges);
      }
      
      // Calculate max stimuli count from benchmark metadata
      if (window.benchmarkStimuliMetaMap && Object.keys(window.benchmarkStimuliMetaMap).length > 0) {
        let maxStimuliCount = 0;
        Object.values(window.benchmarkStimuliMetaMap).forEach(stimuliMeta => {
          if (stimuliMeta && stimuliMeta.num_stimuli) {
            const stimuliCount = parseInt(stimuliMeta.num_stimuli);
            if (stimuliCount > maxStimuliCount) {
              maxStimuliCount = stimuliCount;
            }
          }
        });
        
        if (maxStimuliCount > 0) {
          calculatedRanges.max_stimuli_count = Math.ceil(maxStimuliCount / 100) * 100 + 100;
          console.log('📊 Calculated max stimuli count from benchmark metadata:', calculatedRanges.max_stimuli_count);
        }
      }
      
      // Use calculated ranges if filterOptions ranges are missing or seem wrong
      const ranges = filterOptions?.parameter_ranges || {};
      const finalRanges = {
        max_param_count: ranges.max_param_count || calculatedRanges.max_param_count,
        max_model_size: ranges.max_model_size || calculatedRanges.max_model_size,
        max_stimuli_count: ranges.max_stimuli_count || calculatedRanges.max_stimuli_count
      };
      
      console.log('📊 Final parameter ranges to use:', finalRanges);
      console.log('📊 Original filterOptions ranges:', ranges);
      
      // Update parameter count range
      const paramCountMin = document.getElementById('paramCountMin');
      const paramCountMax = document.getElementById('paramCountMax');
      if (paramCountMin && paramCountMax) {
        paramCountMin.max = finalRanges.max_param_count;
        paramCountMax.max = finalRanges.max_param_count;
        paramCountMax.value = finalRanges.max_param_count;
        
        // Update slider container data attributes
        const paramSliderContainer = paramCountMin.closest('.filter-group')?.querySelector('.slider-container');
        if (paramSliderContainer) {
          paramSliderContainer.dataset.max = finalRanges.max_param_count;
          const maxHandle = paramSliderContainer.querySelector('.handle-max');
          if (maxHandle) {
            maxHandle.dataset.value = finalRanges.max_param_count;
          }
        }
        
        console.log('✅ Set param count range to:', finalRanges.max_param_count);
      }
      
      // Update model size range
      const modelSizeMin = document.getElementById('modelSizeMin');
      const modelSizeMax = document.getElementById('modelSizeMax');
      if (modelSizeMin && modelSizeMax) {
        modelSizeMin.max = finalRanges.max_model_size;
        modelSizeMax.max = finalRanges.max_model_size;
        modelSizeMax.value = finalRanges.max_model_size;
        
        // Update slider container data attributes
        const modelSizeSliderContainer = modelSizeMin.closest('.filter-group')?.querySelector('.slider-container');
        if (modelSizeSliderContainer) {
          modelSizeSliderContainer.dataset.max = finalRanges.max_model_size;
          const maxHandle = modelSizeSliderContainer.querySelector('.handle-max');
          if (maxHandle) {
            maxHandle.dataset.value = finalRanges.max_model_size;
          }
        }
        
        console.log('✅ Set model size range to:', finalRanges.max_model_size);
      }
      
      // Update stimuli count range
      const stimuliCountMin = document.getElementById('stimuliCountMin');
      const stimuliCountMax = document.getElementById('stimuliCountMax');
      if (stimuliCountMin && stimuliCountMax) {
        stimuliCountMin.max = finalRanges.max_stimuli_count;
        stimuliCountMax.max = finalRanges.max_stimuli_count;
        stimuliCountMax.value = finalRanges.max_stimuli_count;
        
        // Update slider container data attributes
        const stimuliSliderContainer = stimuliCountMin.closest('.filter-group')?.querySelector('.slider-container');
        if (stimuliSliderContainer) {
          stimuliSliderContainer.dataset.max = finalRanges.max_stimuli_count;
          const maxHandle = stimuliSliderContainer.querySelector('.handle-max');
          if (maxHandle) {
            maxHandle.dataset.value = finalRanges.max_stimuli_count;
          }
        }
        
        console.log('✅ Set stimuli count range to:', finalRanges.max_stimuli_count);
      }

      console.log('✅ All data loaded successfully');
      console.log('rowData count:', rowData.length);
      console.log('columnDefs count:', columnDefs.length);
    } catch (e) {
      console.error('❌ Error parsing data:', e);
      console.warn('🧪 Using test data since Django template data is not available');
      
      // Provide test data for development/debugging
      rowData = [
        {
          model: { name: 'Test Model 1', id: 'test1', submitter: 'Test User' },
          rank: 1,
          runnable_status: 'functional',
          average_vision_v0: { value: 0.85, color: 'rgba(0, 255, 0, 0.5)' },
          metadata: { runnable: true, architecture: 'ResNet', param_count: 25.6 }
        },
        {
          model: { name: 'Test Model 2', id: 'test2', submitter: 'Another User' },
          rank: 2,
          runnable_status: 'issues',
          average_vision_v0: { value: 0.75, color: 'rgba(255, 165, 0, 0.5)' },
          metadata: { runnable: false, architecture: 'VGG', param_count: 138.0 }
        }
      ];
      
      columnDefs = [
        { 
          headerName: 'Model', 
          field: 'model', 
          width: 200, 
          cellRenderer: 'modelCellRenderer',
          pinned: 'left'
        },
        { 
          headerName: 'Rank', 
          field: 'rank', 
          width: 80,
          pinned: 'left'
        },
        { 
          headerName: 'Average Vision', 
          field: 'average_vision_v0', 
          width: 150, 
          cellRenderer: 'scoreCellRenderer',
          headerComponent: 'expandableHeaderComponent',
          context: { benchmarkId: 'average_vision_v0' }
        }
      ];
      
      benchmarkGroups = {
        'average_vision_v0': ['neural_vision_v0', 'behavior_vision_v0']
      };
      
      benchmarkTree = [
        {
          identifier: 'average_vision_v0',
          name: 'Average Vision',
          children: []
        }
      ];
      
      filterOptions = {
        architectures: ['ResNet', 'VGG'],
        model_families: ['CNN'],
        parameter_ranges: {
          max_param_count: 200,
          max_model_size: 1000,
          max_stimuli_count: 1000
        }
      };
      
      window.benchmarkTree = benchmarkTree;
      window.originalRowData = rowData;
      window.filterOptions = filterOptions;
      window.benchmarkMetadata = [];
      window.benchmarkIds = {};
      window.modelMetadataMap = {};
      window.benchmarkMetadataMap = {};
      window.benchmarkStimuliMetaMap = {};
      window.benchmarkDataMetaMap = {};
      window.benchmarkMetricMetaMap = {};
      
      // Initialize global state objects for test data too
      if (!window.activeFilters) {
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
      }
      
      if (!window.filteredOutBenchmarks) {
        window.filteredOutBenchmarks = new Set();
      }
      
      if (!window.columnExpansionState) {
        window.columnExpansionState = new Map();
      }
      
      console.log('✅ Test data loaded successfully');
    }
    
    // Range inputs already set up before grid initialization
    
    // Initialize the grid - EXACTLY like original monolithic file
    console.log('🏗️ Initializing grid...');
    console.log('Data summary:', {
      rowDataCount: rowData.length,
      columnDefsCount: columnDefs.length,
      hasData: rowData.length > 0 && columnDefs.length > 0
    });
    
    // Always call initializeGrid directly - just like the original did
    initializeGrid(rowData, columnDefs, benchmarkGroups);
    
    // Setup UI components
    setupUIComponents(filterOptions, benchmarkTree);
    
    // Setup event handlers
    setupEventHandlers();
    
    // Initialize filters from URL or set defaults
    setTimeout(() => {
      initializeFilters();
      
      // Update count badges after everything is loaded
      setTimeout(() => {
        console.log('🔄 Updating count badges...');
        updateAllCountBadges(); // Call directly like original
        
        // Force refresh count badges even if the update function doesn't work
        setTimeout(() => {
          const countBadges = document.querySelectorAll('[data-parent-field]');
          console.log('🔍 Found count badges:', countBadges.length);
          countBadges.forEach(badge => {
            const parentField = badge.dataset.parentField;
            const countElement = badge.querySelector('.count-value');
            console.log('🔍 Badge details:', { parentField, hasCountElement: !!countElement });
            
            if (countElement && parentField) {
              console.log('🔍 About to call getFilteredLeafCount for:', parentField);
              console.log('🔍 Current state:', {
                benchmarkTree: !!window.benchmarkTree,
                filteredOutBenchmarks: !!window.filteredOutBenchmarks,
                filteredOutSize: window.filteredOutBenchmarks?.size
              });
              const newCount = getFilteredLeafCount(parentField); // Call directly like original
              console.log('🔄 Updating badge count:', { parentField, newCount });
              countElement.textContent = newCount;
            }
          });
        }, 200);
      }, 100);
      
      // Debug: Check state after initialization
      console.log('🔍 Post-initialization state:', {
        filteredOutBenchmarks: Array.from(window.filteredOutBenchmarks || []),
        columnExpansionState: Array.from(window.columnExpansionState?.entries() || []),
        filteredScoreVisible: window.globalGridApi?.getColumn('filtered_score')?.isVisible()
      });
    }, 200);
    
    console.log('🎉 Leaderboard initialization complete!');
    
  } catch (error) {
    console.error('💥 Error during initialization:', error);
  }
});

// Setup UI components - EXACTLY like original monolithic file setup pattern
function setupUIComponents(filterOptions, benchmarkTree) {
  console.log('🎛️ Setting up UI components...');
  
  // Setup filter components - call functions directly like original
  const treeContainer = document.getElementById('benchmarkFilterPanel');
  if (treeContainer) {
    renderBenchmarkTree(treeContainer, benchmarkTree);
  }
  
  populateFilterDropdowns(filterOptions);
  setupDropdownHandlers();
  setupBenchmarkCheckboxes(filterOptions);
  
  // Initialize sliders with small delay like original
  setTimeout(() => {
    initializeDualHandleSliders();
  }, 100);
  
  console.log('✅ UI components setup complete');
}

// Setup event handlers
function setupEventHandlers() {
  console.log('🔗 Setting up event handlers...');
  
  // Advanced filter panel and layout controls
  setupAdvancedFilterPanel();
  setupLayoutControls();
  
  // Filter action buttons
  setupFilterActionButtons();
  
  console.log('✅ Event handlers setup complete');
}

// Setup advanced filter panel
function setupAdvancedFilterPanel() {
  const panel = document.getElementById('advancedFiltersPanel');
  const container = document.querySelector('.leaderboard-container');
  const advancedFilterBtn = document.getElementById('advancedFilterBtn');
  
  if (!panel || !container || !advancedFilterBtn) return;
  
  let isPanelVisible = false;
  
  // Check for saved layout preference
  const savedLayout = localStorage.getItem('leaderboardLayout');
  if (savedLayout === 'sidebar') {
    container.classList.add('sidebar-mode');
    panel.classList.add('hidden');
    isPanelVisible = false;
  } else {
    container.classList.remove('sidebar-mode');
    panel.classList.add('hidden');
    isPanelVisible = false;
  }
  
  // Advanced filter button click handler
  advancedFilterBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (!container.classList.contains('sidebar-mode')) {
      // In horizontal mode, toggle the panel
      isPanelVisible = !isPanelVisible;
      if (isPanelVisible) {
        panel.classList.remove('hidden');
        panel.style.display = 'block';
      } else {
        panel.classList.add('hidden');
        panel.style.display = '';
      }
    } else {
      // In sidebar mode, also toggle visibility
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

// Setup layout controls
function setupLayoutControls() {
  const layoutToggleBtn = document.getElementById('toggleLayoutBtn');
  const container = document.querySelector('.leaderboard-container');
  const panel = document.getElementById('advancedFiltersPanel');
  
  if (!layoutToggleBtn || !container || !panel) return;
  
  let isPanelVisible = false;
  
  // Function to update toggle button text
  function updateToggleButton(mode) {
    const toggleText = layoutToggleBtn.querySelector('.toggle-text');
    if (toggleText) {
      toggleText.textContent = mode === 'sidebar' ? 'Full Width Mode' : 'Sidebar Mode';
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
  
  // Set initial state
  const savedLayout = localStorage.getItem('leaderboardLayout');
  updateToggleButton(savedLayout === 'sidebar' ? 'sidebar' : 'horizontal');
  positionPanel(savedLayout === 'sidebar' ? 'sidebar' : 'horizontal');
  
  // Layout toggle button click handler
  layoutToggleBtn.addEventListener('click', () => {
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
}

// Setup filter action buttons
function setupFilterActionButtons() {
  const resetBtn = document.getElementById('resetAllFiltersBtn');
  const resetBenchmarksLink = document.getElementById('resetBenchmarksLink');
  const copyBibtexBtn = document.getElementById('copyBibtexBtn');
  
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      resetAllFilters(); // Call directly like original
    });
  }
  
  if (resetBenchmarksLink) {
    resetBenchmarksLink.addEventListener('click', (e) => {
      e.preventDefault();
      
      // Check all checkboxes (include all benchmarks by default)
      const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
      allCheckboxes.forEach(cb => {
        cb.checked = true;
      });
      
      // Rebuild the exclusion set
      window.filteredOutBenchmarks = new Set();
      
      // Trigger update (skip column toggle during initialization)
      applyCombinedFilters(true); // Call directly like original
    });
  }
  
  if (copyBibtexBtn) {
    copyBibtexBtn.addEventListener('click', (e) => {
      e.preventDefault();
      copyBibtexToClipboard(); // Call directly like original
    });
  }
}

// Initialize filters from URL or set defaults
function initializeFilters() {
  console.log('🔧 Initializing filters...');
  
  const urlParams = new URLSearchParams(window.location.search);
  const hasExplicitBenchmarks = urlParams.has('benchmark_regions') ||
                                urlParams.has('benchmark_species') ||
                                urlParams.has('benchmark_tasks') ||
                                urlParams.has('public_data_only') ||
                                urlParams.has('excluded_benchmarks');

  // Parse URL filters first - call directly like original
  parseURLFilters();
  
  // If no explicit benchmark filters in URL, use default (include all benchmarks)
  if (!hasExplicitBenchmarks) {
    window.filteredOutBenchmarks = new Set();
  }
  
  // Always rebuild exclusion set based on current checkbox states
  const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  allCheckboxes.forEach(cb => {
    if (!cb.checked) {
      window.filteredOutBenchmarks.add(cb.value);
    }
  });
  
  console.log('✅ Filters initialized');
}

// Data extraction utilities for HTML template
function extractDataFromHTML() {
  // These would be populated by the Django template
  const dataElements = {
    rowData: document.getElementById('rowData'),
    columnDefs: document.getElementById('columnDefs'),
    benchmarkGroups: document.getElementById('benchmarkGroups'),
    benchmarkTree: document.getElementById('benchmarkTree'),
    filterOptions: document.getElementById('filterOptions'),
    benchmarkMetadata: document.getElementById('benchmarkMetadata'),
    benchmarkIds: document.getElementById('benchmarkIds'),
    modelMetadataMap: document.getElementById('modelMetadataMap'),
    benchmarkStimuliMetaMap: document.getElementById('benchmarkStimuliMetaMap'),
    benchmarkDataMetaMap: document.getElementById('benchmarkDataMetaMap'),
    benchmarkMetricMetaMap: document.getElementById('benchmarkMetricMetaMap')
  };
  
  const data = {};
  
  for (const [key, element] of Object.entries(dataElements)) {
    if (element && element.textContent) {
      try {
        data[key] = JSON.parse(element.textContent);
      } catch (e) {
        console.warn(`Error parsing ${key}:`, e);
        data[key] = key === 'modelMetadataMap' ? {} : null;
      }
    } else {
      data[key] = key === 'modelMetadataMap' ? {} : null;
    }
  }
  
  return data;
}

console.log('📦 Leaderboard initialization script loaded');