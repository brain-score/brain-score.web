// Tour configuration for the AG-Grid leaderboard
// This file defines all tutorial steps and can be easily extended for future features

window.tourConfigs = window.tourConfigs || {};

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
        description: 'These benchmarks measure how well models predict neural responses recorded from brain areas like V1, V2, V4, and IT cortex. Click to expand and see individual neural benchmarks.',
        position: 'bottom',
        beforeShow: () => {
          // Ensure neural column is visible
          if (window.globalGridApi) {
            window.globalGridApi.applyColumnState({
              state: [{ colId: 'neural_vision_v0', hide: false }]
            });
          }
        }
      }
    },
    {
      element: '.expandable-header.behavior',
      popover: {
        title: 'Behavioral Benchmarks',
        description: 'These benchmarks test how well models predict human behavioral responses on tasks like object recognition and visual reasoning. Click to expand for detailed behavioral benchmarks.',
        position: 'bottom',
        beforeShow: () => {
          // Ensure behavior column is visible
          if (window.globalGridApi) {
            window.globalGridApi.applyColumnState({
              state: [{ colId: 'behavior_vision_v0', hide: false }]
            });
          }
        }
      }
    },
    {
      element: '.expandable-header.engineering',
      popover: {
        title: 'Engineering Benchmarks',
        description: 'Engineering benchmarks test practical computer vision capabilities like ImageNet classification. These are excluded from the global Brain-Score but help understand model capabilities.',
        position: 'bottom',
        beforeShow: () => {
          // Ensure engineering column is visible
          if (window.globalGridApi) {
            window.globalGridApi.applyColumnState({
              state: [{ colId: 'engineering_vision_v0', hide: false }]
            });
          }
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

// Advanced features tour (for future expansion)
window.tourConfigs.advancedFeaturesTour = {
  steps: [
    {
      element: '#benchmarkFilterPanel',
      popover: {
        title: 'Benchmark Selection',
        description: 'Select which benchmarks to include in your analysis. Uncheck benchmarks to exclude them from score calculations and see how rankings change.',
        position: 'left'
      }
    },
    {
      element: '.filter-dropdown',
      popover: {
        title: 'Model Property Filters',
        description: 'Filter models by their properties like architecture (ResNet, Vision Transformer), parameter count, model size, and more.',
        position: 'top'
      }
    },
    {
      element: '.range-filter',
      popover: {
        title: 'Range Filters',
        description: 'Use these sliders to filter models by numerical properties like parameter count or model size. Drag the handles to set your desired range.',
        position: 'top'
      }
    },
    {
      element: '#toggleLayoutBtn',
      popover: {
        title: 'Layout Modes',
        description: 'Switch between horizontal (filters above) and sidebar (filters on right) layouts for optimal viewing on different screen sizes.',
        position: 'top'
      }
    }
  ],
  options: {
    animate: true,
    allowClose: true,
    showProgress: true
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