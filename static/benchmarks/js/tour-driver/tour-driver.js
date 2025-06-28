/**
 * Generic Driver.js Wrapper
 * Provides a reusable interface for Driver.js tours across different pages
 */

class TourDriver {
  constructor(options = {}) {
    this.driver = null;
    this.isInitialized = false;
    this.isStopping = false;
    this.onResetCallback = null;
    this.defaultOptions = {
      animate: true,
      allowClose: true,
      overlayClickNext: false,
      keyboardControl: true,
      smoothScroll: true,
      stagePadding: 12,
      ...options
    };
  }

  /**
   * Initialize Driver.js with configuration
   * @param {Object} config - Driver.js configuration object
   * @param {Object} callbacks - Event callbacks {onNext, onPrevious, onReset, onHighlighted, onDeselected}
   */
  initialize(config, callbacks = {}) {
    if (!window.driver || !window.driver.js || !window.driver.js.driver) {
      return false;
    }

    // Store the reset callback for manual triggering
    this.onResetCallback = callbacks.onReset || (() => {});

    // Merge configuration with defaults
    const driverConfig = {
      ...this.defaultOptions,
      ...config.options,
      
      // Event handlers for v1.x API
      onNextClick: (element, step, options) => {
        if (callbacks.onNext) {
          callbacks.onNext();
        }
        // Move to next step (required in v1.x when overriding onNextClick)
        this.driver.moveNext();
      },
      onPrevClick: (element, step, options) => {
        if (callbacks.onPrevious) {
          callbacks.onPrevious();
        }
        
        // Handle state restoration for interactive tours
        const currentStepIndex = options.state.activeIndex;
        const prevStepIndex = currentStepIndex - 1;
        
        // Restore state for the previous step if state tracking is available
        if (window.tourStepState && prevStepIndex >= 0) {
          window.tourStepState.restoreState(currentStepIndex);
        }
        
        // Move to previous step (required in v1.x when overriding onPrevClick)
        this.driver.movePrevious();
      },
      onCloseClick: (element) => {
        if (!this.isStopping && this.onResetCallback) {
          this.onResetCallback();
        }
      },
      onHighlighted: callbacks.onHighlighted || (() => {}),
      onDeselected: callbacks.onDeselected || (() => {})
    };

        try {
      
      // Access driver function via CDN (official documentation approach)
      if (window.driver && window.driver.js && typeof window.driver.js.driver === 'function') {
        this.driver = window.driver.js.driver(driverConfig);
      } else {
        throw new Error('Could not find driver function. Available: ' + Object.keys(window.driver || {}));
      }
      
      // Process steps for Driver.js v1.x with beforeShow -> onHighlightStarted mapping
      const cleanSteps = config.steps.map(step => {
        const cleanStep = {
          element: step.element,
          popover: step.popover
        };
        
        // Map beforeShow to onHighlightStarted for v1.x compatibility
        if (step.beforeShow && typeof step.beforeShow === 'function') {
          cleanStep.onHighlightStarted = step.beforeShow;
        }
        
        return cleanStep;
      });
      

      
      // Validate first step element exists
      if (cleanSteps.length > 0 && !this.validateFirstStep(cleanSteps)) {
        return false;
      }
      
      this.isInitialized = true;
      return cleanSteps;
      
    } catch (error) {
      return false;
    }
  }

  /**
   * Validate and potentially fix the first step element
   */
  validateFirstStep(steps) {
    const firstElement = document.querySelector(steps[0].element);
    
    if (!firstElement) {
      // Try common fallback elements
      const fallbacks = ['.ag-root-wrapper', '#leaderboardGrid', 'body'];
      for (const fallback of fallbacks) {
        if (document.querySelector(fallback)) {
          steps[0].element = fallback;
          return true;
        }
      }
      
      return false;
    }
    
    return true;
  }

  /**
   * Start the tour with given steps
   */
  start(steps) {
    if (!this.isInitialized || !this.driver) {
      return false;
    }

    try {
      // Set steps and start tour using v1.x API
      this.driver.setSteps(steps);
      this.driver.drive();
      
      // Add custom escape key handler as fallback
      this.addEscapeKeyHandler();
      
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Add escape key handler for closing tour
   */
  addEscapeKeyHandler() {
    const escapeHandler = (e) => {
      if (e.key === 'Escape' || e.keyCode === 27) {
        this.stop();
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    
    document.addEventListener('keydown', escapeHandler);
    
    // Also add click handler for overlay (if Driver.js doesn't handle it)
    setTimeout(() => {
      const overlay = document.getElementById('driver-page-overlay');
      if (overlay) {
        const clickHandler = (e) => {
          if (e.target === overlay) {
            this.stop();
            overlay.removeEventListener('click', clickHandler);
          }
        };
        overlay.addEventListener('click', clickHandler);
      }
    }, 100);
  }

  /**
   * Stop the current tour
   */
  stop() {
    if (this.driver && !this.isStopping) {
      // Set flag to prevent recursive calls
      this.isStopping = true;
      
      // Clear tour state tracking if available
      if (window.tourStepState) {
        window.tourStepState.clear();
      }
      
      // Destroy the driver (v1.x API)
      this.driver.destroy();
      
      // Clear the flag after a brief delay
      setTimeout(() => {
        this.isStopping = false;
      }, 100);
    }
  }

  /**
   * Check if Driver.js is available
   */
  static isAvailable() {
    return typeof window.driver !== 'undefined' && 
           typeof window.driver.js !== 'undefined' && 
           typeof window.driver.js.driver !== 'undefined';
  }

  /**
   * Wait for Driver.js to be loaded
   */
  static waitForDriver(timeout = 5000) {
    return new Promise((resolve, reject) => {
      if (window.driver && window.driver.js && window.driver.js.driver) {
        resolve(true);
        return;
      }

      const startTime = Date.now();
      const checkInterval = setInterval(() => {
        if (window.driver && window.driver.js && window.driver.js.driver) {
          clearInterval(checkInterval);
          resolve(true);
        } else if (Date.now() - startTime > timeout) {
          clearInterval(checkInterval);
          reject(new Error('Driver.js failed to load within timeout'));
        }
      }, 100);
    });
  }

  /**
   * Add tour styling to the page (v1.x includes CSS, but this provides fallback)
   */
  static addTourStyling() {
    // v1.x includes its own CSS file, so this is mainly for fallback/customization
  }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TourDriver;
}

// Global availability
window.TourDriver = TourDriver; 