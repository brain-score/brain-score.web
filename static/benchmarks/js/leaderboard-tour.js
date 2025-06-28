/**
 * Leaderboard Tour Module
 * Integrates Driver.js with the AG-Grid leaderboard using modular tour components.
 * Handles leaderboard-specific logic while leveraging reusable tour infrastructure.
 */

class LeaderboardTour {
  constructor() {
    this.tourDriver = new TourDriver();
    this.stateManager = new TourStateManager('leaderboard', '1.0');
    this.configLoader = new TourConfigLoader();
    this.currentConfig = null;
    this.originalColumnState = null;
    this.tourSections = new Map();
  }

  /**
   * Prepare the AG-Grid for optimal tour experience
   */
  prepareGridForTour() {
    if (!window.globalGridApi) {
      console.error('AG-Grid API not available');
      return false;
    }

    try {
      // Store current column state (for potential future use)
      this.originalColumnState = window.globalGridApi.getColumnState();
      
      // Skip layout changes - keep the grid as-is
      // this.setOptimalLayout(); // Commented out to preserve current layout
      
      // Scroll to top
      window.globalGridApi.ensureIndexVisible(0, 'top');
      
      // Clear any existing selections
      window.globalGridApi.deselectAll();
      
      return true;
      
    } catch (error) {
      console.error('Failed to prepare grid for tour:', error);
      return false;
    }
  }

  /**
   * Set optimal column layout for tour visibility
   */
  setOptimalLayout() {
    if (!window.globalGridApi) return;

    try {
      // Ensure key columns are visible and properly sized
      const columnState = [
        { colId: 'rank', hide: false, width: 60 },
        { colId: 'model', hide: false, width: 200 },
        { colId: 'average', hide: false, width: 120 },
        { colId: 'neural_vision_v0', hide: false, width: 120 },
        { colId: 'behavior_vision_v0', hide: false, width: 120 },
        { colId: 'engineering_vision_v0', hide: false, width: 120 }
      ];
      
      window.globalGridApi.applyColumnState({ state: columnState });
      
      // Ensure the grid is sized properly
      window.globalGridApi.sizeColumnsToFit();
      
    } catch (error) {
      console.error('Failed to set optimal layout:', error);
    }
  }

  /**
   * Restore original grid state after tour
   */
  restoreGridState() {
    if (!window.globalGridApi || !this.originalColumnState) return;

    try {
      window.globalGridApi.applyColumnState({ state: this.originalColumnState });
      this.originalColumnState = null;
    } catch (error) {
      console.error('Failed to restore grid state:', error);
    }
  }

  /**
   * Handle tour completion
   */
  onTourComplete(completed = true) {
    // Mark tour as completed in state
    if (completed) {
      this.stateManager.markTourCompleted();
    }
    
    // Restore interactive tour state if needed
    this.restoreInteractiveTourState();
    
    // Restore grid state
    this.restoreGridState();
    
    // Clean up
    this.tourDriver.stop();
  }

