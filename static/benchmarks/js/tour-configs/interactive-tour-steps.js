// Interactive Tour Configuration
// This file contains the advanced benchmark filtering demonstration tour

// Ensure tour configs namespace exists
window.tourConfigs = window.tourConfigs || {};

// Interactive Benchmark Tour - Advanced filtering demonstration
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
        description: 'Here\'s the benchmark filter tree. Each checkbox controls whether that benchmark is displayed in the leaderboard and if it contributes to the Brain-Score. Engineering benchmarks are excluded from the calculation by default.',
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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
        title: 'Benchmark Filtering Demo',
        description: 'I\'ll expand both Neural and V1 categories to show the tree structure. Notice how the V1 category contains individual benchmarks like FreemanZiemba2013. This hierarchy lets you filter at different levels of granularity.',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Expand leaderboard columns like the basic tour does
        expandBenchmarkHeaders(['neural_vision_v0']);
        
        // Expand the filter tree to show the hierarchy
        setTimeout(() => {
          // Find neural category in filter tree and expand it
          const neuralNode = document.querySelector('input[value="neural_vision_v0"]')?.closest('.benchmark-node');
          if (neuralNode && neuralNode.classList.contains('collapsed')) {
            const neuralToggle = neuralNode.querySelector('.tree-toggle, .expand-toggle, [data-toggle]');
            if (neuralToggle) {
              neuralToggle.click();
            }
          }
          
          // Small delay before expanding V1 to show the progression
          setTimeout(() => {
            // Find and expand V1 subcategory
            const v1Node = document.querySelector('input[value="V1_v0"]')?.closest('.benchmark-node');
            if (v1Node && v1Node.classList.contains('collapsed')) {
              const v1Toggle = v1Node.querySelector('.tree-toggle, .expand-toggle, [data-toggle]');
              if (v1Toggle) {
                v1Toggle.click();
              }
            }
          }, 300);
        }, 100);
      }
    },
    {
      element: 'input[value="V1_v0"]',
      popover: {
        title: 'Deselecting V1 Category',
        description: 'Now I\'ll deselect the V1 category to demonstrate benchmark filtering. Watch as all V1 benchmarks get excluded and the V1 columns disappear from the leaderboard, but the tree stays expanded so you can see what was filtered out!',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Deselect V1 checkbox to show category filtering
        const v1Checkbox = document.querySelector('input[value="V1_v0"]');
        if (v1Checkbox && v1Checkbox.checked) {
          // Set checkbox state
          v1Checkbox.checked = false;
          
          // Trigger change event manually
          const changeEvent = new Event('change', { bubbles: true });
          v1Checkbox.dispatchEvent(changeEvent);
          
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
      element: '.ag-row[row-index="0"] .ag-cell[col-id="neural_vision_v0"]',
      popover: {
        title: 'Watch the Neural Scores Change!',
        description: 'Notice how the Neural column scores have been recalculated! By removing V1 benchmarks, we\'ve changed how neural vision performance is calculated, affecting each model\'s Brain-Score. Notice how neural column has become blue. Any benchmark that is affected by filtering will change it\'s color scale to reflect divergence from thestandard Brain-Score leaderboard.',
        position: 'left'
      }
    },
    {
      element: '.ag-header-cell[col-id="filtered_score"] .ag-header-cell-text', 
      popover: {
        title: 'Global Brain-Score Updated',
        description: 'The global Brain-Score (filtered score column) has also recalculated! Since we removed a neural benchmark, the overall Brain-Scores have changed. Some models may have moved up or down in ranking.',
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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
      element: 'input[value="behavior_vision_v0"]',
      popover: {
        title: 'Deselecting Behavioral Benchmarks',
        description: 'Now I\'ll uncheck Behavioral benchmarks to show you how this affects the leaderboard. Watch the columns and scores change in real-time!',
        position: 'left'
      },
      beforeShow: (element, step, options) => {
        const stepIndex = options.state.activeIndex;
        
        // Record current state before making changes
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Scroll to engineering section first
        const engineeringParent = document.querySelector('.engineering-parent');
        if (engineeringParent && window.scrollElementIntoView) {
          window.scrollElementIntoView(engineeringParent);
        }
        
        // Small delay before expanding to ensure scroll completes
        setTimeout(() => {
          // Expand engineering parent if collapsed
          if (engineeringParent && engineeringParent.classList.contains('collapsed')) {
            const toggle = engineeringParent.querySelector('.tree-toggle');
            if (toggle) toggle.click();
          }
        }, 300);
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
        // Scroll to engineering checkbox to ensure it's visible
        const engineeringCheckbox = document.querySelector('input[value="engineering_vision_v0"]');
        if (engineeringCheckbox && window.scrollElementIntoView) {
          window.scrollElementIntoView(engineeringCheckbox);
        }
        
        // Small delay before checking to ensure scroll completes
        setTimeout(() => {
          // Check engineering benchmarks
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
        }, 300);
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
        window.tourStepState.recordCurrentStateForStep(stepIndex);
        
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
        description: 'Use this Reset button to restore all filters to their default state anytime. I\'ll click it now to clean up after our demo!',
        position: 'top'
      },
      beforeShow: (element, step, options) => {
        // Scroll to reset button to ensure it's visible
        const resetButton = document.querySelector('#resetAllFiltersBtn');
        if (resetButton && window.scrollElementIntoView) {
          window.scrollElementIntoView(resetButton);
        }
      }
    },
    {
      element: '#advancedFilterBtn',
      popover: {
        title: 'Demo Complete! 🎉',
        description: 'Perfect! All filters have been reset and I\'m closing the advanced panel to return you to the default view. You now know how to use benchmark filtering to customize your analysis and explore model capabilities!',
        position: 'bottom'
      },
      beforeShow: (element, step, options) => {
        // Reset all filters first
        setTimeout(() => {
          const resetButton = document.querySelector('#resetAllFiltersBtn');
          if (resetButton) {
            resetButton.click();
          }
        }, 100);
        
        // Close the advanced filters panel after a delay
        setTimeout(() => {
          const panel = document.getElementById('advancedFiltersPanel');
          const advancedBtn = document.getElementById('advancedFilterBtn');
          
          if (panel && !panel.classList.contains('hidden') && advancedBtn) {
            advancedBtn.click();
          }
        }, 800); // Delay to let reset complete first
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