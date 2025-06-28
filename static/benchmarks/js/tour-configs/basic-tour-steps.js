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
        description: 'These benchmarks measure how well models predict neural responses recorded from brain areas like V1, V2, V4, and IT cortex. Notice the count badge on the bottom right - this shows how many benchmarks are included and lets you expand to see individual neural benchmarks.',
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
      element: '.expandable-header.neural .benchmark-count',
      popover: {
        title: 'Expansion Count Badge',
        description: 'This count badge shows how many neural benchmarks are included (like "4") and doubles as an expand button! Click on it to reveal individual brain area benchmarks like V1, V2, V4, and IT. I\'ll click it now to demonstrate!',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Actually click the count badge to demonstrate expansion
        setTimeout(() => {
          const neuralCountBadge = document.querySelector('.expandable-header.neural .benchmark-count');
          if (neuralCountBadge) {
            // Check if neural column is currently collapsed
            const isExpanded = window.columnExpansionState && window.columnExpansionState.get('neural_vision_v0') === true;
            if (!isExpanded) {
              neuralCountBadge.click();
            }
          }
        }, 500); // Small delay to let the step highlight show first
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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