  /**
   * Restore any changes made during interactive tours
   */
  restoreInteractiveTourState() {
    // Restore behavioral benchmarks if they were disabled during tour
    if (window._tourOriginalBehaviorState !== undefined) {
      const behaviorCheckbox = document.querySelector('input[value="behavior_vision_v0"]');
      if (behaviorCheckbox && behaviorCheckbox.checked !== window._tourOriginalBehaviorState) {
        // Set checkbox state
        behaviorCheckbox.checked = window._tourOriginalBehaviorState;
        
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
      delete window._tourOriginalBehaviorState;
    }
    
    // Restore Freeman benchmark if it was modified during tour
    if (window._tourOriginalFreemanState !== undefined) {
      const freemanCheckbox = document.querySelector('input[value="FreemanZiemba2013.V1-pls_v2"]');
      if (freemanCheckbox && freemanCheckbox.checked !== window._tourOriginalFreemanState) {
        // Set checkbox state
        freemanCheckbox.checked = window._tourOriginalFreemanState;
        
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
      delete window._tourOriginalFreemanState;
    }
    
    // Close advanced filters panel if it was opened during tour
    const panel = document.getElementById('advancedFiltersPanel');
    if (panel && !panel.classList.contains('hidden')) {
      document.getElementById('advancedFilterBtn').click();
    }
  }

  /**
   * Start the tour with specified configuration
   */
  startTour(configName = 'default') {
    // Clear any previous tour state
    if (window.tourStepState) {
      window.tourStepState.clear();
    }
    
    // Load configuration
    this.currentConfig = this.configLoader.loadTourConfig(configName);
    if (!this.currentConfig) {
      console.error('Failed to load tour configuration');
      return false;
    }

    // Wait for grid to be ready, then start tour
    this.waitForGridReady()
      .then(() => this.continueStartTour())
      .catch(error => {
        console.error('Failed to start tour:', error);
      });
  }

  /**
   * Continue tour start after grid is ready
   */
  continueStartTour() {
    // Prepare grid for tour
    if (!this.prepareGridForTour()) {
      console.error('Failed to prepare grid for tour');
      return false;
    }

    // Set up tour callbacks
    const callbacks = {
      onNext: () => {
        this.stateManager.updateCurrentStep(this.stateManager.getCurrentStep() + 1);
      },
      
      onPrevious: () => {
        const currentStep = Math.max(0, this.stateManager.getCurrentStep() - 1);
        this.stateManager.updateCurrentStep(currentStep);
      },
      
      onReset: () => {
        console.log('Tour: Reset/Close triggered');
        this.onTourComplete(false);
      },
      
      onHighlighted: (element) => {
        console.log('Tour: Element highlighted:', element);
        this.handleStepHighlight(element);
      },
      
      onDeselected: (element) => {
        console.log('Tour: Element deselected:', element);
      }
    };

    // Initialize tour driver
    const steps = this.tourDriver.initialize(this.currentConfig, callbacks);
    if (!steps) {
      console.error('Failed to initialize tour driver');
      this.onTourComplete(false);
      return false;
    }

    // Add tour styling (fallback for when CSS file isn't available)
    TourDriver.addTourStyling();

    // Start the tour
    setTimeout(() => {
      if (this.tourDriver.start(steps)) {
        // Tour started successfully
      } else {
        console.error('Failed to start tour');
        this.onTourComplete(false);
      }
    }, 500); // Brief delay to ensure everything is ready

    return true;
  }

  /**
   * Handle step highlighting with leaderboard-specific logic
   */
  handleStepHighlight(element) {


    // Handle leaderboard-specific step logic
    if (element && element.classList) {
      // Handle expandable headers
      if (element.classList.contains('expandable-header')) {
        this.handleExpandableHeader(element);
      }
      
      // Handle grid cell highlighting
      if (element.classList.contains('ag-cell')) {
        this.handleGridCellHighlight(element);
      }
    }
  }

  /**
   * Handle expandable header interactions
   */
  handleExpandableHeader(element) {
    // Ensure the header is visible and properly positioned
    const headerRect = element.getBoundingClientRect();
    const gridContainer = document.querySelector('#leaderboardGrid');
    
    if (headerRect.top < 100 || headerRect.bottom > window.innerHeight - 100) {
      // Scroll to bring header into view
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  /**
   * Handle grid cell highlighting
   */
  handleGridCellHighlight(element) {
    // Ensure the cell is visible
    const cellRect = element.getBoundingClientRect();
    
    if (cellRect.top < 50 || cellRect.bottom > window.innerHeight - 50) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  /**
   * Wait for AG-Grid to be ready
   */
  waitForGridReady() {
    return new Promise((resolve) => {
      const checkGrid = () => {
        if (window.globalGridApi && window.globalGridApi.getDisplayedRowCount() > 0) {
          const checkReady = () => {
            const firstRow = document.querySelector('.ag-row');
            const firstCell = document.querySelector('.ag-cell');
            
            if (firstRow && firstCell) {
              resolve();
            } else {
              setTimeout(checkReady, 100);
            }
          };
          checkReady();
        } else {
          setTimeout(checkGrid, 100);
        }
      };
      checkGrid();
    });
  }

  /**
   * Register additional tour sections for future features
   */
  registerTourSection(name, steps) {
    this.tourSections.set(name, steps);
  }

  /**
   * Check if user should see tour
   */
  shouldShowTour() {
    return this.stateManager.shouldShowTour();
  }

  /**
   * Check if user should see a specific feature tour
   */
  shouldShowFeatureTour(featureName) {
    return this.stateManager.shouldShowFeatureTour(featureName);
  }

  /**
   * Mark feature tour as completed
   */
  markFeatureTourCompleted(featureName) {
    this.stateManager.markFeatureTourCompleted(featureName);
  }

  /**
   * Get step handlers for advanced interactions
   */
  getStepHandlers() {
    return this.configLoader.getStepHandlers();
  }
}

// Initialize tour system when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  // Wait for existing leaderboard initialization
  const initTour = () => {
    if (window.globalGridApi && document.getElementById('tutorialBtn')) {
      const tour = new LeaderboardTour();
      
      // Create tutorial dropdown menu
      createTutorialDropdown(tour);
      
      // Show tour automatically for new users (optional)
      // if (tour.shouldShowTour()) {
      //   setTimeout(() => tour.startTour(), 1000);
      // }
      
      // Make tour available globally for debugging
      window.leaderboardTour = tour;
    } else {
      // Retry until grid is ready
      setTimeout(initTour, 100);
    }
  };
  
  initTour();
});

/**
 * Create tutorial dropdown menu with multiple tour options
 */
function createTutorialDropdown(tour) {
  const tutorialBtn = document.getElementById('tutorialBtn');
  const wrapper = tutorialBtn.parentNode;
  
  // Create dropdown container
  const dropdownContainer = document.createElement('div');
  dropdownContainer.className = 'tutorial-dropdown-container';
  dropdownContainer.style.position = 'relative';
  dropdownContainer.style.display = 'inline-block';
  
  // Create dropdown menu
  const dropdownMenu = document.createElement('div');
  dropdownMenu.className = 'tutorial-dropdown-menu';
  dropdownMenu.style.cssText = `
    position: absolute;
    top: 100%;
    left: 0;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 1000;
    min-width: 220px;
    display: none;
    padding: 8px 0;
    margin-top: 4px;
  `;
  
  // Create menu items
  const menuItems = [
    {
      title: 'Basic Tour',
      description: 'Quick overview of key features',
      action: () => tour.startTour('default')
    },
    {
      title: 'Interactive Filter Demo',
      description: 'See filtering in action with live examples',
      action: () => tour.startTour('interactiveBenchmarkTour')
    }
  ];
  
  menuItems.forEach(item => {
    const menuItem = document.createElement('div');
    menuItem.style.cssText = `
      padding: 12px 16px;
      cursor: pointer;
      border-bottom: 1px solid #f0f0f0;
      transition: background-color 0.2s;
    `;
    menuItem.innerHTML = `
      <div style="font-weight: 600; color: #333; margin-bottom: 4px;">${item.title}</div>
      <div style="font-size: 12px; color: #666; line-height: 1.3;">${item.description}</div>
    `;
    
    menuItem.addEventListener('mouseenter', () => {
      menuItem.style.backgroundColor = '#f8f9fa';
    });
    menuItem.addEventListener('mouseleave', () => {
      menuItem.style.backgroundColor = 'transparent';
    });
    menuItem.addEventListener('click', (e) => {
      e.preventDefault();
      dropdownMenu.style.display = 'none';
      item.action();
    });
    
    dropdownMenu.appendChild(menuItem);
  });
  
  // Remove border from last item
  const lastItem = dropdownMenu.lastElementChild;
  if (lastItem) {
    lastItem.style.borderBottom = 'none';
  }
  
  // Replace button with dropdown container
  wrapper.replaceChild(dropdownContainer, tutorialBtn);
  dropdownContainer.appendChild(tutorialBtn);
  dropdownContainer.appendChild(dropdownMenu);
  
  // Add dropdown toggle functionality
  tutorialBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    const isVisible = dropdownMenu.style.display === 'block';
    dropdownMenu.style.display = isVisible ? 'none' : 'block';
  });
  
  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!dropdownContainer.contains(e.target)) {
      dropdownMenu.style.display = 'none';
    }
  });
  
  // Add dropdown arrow to button
  const originalText = tutorialBtn.querySelector('.text-wrapper').textContent;
  tutorialBtn.querySelector('.text-wrapper').innerHTML = `${originalText} <span style="font-size: 10px; margin-left: 4px;">▼</span>`;
}

// Export for potential use in other modules
window.LeaderboardTour = LeaderboardTour; 