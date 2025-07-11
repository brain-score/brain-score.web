/**
 * Tour Configuration Loader
 * Handles loading and managing tour configurations from various sources
 * Provides fallback mechanisms and validation
 */

class TourConfigLoader {
  constructor(configNamespace = 'tourConfigs') {
    this.configNamespace = configNamespace;
    this.loadedConfigs = new Map();
    this.fallbackConfigs = new Map();
  }

  /**
   * Load tour configuration by name
   * @param {string} configName - Name of the configuration to load
   * @param {string} tourType - Type of tour (e.g., 'default', 'advanced')
   */
  loadTourConfig(configName = 'default', tourType = 'defaultTour') {
    try {
      
      
      // Check if tour configurations are loaded
      if (!window[this.configNamespace]) {
        console.error('Tour configurations not loaded');
        return this.getFallbackConfig(configName);
      }
      
      // Handle special config types
      const configKey = this.getConfigKey(configName, tourType);
      const config = window[this.configNamespace][configKey];
      
      if (!config) {
        return this.getFallbackConfig(configName);
      }
      
      // Validate configuration
      if (!this.validateConfig(config)) {
        console.error('Invalid configuration, using fallback');
        return this.getFallbackConfig(configName);
      }
      
      // Cache the loaded config
      this.loadedConfigs.set(configName, config);
      
      return config;
    } catch (error) {
      console.error('Failed to load tour configuration:', error);
      return this.getFallbackConfig(configName);
    }
  }

  /**
   * Get the configuration key based on config name and type
   */
  getConfigKey(configName, tourType) {
    if (configName === 'advanced') {
      return 'advancedFeaturesTour';
    }
    
    // Map common config names to their keys
    const keyMap = {
      'default': 'defaultTour',
      'basic': 'defaultTour',
      'advanced': 'advancedFeaturesTour',
      'features': 'advancedFeaturesTour',
      'interactiveBenchmarkTour': 'interactiveBenchmarkTour'
    };
    
    return keyMap[configName] || tourType;
  }

  /**
   * Validate tour configuration structure
   */
  validateConfig(config) {
    if (!config || typeof config !== 'object') {
      return false;
    }
    
    // Must have steps array
    if (!Array.isArray(config.steps) || config.steps.length === 0) {
      return false;
    }
    
    // Validate each step
    for (const step of config.steps) {
      // Step must have popover
      if (!step.popover) {
        return false;
      }
      
      // Popover must have title and description
      if (!step.popover.title || !step.popover.description) {
        return false;
      }
      
      // Element is optional for center-positioned popovers
      if (!step.element && step.popover.position !== 'center') {
        return false;
      }
    }
    
    return true;
  }

  /**
   * Register a fallback configuration
   */
  registerFallbackConfig(name, config) {
    if (this.validateConfig(config)) {
      this.fallbackConfigs.set(name, config);
    } else {
      console.error('Invalid fallback configuration for:', name);
    }
  }

  /**
   * Get fallback configuration
   */
  getFallbackConfig(configName = 'default') {
    // Try registered fallback first
    if (this.fallbackConfigs.has(configName)) {
      return this.fallbackConfigs.get(configName);
    }
    
    // Return basic fallback
    return this.getBasicFallbackConfig();
  }

  /**
   * Basic fallback configuration for any page
   */
  getBasicFallbackConfig() {
    return {
      steps: [
        {
          element: 'body',
          popover: {
            title: 'Welcome to the Tour',
            description: 'This is a basic tour fallback. The main tour configuration could not be loaded.',
            position: 'center'
          }
        }
      ],
      options: {
        animate: true,
        allowClose: true,
        showProgress: false
      }
    };
  }

  /**
   * Get configuration for specific elements (dynamic generation)
   */
  generateConfigForElements(elements, title = 'Feature Tour') {
    const steps = elements.map((element, index) => ({
      element: element.selector,
      popover: {
        title: element.title || `${title} - Step ${index + 1}`,
        description: element.description || `Learn about this feature.`,
        position: element.position || 'bottom'
      }
    }));

    return {
      steps,
      options: {
        animate: true,
        allowClose: true,
        showProgress: true
      }
    };
  }

  /**
   * Get available configuration names
   */
  getAvailableConfigs() {
    const configs = [];
    
    if (window[this.configNamespace]) {
      configs.push(...Object.keys(window[this.configNamespace]));
    }
    
    configs.push(...this.fallbackConfigs.keys());
    
    return [...new Set(configs)]; // Remove duplicates
  }

  /**
   * Check if a configuration exists
   */
  hasConfig(configName, tourType = 'defaultTour') {
    const configKey = this.getConfigKey(configName, tourType);
    
    return !!(
      (window[this.configNamespace] && window[this.configNamespace][configKey]) ||
      this.fallbackConfigs.has(configName)
    );
  }

  /**
   * Get step handlers from configuration
   */
  getStepHandlers(configName = 'default') {
    try {
      if (window[this.configNamespace] && window[this.configNamespace].stepHandlers) {
        return window[this.configNamespace].stepHandlers;
      }
    } catch (error) {
      console.error('Failed to load step handlers:', error);
    }
    
    return {};
  }

  /**
   * Clear cached configurations
   */
  clearCache() {
    this.loadedConfigs.clear();
  }

  /**
   * Static utility methods
   */

  /**
   * Create a new config loader with default settings
   */
  static create(namespace = 'tourConfigs') {
    return new TourConfigLoader(namespace);
  }

  /**
   * Quick config validation
   */
  static isValidConfig(config) {
    const loader = new TourConfigLoader();
    return loader.validateConfig(config);
  }

  /**
   * Create a simple config from element list
   */
  static createSimpleConfig(elements, options = {}) {
    const loader = new TourConfigLoader();
    return {
      ...loader.generateConfigForElements(elements),
      options: {
        ...loader.generateConfigForElements(elements).options,
        ...options
      }
    };
  }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TourConfigLoader;
}

// Global availability
window.TourConfigLoader = TourConfigLoader; 