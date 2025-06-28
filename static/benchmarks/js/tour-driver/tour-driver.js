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
    console.log('=== Driver.js Initialization ===');
    console.log('window.Driver exists:', !!window.Driver);
    console.log('typeof window.Driver:', typeof window.Driver);
    
    if (!window.Driver) {
      console.error('Driver.js not loaded - window.Driver is not available');
      return false;
    }

    // Store the reset callback for manual triggering
    this.onResetCallback = callbacks.onReset || (() => {});

    // Merge configuration with defaults
    const driverConfig = {
      ...this.defaultOptions,
      ...config.options,
      
      // Event handlers
      onNext: callbacks.onNext || (() => {}),
      onPrevious: callbacks.onPrevious || (() => {}),
      onReset: (element) => {
        console.log('Driver.js onReset triggered');
        if (!this.isStopping && this.onResetCallback) {
          this.onResetCallback();
        }
      },
      onHighlighted: callbacks.onHighlighted || (() => {}),
      onDeselected: callbacks.onDeselected || (() => {})
    };

    console.log('Creating driver instance with config:', driverConfig);
    
    try {
      console.log('Using new Driver() constructor for v0.9.8');
      this.driver = new window.Driver(driverConfig);
      
      // Clean up steps - remove unsupported callbacks
      const cleanSteps = config.steps.map(step => ({
        element: step.element,
        popover: step.popover
      }));
      
      console.log('Setting steps. Total steps:', cleanSteps.length);
      
      // Validate first step element exists
      if (cleanSteps.length > 0 && !this.validateFirstStep(cleanSteps)) {
        return false;
      }
      
      this.isInitialized = true;
      return cleanSteps;
      
    } catch (error) {
      console.error('Failed to initialize Driver.js:', error);
      return false;
    }
  }

  /**
   * Validate and potentially fix the first step element
   */
  validateFirstStep(steps) {
    const firstElement = document.querySelector(steps[0].element);
    console.log('First step element exists:', !!firstElement, steps[0].element);
    
    if (!firstElement) {
      console.warn('First step element not found, looking for fallback...');
      
      // Try common fallback elements
      const fallbacks = ['.ag-root-wrapper', '#leaderboardGrid', 'body'];
      for (const fallback of fallbacks) {
        if (document.querySelector(fallback)) {
          console.log('Using fallback element:', fallback);
          steps[0].element = fallback;
          return true;
        }
      }
      
      console.error('No suitable fallback element found');
      return false;
    }
    
    return true;
  }

  /**
   * Start the tour with given steps
   */
  start(steps) {
    if (!this.isInitialized || !this.driver) {
      console.error('Driver not initialized');
      return false;
    }

    try {
      console.log('Starting tour with steps:', steps.length);
      
      // Define steps and start tour
      this.driver.defineSteps(steps);
      this.driver.start();
      
      // Add custom escape key handler as fallback
      this.addEscapeKeyHandler();
      
      return true;
    } catch (error) {
      console.error('Failed to start tour:', error);
      return false;
    }
  }

  /**
   * Add escape key handler for closing tour
   */
  addEscapeKeyHandler() {
    const escapeHandler = (e) => {
      if (e.key === 'Escape' || e.keyCode === 27) {
        console.log('Escape key pressed - closing tour');
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
            console.log('Overlay clicked - closing tour');
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
      console.log('Stopping tour manually');
      
      // Set flag to prevent recursive calls
      this.isStopping = true;
      
      // Reset the driver first (this will trigger Driver.js cleanup)
      this.driver.reset();
      
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
    return typeof window.Driver !== 'undefined';
  }

  /**
   * Wait for Driver.js to be loaded
   */
  static waitForDriver(timeout = 5000) {
    return new Promise((resolve, reject) => {
      if (window.Driver) {
        resolve(true);
        return;
      }

      const startTime = Date.now();
      const checkInterval = setInterval(() => {
        if (window.Driver) {
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
   * Add tour styling to the page (fallback for when CSS file isn't available)
   */
  static addTourStyling() {
    if (document.getElementById('tour-driver-styles')) {
      return; // Already added
    }

    const style = document.createElement('style');
    style.id = 'tour-driver-styles';
    style.textContent = `
      /* Fixed Driver.js styling based on actual HTML structure */
      
      /* Dark overlay */
      #driver-page-overlay {
        background: rgba(0,0,0,0.5) !important;
        z-index: 999998 !important;
      }
      
      /* Remove white background from highlighted stage */
      #driver-highlighted-element-stage {
        background-color: transparent !important;
        background: none !important;
        border: 3px solid #667eea !important;
        border-radius: 6px !important;
        box-shadow: 0 0 0 6px rgba(102, 126, 234, 0.2) !important;
      }
      
      /* Highlighted elements - just outline */
      .driver-highlighted-element {
        z-index: 1000000 !important;
        position: relative !important;
        outline: 3px solid #667eea !important;
        outline-offset: 2px !important;
        border-radius: 6px !important;
        box-shadow: 0 0 0 6px rgba(102, 126, 234, 0.2) !important;
      }
      
      /* Main popover container */
      #driver-popover-item {
        z-index: 999999 !important;
        position: absolute !important;
        background: white !important;
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.15) !important;
        max-width: 350px !important;
        padding: 20px !important;
        font-family: system-ui, -apple-system, sans-serif !important;
      }
      
      /* Popover content */
      .driver-popover-title {
        font-size: 18px !important;
        font-weight: 600 !important;
        margin-bottom: 10px !important;
        color: #333 !important;
        padding-right: 35px !important;
      }
      
      .driver-popover-description {
        font-size: 14px !important;
        line-height: 1.5 !important;
        color: #666 !important;
        margin-bottom: 20px !important;
        padding-right: 35px !important;
        position: relative !important;
      }
      
      /* Button container */
      .driver-popover-footer {
        display: flex !important;
        justify-content: flex-end !important;
        align-items: center !important;
        gap: 10px !important;
        margin-top: 15px !important;
      }
      
      /* Main popover container needs to be positioned */
      #driver-popover-item {
        position: relative !important;
      }
      
      /* Close button positioned relative to main popover at title level */
      .driver-popover-footer .driver-close-btn {
        position: absolute !important;
        top: 20px !important;
        right: 12px !important;
        background: #f5f5f5 !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 4px !important;
        width: 26px !important;
        height: 26px !important;
        cursor: pointer !important;
        font-size: 14px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: #666 !important;
        transition: all 0.2s ease !important;
        z-index: 10 !important;
        align-self: auto !important;
        margin: 0 !important;
      }
      
      .driver-close-btn:hover {
        background: #e8e8e8 !important;
        color: #333 !important;
      }
      
      /* Navigation buttons container */
      .driver-btn-group {
        display: flex !important;
        gap: 8px !important;
      }
      
      /* Individual buttons */
      .driver-prev-btn,
      .driver-next-btn {
        padding: 8px 16px !important;
        border-radius: 4px !important;
        font-size: 14px !important;
        cursor: pointer !important;
        border: none !important;
      }
      
      .driver-next-btn {
        background: #667eea !important;
        color: white !important;
      }
      
      .driver-prev-btn {
        background: #f5f5f5 !important;
        color: #333 !important;
        border: 1px solid #ddd !important;
      }
      
      .driver-prev-btn.driver-disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
      }
      
      /* Fix layout shifts - prevent driver-fix-stacking from affecting layout */
      .driver-fix-stacking {
        z-index: auto !important;
      }
      
      /* Ensure Driver.js positioning is not overridden */
      #driver-popover-item[style*="left"][style*="top"] {
        position: absolute !important;
        z-index: 999999 !important;
        /* Don't override left/top - let Driver.js handle positioning */
      }
      
      /* Popover tip/arrow */
      .driver-popover-tip {
        position: absolute !important;
        width: 0 !important;
        height: 0 !important;
        border: 8px solid transparent !important;
      }
      
      .driver-popover-tip.top {
        top: -16px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        border-bottom-color: white !important;
        border-top: none !important;
      }
      
      .driver-popover-tip.left {
        left: -16px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        border-right-color: white !important;
        border-left: none !important;
      }
    `;
    
    document.head.appendChild(style);
  }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TourDriver;
}

// Global availability
window.TourDriver = TourDriver; 