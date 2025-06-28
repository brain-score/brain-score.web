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
      console.log('Preparing grid for tour...');
      
      // Store current column state
      this.originalColumnState = window.globalGridApi.getColumnState();
      
      // Set optimal layout for tour
      this.setOptimalLayout();
      
      // Scroll to top
      window.globalGridApi.ensureIndexVisible(0, 'top');
      
      // Clear any existing selections
      window.globalGridApi.deselectAll();
      
      console.log('Grid prepared successfully');
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
      console.log('Restoring original grid state...');
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
    console.log('Tour completed:', completed);
    
    // Mark tour as completed in state
    if (completed) {
      this.stateManager.markTourCompleted();
    }
    
    // Restore grid state
    this.restoreGridState();
    
    // Clean up
    this.tourDriver.stop();
    
    console.log('Tour cleanup completed');
  }

  /**
   * Start the tour with specified configuration
   */
  startTour(configName = 'default') {
    console.log('Starting leaderboard tour with config:', configName);
    
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
    console.log('Continuing tour start...');
    
    // Prepare grid for tour
    if (!this.prepareGridForTour()) {
      console.error('Failed to prepare grid for tour');
      return false;
    }

    // Set up tour callbacks
    const callbacks = {
      onNext: () => {
        console.log('Tour: Next button clicked');
        this.stateManager.updateCurrentStep(this.stateManager.getCurrentStep() + 1);
      },
      
      onPrevious: () => {
        console.log('Tour: Previous button clicked');
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
        console.log('Tour started successfully');
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
    // Debug: Check for popover elements and current styling
    setTimeout(() => {
      const popover = document.getElementById('driver-popover-item');
      if (popover) {
        console.log('Popover element:', popover);
        console.log('Popover position:', {
          left: popover.style.left,
          top: popover.style.top,
          display: popover.style.display
        });
      }
    }, 100);

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
              console.log('Grid is ready with data and rendered cells');
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
      
      // Add event listener to tutorial button
      document.getElementById('tutorialBtn').addEventListener('click', (e) => {
        e.preventDefault();
        console.log('Tutorial button clicked, starting tour...');
        tour.startTour();
      });
      
      // Show tour automatically for new users (optional)
      // if (tour.shouldShowTour()) {
      //   setTimeout(() => tour.startTour(), 1000);
      // }
      
      // Make tour available globally for debugging
      window.leaderboardTour = tour;
      
      console.log('Leaderboard tour initialized successfully');
    } else {
      // Retry until grid is ready
      setTimeout(initTour, 100);
    }
  };
  
  initTour();
});

// Export for potential use in other modules
window.LeaderboardTour = LeaderboardTour; 