// Tour configuration for the AG-Grid leaderboard
// This file defines all tutorial steps and can be easily extended for future features

window.tourConfigs = window.tourConfigs || {};

// Helper Functions for Tour
// Expand header columns to show child benchmarks
function expandBenchmarkHeaders(columnIds) {
  columnIds.forEach(columnId => {
    // Find the header cell by column ID
    const headerCell = document.querySelector(`.ag-header-cell[col-id="${columnId}"]`);
    if (headerCell) {
      const expandToggle = headerCell.querySelector('.expand-toggle');
      if (expandToggle && expandToggle.textContent === '▾') {
        // Only click if it's currently collapsed (showing downward arrow)
        expandToggle.click();
      }
    }
  });
}

// Step State Management for Interactive Tour
// Tracks DOM changes to restore state when navigating backward
window.tourStepState = {
  currentStep: 0,
  states: new Map(),
  
  // Record the state before making changes
  recordState(stepIndex, stateData) {
    this.states.set(stepIndex, stateData);
  },
  
  // Restore state when going backward
  restoreState(stepIndex) {
    const state = this.states.get(stepIndex);
    if (!state) return;
    
    // Restore collapsed/expanded states
    if (state.collapsedNodes) {
      state.collapsedNodes.forEach(nodeSelector => {
        const node = document.querySelector(nodeSelector);
        if (node && !node.classList.contains('collapsed')) {
          const toggle = node.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
      });
    }
    
    // Restore checkbox states
    if (state.checkboxStates) {
      state.checkboxStates.forEach((checked, selector) => {
        const checkbox = document.querySelector(selector);
        if (checkbox && checkbox.checked !== checked) {
          checkbox.checked = checked;
          
          // Trigger change event
          const changeEvent = new Event('change', { bubbles: true });
          checkbox.dispatchEvent(changeEvent);
        }
      });
      
      // Update grid after checkbox changes
      setTimeout(() => {
        if (window.updateExclusions) window.updateExclusions();
        if (window.applyCombinedFilters) window.applyCombinedFilters();
      }, 100);
    }
    
    // Restore AG-Grid column visibility states
    if (state.columnStates && window.globalGridApi) {
      const columnStateArray = [];
      state.columnStates.forEach((visible, colId) => {
        columnStateArray.push({ colId, hide: !visible });
      });
      
      if (columnStateArray.length > 0) {
        window.globalGridApi.applyColumnState({ state: columnStateArray });
      }
    }
    
    // Restore column expansion states
    if (state.expandedColumns && window.columnExpansionState) {
      // First, collapse all columns that should be collapsed
      const keyColumns = ['neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0', 'V1_v0', 'V2_v0', 'V4_v0', 'IT_v0'];
      keyColumns.forEach(colId => {
        if (!state.expandedColumns.has(colId) && window.columnExpansionState.get(colId) === true) {
          // Column should be collapsed but is currently expanded
          const headerCell = document.querySelector(`.ag-header-cell[col-id="${colId}"]`);
          if (headerCell) {
            const expandToggle = headerCell.querySelector('.expand-toggle');
            if (expandToggle && expandToggle.textContent === '▴') {
              expandToggle.click();
            }
          }
        }
      });
    }
  },
  
  // Get current DOM state for recording
  getCurrentState() {
    const collapsedNodes = [];
    const checkboxStates = new Map();
    const columnStates = new Map();
    const expandedColumns = new Set();
    
    // Record expanded/collapsed benchmark nodes
    document.querySelectorAll('.benchmark-node.collapsed').forEach(node => {
      const input = node.querySelector('input[value]');
      if (input) {
        collapsedNodes.push(`input[value="${input.value}"]`);
      }
    });
    
    // Record checkbox states for key benchmarks
    const keyCheckboxes = [
      'input[value="neural_vision_v0"]',
      'input[value="V1_v0"]', 
      'input[value="FreemanZiemba2013.V1-pls_v2"]',
      'input[value="behavior_vision_v0"]',
      'input[value="engineering_vision_v0"]'
    ];
    
    keyCheckboxes.forEach(selector => {
      const checkbox = document.querySelector(selector);
      if (checkbox) {
        checkboxStates.set(selector, checkbox.checked);
      }
    });
    
    // Record AG-Grid column visibility states for key columns
    if (window.globalGridApi) {
      const keyColumns = ['neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0', 'V1_v0', 'V2_v0', 'V4_v0', 'IT_v0'];
      keyColumns.forEach(colId => {
        const column = window.globalGridApi.getColumn(colId);
        if (column) {
          columnStates.set(colId, column.isVisible());
        }
      });
      
      // Record expanded column states
      if (window.columnExpansionState) {
        keyColumns.forEach(colId => {
          if (window.columnExpansionState.get(colId) === true) {
            expandedColumns.add(colId);
          }
        });
      }
    }
    
    return { collapsedNodes, checkboxStates, columnStates, expandedColumns };
  },
  
  // Clear all tracked state
  clear() {
    this.states.clear();
    this.currentStep = 0;
  }
};

// ------------------------------------------------------------
// Basic Tour
// ------------------------------------------------------------
window.tourConfigs.defaultTour = {
  steps: [
    {
      element: '.ag-cell[col-id="rank"]',
      popover: {
        title: 'Model Rankings',
        description: 'Models are ranked by their overall performance across neural and behavioral benchmarks. Higher-ranking models better predict brain responses.',
        position: 'right'
      }
    },
    {
      element: '.ag-cell[col-id="model"]',
      popover: {
        title: 'Model Information',
        description: 'Click on any model name to view detailed information, including the research paper, code repository, and submission details. The submitter information shows who contributed the model.',
        position: 'right'
      }
    },
    {
      element: '.expandable-header.average',
      popover: {
        title: 'Global Score',
        description: 'This shows the overall Brain-Score - an average across neural and behavioral benchmarks. This is the primary metric for ranking models. Engineering benchmarks are excluded from this global score.',
        position: 'bottom'
      }
    },
    {
      element: '.expandable-header.neural',
      popover: {
        title: 'Neural Benchmarks',
        description: 'These benchmarks measure how well models predict neural responses recorded from brain areas like V1, V2, V4, and IT cortex. Notice the expand toggle (▾) on the right - this lets you see individual neural benchmarks.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Ensure neural column is visible
        if (window.globalGridApi) {
          window.globalGridApi.applyColumnState({
            state: [{ colId: 'neural_vision_v0', hide: false }]
          });
        }
      }
    },
    {
      element: '.expandable-header.neural .expand-toggle',
      popover: {
        title: 'Expansion Toggle',
        description: 'This toggle button (▾) expands the Neural column to show individual brain area benchmarks like V1, V2, V4, and IT. I\'ll click it now to demonstrate!',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
      }
    },
    {
      element: '.ag-header-cell[col-id="V1_v0"]',
      popover: {
        title: 'Neural Brain Areas Revealed',
        description: 'Perfect! I just expanded the Neural column and now you can see all four major neural benchmark categories: V1 (primary visual cortex), V2 (secondary visual cortex), V4 (color and shape processing), and IT (inferotemporal cortex for object recognition). Each tests how well models predict responses from different brain regions.',
        position: 'top'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Expand neural benchmarks to show V1, V2, V4, IT columns
        expandBenchmarkHeaders(['neural_vision_v0']);
        
      }
    },
    {
      element: '.expandable-header.behavior',
      popover: {
        title: 'Behavioral Benchmarks',
        description: 'These benchmarks test how well models predict human behavioral responses on tasks like object recognition and visual reasoning. Click to expand for detailed behavioral benchmarks.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Ensure behavior column is visible
        if (window.globalGridApi) {
          window.globalGridApi.applyColumnState({
            state: [{ colId: 'behavior_vision_v0', hide: false }]
          });
        }
      }
    },
    {
      element: '.expandable-header.engineering',
      popover: {
        title: 'Engineering Benchmarks',
        description: 'Engineering benchmarks test practical computer vision capabilities like ImageNet classification. These are excluded from the global Brain-Score but help understand model capabilities.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Ensure engineering column is visible
        if (window.globalGridApi) {
          window.globalGridApi.applyColumnState({
            state: [{ colId: 'engineering_vision_v0', hide: false }]
          });
        }
      }
    },
    {
      element: '.score-pill',
      popover: {
        title: 'Performance Scores',
        description: 'Each colored pill shows a model\'s performance on a benchmark (0-1 scale, higher is better). Colors indicate relative performance - darker colors mean better scores. "X" means the benchmark wasn\'t run for that model.',
        position: 'top'
      }
    },
    {
      element: '#modelSearchInput',
      popover: {
        title: 'Search Models',
        description: 'Search for specific models by name or research group. This helps you quickly find models you\'re interested in comparing.',
        position: 'bottom'
      }
    },
    {
      element: '#advancedFilterBtn',
      popover: {
        title: 'Advanced Filtering',
        description: 'Click here to access powerful filtering options. You can filter by model properties (architecture, parameter count), benchmark characteristics (brain region, species), and more.',
        position: 'bottom'
      }
    }
  ],
  
  // Global configuration for the tour
  options: {
    animate: true,
    allowClose: true,
    overlayClickNext: false,
    stagePadding: 8,
    showProgress: true,
    showButtons: ['next', 'previous', 'close'],
    nextBtnText: 'Next →',
    prevBtnText: '← Previous',
    doneBtnText: 'Finish',
    closeBtnText: '✕',
    theme: 'leaderboard-theme'
  }
};

// ------------------------------------------------------------
// Advanced Filters Tour
// ------------------------------------------------------------
window.tourConfigs.interactiveBenchmarkTour = {
  steps: [
    {
      element: '#advancedFilterBtn',
      popover: {
        title: 'Interactive Filter Demo',
        description: 'Let\'s explore how benchmark filtering works! I\'ll show you the advanced filters and demonstrate how they change the leaderboard in real-time.',
        position: 'bottom'
      },
      beforeShow: () => {
        // Ensure advanced filters are closed initially
        const panel = document.getElementById('advancedFiltersPanel');
        if (panel && !panel.classList.contains('hidden')) {
          document.getElementById('advancedFilterBtn').click();
        }
      }
    },
    {
      element: '#advancedFilterBtn',
      popover: {
        title: 'Opening Advanced Filters',
        description: 'I\'m now opening the advanced filter panel for you. Watch as it reveals powerful filtering options.',
        position: 'bottom'
      },
      beforeShow: () => {
        // Open the advanced filters panel
        const panel = document.getElementById('advancedFiltersPanel');
        if (panel && panel.classList.contains('hidden')) {
          document.getElementById('advancedFilterBtn').click();
        }
      }
    },
    {
      element: '#benchmarkFilterPanel',
      popover: {
        title: 'Benchmark Selection Tree',
        description: 'Here\'s the benchmark filter tree. Each checkbox controls whether that benchmark is included in the leaderboard. Currently, all benchmarks except Engineering are selected (notice Engineering is unchecked by default).',
        position: 'left'
      }
    },
    {
      element: '.vision-parent',
      popover: {
        title: 'Vision Benchmarks Category',
        description: 'Vision Benchmarks include Neural and Behavioral tests. These contribute to the global Brain-Score. Let me expand this category to show you the individual benchmarks.',
        position: 'left'
      },
      beforeShow: () => {
        // Expand the vision parent if collapsed
        const visionParent = document.querySelector('.vision-parent');
        if (visionParent && visionParent.classList.contains('collapsed')) {
          const toggle = visionParent.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
      }
    },
    {
      element: '.vision-parent input[value="neural_vision_v0"]',
      popover: {
        title: 'Neural Benchmarks',
        description: 'Neural benchmarks measure how well models predict brain responses. I\'ll expand this category to show you specific neural benchmarks like V1, V2, V4, and IT cortex predictions.',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Expand neural benchmarks
        const neuralNode = document.querySelector('input[value="neural_vision_v0"]').closest('.benchmark-node');
        if (neuralNode && neuralNode.classList.contains('collapsed')) {
          const toggle = neuralNode.querySelector('.tree-toggle');
          if (toggle) {
            toggle.click();
          }
        }
      }
    },
    {
      element: 'input[value="V1_v0"]',
      popover: {
        title: 'V1 Neural Benchmarks',
        description: 'V1 benchmarks test predictions of primary visual cortex responses. Let me expand this category to show specific V1 tests, then deselect one to demonstrate real-time changes.',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Expand V1 benchmarks
        const v1Node = document.querySelector('input[value="V1_v0"]').closest('.benchmark-node');
        if (v1Node && v1Node.classList.contains('collapsed')) {
          const toggle = v1Node.querySelector('.tree-toggle');
          if (toggle) {
            toggle.click();
          }
        }
      }
    },
    {
      element: 'input[value="FreemanZiemba2013.V1-pls_v2"]',
      popover: {
        title: 'Specific V1 Benchmark',
        description: 'This is the FreemanZiemba2013.V1-pls benchmark - a specific test of V1 texture processing. I\'ll deselect it now to show you how the leaderboard updates in real-time!',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Ensure neural_vision is expanded (backup safety check)
        const neuralNode = document.querySelector('input[value="neural_vision_v0"]').closest('.benchmark-node');
        if (neuralNode && neuralNode.classList.contains('collapsed')) {
          const toggle = neuralNode.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
        
        // Ensure V1 is expanded (backup safety check)
        const v1Node = document.querySelector('input[value="V1_v0"]').closest('.benchmark-node');
        if (v1Node && v1Node.classList.contains('collapsed')) {
          const toggle = v1Node.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
        
        // Small delay to ensure expansions complete
        setTimeout(() => {
          // Store original state for restoration
          const freemanCheckbox = document.querySelector('input[value="FreemanZiemba2013.V1-pls_v2"]');
          if (freemanCheckbox) {
            window._tourOriginalFreemanState = freemanCheckbox.checked;
          }
          
          // Uncheck the Freeman-Ziemba benchmark properly
          if (freemanCheckbox && freemanCheckbox.checked) {
            
            // Set checkbox state
            freemanCheckbox.checked = false;
            
            // Trigger change event manually
            const changeEvent = new Event('change', { bubbles: true });
            freemanCheckbox.dispatchEvent(changeEvent);
            
            // Call update functions with a small delay to ensure DOM is updated
            setTimeout(() => {
              if (window.updateExclusions) {
                window.updateExclusions();
              }
              if (window.applyCombinedFilters) {
                window.applyCombinedFilters();
              }
            }, 100);
          }
        }, 200); // Give time for expansions to complete
      }
    },
    {
      element: '.ag-row[row-index="0"] .ag-cell[col-id="neural_vision_v0"]',
      popover: {
        title: 'Watch the Neural Scores Change!',
        description: 'Notice how the Neural column scores have recalculated! By removing the FreemanZiemba2013.V1-pls benchmark, we\'ve changed how V1 performance is measured, affecting each model\'s neural score. Look at the changed values in this entire column!',
        position: 'left'
      }
    },
          {
        element: '.ag-header-cell[col-id="filtered_score"] .ag-header-cell-text', 
        popover: {
          title: 'Global Brain-Score Updated',
          description: 'The global Brain-Score (Average column) has also recalculated! Since we removed a neural benchmark, the overall brain-relevance scores have changed. Some models may have moved up or down in ranking.',
          position: 'bottom'
        }
      },
    {
      element: '.vision-parent input[value="behavior_vision_v0"]',
      popover: {
        title: 'Now Let\'s Try Behavioral Benchmarks',
        description: 'Behavioral benchmarks are already expanded. Let me show you what happens when we deselect all behavioral benchmarks to isolate neural performance.',
        position: 'left'  
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Restore the Freeman benchmark first
        const freemanCheckbox = document.querySelector('input[value="FreemanZiemba2013.V1-pls_v2"]');
        if (freemanCheckbox && !freemanCheckbox.checked && window._tourOriginalFreemanState) {
          // Set checkbox state
          freemanCheckbox.checked = true;
          
          // Trigger change event manually
          const changeEvent = new Event('change', { bubbles: true });
          freemanCheckbox.dispatchEvent(changeEvent);
          
          // Call update functions with a small delay to ensure DOM is updated
          setTimeout(() => {
            if (window.updateExclusions) {
              window.updateExclusions();
            }
            if (window.applyCombinedFilters) {
              window.applyCombinedFilters();
            }
          }, 100);
        }
        
        // Expand behavioral benchmarks if needed
        const behaviorNode = document.querySelector('input[value="behavior_vision_v0"]').closest('.benchmark-node');
        if (behaviorNode && behaviorNode.classList.contains('collapsed')) {
          const toggle = behaviorNode.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
      }
    },
    {
      element: '.expandable-header.behavior',
      popover: {
        title: 'Notice the Changes!',
        description: 'Look! The Behavioral column is now dimmed/hidden because we unchecked it. The global scores (Average column) have also recalculated to only include Neural benchmarks. Rankings may have changed too!',
        position: 'top'
      }
    },
    {
      element: '.ag-header-cell[col-id="filtered_score"] .ag-header-cell-text',
      popover: {
        title: 'Recalculated Global Scores',
        description: 'The global Brain-Score (Filtered Score column) now only includes Neural benchmarks since we disabled Behavioral ones. Notice how some models\' scores and rankings have changed. This is the power of benchmark filtering!',
        position: 'bottom'
      }
    },
    {
      element: '.engineering-parent',
      popover: {
        title: 'Engineering Benchmarks',
        description: 'Engineering benchmarks (like ImageNet) are excluded by default because they don\'t measure brain-like processing. Let me show you what happens when we include them.',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Expand engineering parent if collapsed
        const engineeringParent = document.querySelector('.engineering-parent');
        if (engineeringParent && engineeringParent.classList.contains('collapsed')) {
          const toggle = engineeringParent.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
      }
    },
    {
      element: 'input[value="engineering_vision_v0"]',
      popover: {
        title: 'Including Engineering Benchmarks',
        description: 'I\'m now checking Engineering benchmarks. Watch as new columns appear in the leaderboard, but note they don\'t affect the global Brain-Score!',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Check engineering benchmarks
        const engineeringCheckbox = document.querySelector('input[value="engineering_vision_v0"]');
        if (engineeringCheckbox && !engineeringCheckbox.checked) {
          // Set checkbox state
          engineeringCheckbox.checked = true;
          
          // Trigger change event manually
          const changeEvent = new Event('change', { bubbles: true });
          engineeringCheckbox.dispatchEvent(changeEvent);
          
          // Call update functions with a small delay to ensure DOM is updated
          setTimeout(() => {
            if (window.updateExclusions) {
              window.updateExclusions();
            }
            if (window.applyCombinedFilters) {
              window.applyCombinedFilters();
            }
          }, 100);
        }
      }
    },
    {
      element: '.expandable-header.engineering',
      popover: {
        title: 'Engineering Columns Appeared!',
        description: 'New Engineering benchmark columns are now visible! These show computer vision performance (like ImageNet accuracy) but don\'t contribute to the Brain-Score ranking.',
        position: 'top'
      }
    },
    {
      element: '.expandable-header.average',
      popover: {
        title: 'Global Score Unchanged',
        description: 'Notice that the global Brain-Score (Average column) didn\'t change when we added Engineering benchmarks. Only Neural and Behavioral benchmarks contribute to brain-relevance scoring.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        if (!window.tourStepState.states.has(stepIndex)) {
          window.tourStepState.recordState(stepIndex, window.tourStepState.getCurrentState());
        }
        
        // Restore behavioral benchmarks for final demonstration
        const behaviorCheckbox = document.querySelector('input[value="behavior_vision_v0"]');
        if (behaviorCheckbox && !behaviorCheckbox.checked) {
          // Set checkbox state
          behaviorCheckbox.checked = true;
          
          // Trigger change event manually
          const changeEvent = new Event('change', { bubbles: true });
          behaviorCheckbox.dispatchEvent(changeEvent);
          
          // Call update functions with a small delay to ensure DOM is updated
          setTimeout(() => {
            if (window.updateExclusions) {
              window.updateExclusions();
            }
            if (window.applyCombinedFilters) {
              window.applyCombinedFilters();
            }
          }, 100);
        }
      }
    },
    {
      element: '#benchmarkFilterPanel',
      popover: {
        title: 'Powerful Filtering Complete!',
        description: 'You\'ve seen how benchmark filtering works! You can select/deselect any combination of benchmarks to customize your analysis. Try experimenting with different combinations to explore model capabilities.',
        position: 'left'
      }
    },
    {
      element: '#resetAllFiltersBtn',
      popover: {
        title: 'Reset When Needed',
        description: 'Use this Reset button to restore all filters to their default state anytime. The tour is complete - now you know how to use benchmark filtering to customize your analysis!',
        position: 'top'
      }
    },
    {
      element: 'input[value="behavior_vision_v0"]',
      popover: {
        title: 'Deselecting Behavioral Benchmarks',
        description: 'Now I\'ll uncheck Behavioral benchmarks to show you how this affects the leaderboard. Watch the columns and scores change in real-time!',
        position: 'left'
      },
      beforeShow: () => {
        // Store original state for restoration later
        window._tourOriginalBehaviorState = true;
        
        // Uncheck behavioral benchmarks properly
        const behaviorCheckbox = document.querySelector('input[value="behavior_vision_v0"]');
        if (behaviorCheckbox && behaviorCheckbox.checked) {
          // Set checkbox state
          behaviorCheckbox.checked = false;
          
          // Trigger change event manually
          const changeEvent = new Event('change', { bubbles: true });
          behaviorCheckbox.dispatchEvent(changeEvent);
          
          // Call update functions with a small delay to ensure DOM is updated
          setTimeout(() => {
            if (window.updateExclusions) {
              window.updateExclusions();
            }
            if (window.applyCombinedFilters) {
              window.applyCombinedFilters();
            }
          }, 100);
        }
      }
    }
  ],
  
  options: {
    animate: true,
    allowClose: true,
    overlayClickNext: false,
    stagePadding: 8,
    showProgress: true,
    showButtons: ['next', 'previous', 'close'],
    nextBtnText: 'Next →',
    prevBtnText: '← Previous', 
    doneBtnText: 'Finish Demo',
    closeBtnText: '✕'
  }
};

// Step handlers for complex interactions
window.tourConfigs.stepHandlers = {
  // Show advanced filters panel
  showAdvancedFilters: () => {
    const btn = document.getElementById('advancedFilterBtn');
    const panel = document.getElementById('advancedFiltersPanel');
    if (btn && panel && panel.classList.contains('hidden')) {
      btn.click();
    }
  },

  // Expand specific benchmark column
  expandBenchmark: (benchmarkId) => {
    if (window.globalGridApi) {
      const allCols = window.globalGridApi.getAllGridColumns();
      const targetCol = allCols.find(col => col.getColId() === benchmarkId);
      if (targetCol) {
        const colDef = targetCol.getColDef();
        const toggle = document.querySelector(`[data-benchmark="${benchmarkId}"] .expand-toggle`);
        if (toggle && colDef.context?.parentField) {
          toggle.click();
        }
      }
    }
  },

  // Set optimal layout for tour
  setTourLayout: () => {
    const container = document.querySelector('.leaderboard-container');
    const panel = document.getElementById('advancedFiltersPanel');
    
    // Ensure we're in horizontal mode for better tour experience
    if (container && container.classList.contains('sidebar-mode')) {
      const toggleBtn = document.getElementById('toggleLayoutBtn');
      if (toggleBtn) {
        toggleBtn.click();
      }
    }
    
    // Hide filters panel initially
    if (panel && !panel.classList.contains('hidden')) {
      const advancedBtn = document.getElementById('advancedFilterBtn');
      if (advancedBtn) {
        advancedBtn.click();
      }
    }
  },

  // Ensure key columns are visible
  showKeyColumns: () => {
    if (window.globalGridApi) {
      window.globalGridApi.applyColumnState({
        state: [
          { colId: 'model', hide: false },
          { colId: 'rank', hide: false },
          { colId: 'average_vision_v0', hide: false },
          { colId: 'neural_vision_v0', hide: false },
          { colId: 'behavior_vision_v0', hide: false },
          { colId: 'engineering_vision_v0', hide: false }
        ]
      });
    }
  }
}; 