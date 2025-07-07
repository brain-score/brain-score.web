// Basic Tour Configuration
// This file contains the step-by-step basic tour for first-time users

// Ensure tour configs namespace exists
window.tourConfigs = window.tourConfigs || {};

// Basic Tour - Introduction to the leaderboard features
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
        description: 'Click on any model name to view detailed information, including the research paper, how-to-use instructions, and per-benchmark scores.',
        position: 'right'
      }
    },
    {
      element: '.ag-cell[col-id="runnable_status"]',
      popover: {
        title: 'Model Status',
        description: 'Models become deprecated over time. Green status indicates the model has been recently tested and is runnable. Red status indicates the model has confirmed to be not longer runnable. Grey status indicates the model has not been tested in a while.',
        position: 'right'
      }
    },
    {
      element: '.expandable-header.average',
      popover: {
        title: 'Unfiltered Score',
        description: 'This shows the overall Brain-Score - an average across all neural and behavioral benchmarks. This is the primary metric for ranking models. Engineering benchmarks are excluded from this global score.',
        position: 'bottom'
      }
    },
    {
      element: '.expandable-header.neural',
      popover: {
        title: 'Neural Benchmarks',
        description: 'These benchmarks measure how well models predict neural responses recorded from brain areas like V1, V2, V4, and IT cortex.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Ensure neural column is visible
        if (window.globalGridApi) {
          window.globalGridApi.applyColumnState({
            state: [{ colId: 'neural_vision_v0', hide: false }]
          });
        }
      }
    },
    {
      element: '.expandable-header.neural .benchmark-count .count-value',
      popover: {
        title: 'Expansion Toggle',
        description: 'This count badge shows how many neural benchmarks are in this category and acts as an expand/collapse toggle. Notice the icon - We\'ll click it in the next step to show individual brain area benchmarks in V1, V2, V4, and IT.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
      }
    },
    {
      popover: {
        title: 'Neural Brain Areas Revealed',
        description: 'We just expanded the Neural column. We can now see all four major neural benchmark categories. Each tests how well models predict responses from different brain regions. We can further expand categories to see individual benchmarks.',
        position: 'center'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Expand neural benchmarks to show V1, V2, V4, IT columns
        expandBenchmarkHeaders(['neural_vision_v0']);
      }
    },
    {
      popover: {
        title: 'Expanding V1 Benchmarks',
        description: 'Let\'s expand the V1 column to show individual benchmarks, such as Marques2020, Freeman, and Coggan. Each represents a specific experimental dataset.',
        position: 'center'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Expand V1 to show individual benchmarks
        expandBenchmarkHeaders(['V1_v0']);
      }
    },
    {
      element: '.leaf-header-label [title*="FreemanZiemba2013"]',
      popover: {
        title: 'Individual Benchmark Details',
        description: 'You can click on leaf benchmarks to view detailed information, including the research paper, how-to-use instructions, and all model scores. Each benchmark represents a specific experimental dataset.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Ensure V1 is still expanded (in case user manually collapsed it)
        expandBenchmarkHeaders(['V1_v0']);
        
        // Give a moment for any animations to complete
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve();
          }, 500);
        });
      }
    },
    {
      element: '.expandable-header.behavior',
      popover: {
        title: 'Behavioral Benchmarks',
        description: 'These benchmarks test how well models predict human behavioral responses on tasks like object recognition. Click to expand for detailed behavioral benchmarks.',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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
        description: 'Each colored pill shows a model\'s performance on a benchmark (0-1 scale, higher is better). Colors indicate relative performance - darker colors mean better scores. "X" means the model failed to run the benchmark.',
        position: 'top'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
      }
    },
    {
      element: '#modelSearchInput',
      popover: {
        title: 'Search Models',
        description: 'Search for specific models by name or research group. You can use logical operators like AND, OR, and NOT to combine search terms. This helps you quickly find models you\'re interested in comparing.',
        position: 'bottom'
      }
    },
    {
      element: '#advancedFilterBtn',
      popover: {
        title: 'Advanced Filtering',
        description: 'Click here to access additional filtering options. You can filter by model properties (architecture, parameter count), benchmark characteristics (brain region, species), and more.',
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