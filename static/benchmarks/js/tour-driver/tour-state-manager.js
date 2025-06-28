/**
 * Tour State Manager
 * Handles tour state persistence using localStorage
 * Provides reusable state management for any tour implementation
 */

class TourStateManager {
  constructor(tourName, tourVersion = '1.0') {
    this.tourName = tourName;
    this.tourVersion = tourVersion;
    this.storageKeys = {
      completed: `${tourName}-tour-completed`,
      version: `${tourName}-tour-version`, 
      lastStep: `${tourName}-tour-last-step`,
      features: `${tourName}-tour-features`
    };
  }

  /**
   * Load tour state from localStorage
   */
  loadTourState() {
    return {
      completed: JSON.parse(localStorage.getItem(this.storageKeys.completed) || 'false'),
      version: localStorage.getItem(this.storageKeys.version) || this.tourVersion,
      lastStep: parseInt(localStorage.getItem(this.storageKeys.lastStep) || '0'),
      features: JSON.parse(localStorage.getItem(this.storageKeys.features) || '{}')
    };
  }

  /**
   * Save tour state to localStorage
   */
  saveTourState(state) {
    localStorage.setItem(this.storageKeys.completed, JSON.stringify(state.completed));
    localStorage.setItem(this.storageKeys.version, state.version);
    localStorage.setItem(this.storageKeys.lastStep, state.lastStep.toString());
    if (state.features) {
      localStorage.setItem(this.storageKeys.features, JSON.stringify(state.features));
    }
  }

  /**
   * Mark tour as completed
   */
  markTourCompleted() {
    const state = this.loadTourState();
    state.completed = true;
    state.version = this.tourVersion;
    this.saveTourState(state);
  }

  /**
   * Reset tour state (for debugging or forced restart)
   */
  resetTourState() {
    Object.values(this.storageKeys).forEach(key => {
      localStorage.removeItem(key);
    });
  }

  /**
   * Check if user should see tour (new users or version updates)
   */
  shouldShowTour() {
    const state = this.loadTourState();
    const tourCompleted = state.completed;
    const isNewVersion = state.version !== this.tourVersion;
    
    return !tourCompleted || isNewVersion;
  }

  /**
   * Update current step
   */
  updateCurrentStep(stepIndex) {
    const state = this.loadTourState();
    state.lastStep = stepIndex;
    this.saveTourState(state);
  }

  /**
   * Get current step
   */
  getCurrentStep() {
    const state = this.loadTourState();
    return state.lastStep;
  }

  /**
   * Feature-specific tour management
   */
  
  /**
   * Check if user should see a specific feature tour
   */
  shouldShowFeatureTour(featureName) {
    const state = this.loadTourState();
    return !state.features[featureName];
  }

  /**
   * Mark feature tour as completed
   */
  markFeatureTourCompleted(featureName) {
    const state = this.loadTourState();
    state.features[featureName] = true;
    this.saveTourState(state);
  }

  /**
   * Get all completed features
   */
  getCompletedFeatures() {
    const state = this.loadTourState();
    return state.features;
  }

  /**
   * Static helper methods
   */

  /**
   * Create a new tour state manager
   */
  static create(tourName, version) {
    return new TourStateManager(tourName, version);
  }

  /**
   * Get tour statistics across all tours
   */
  static getTourStatistics() {
    const stats = {};
    
    // Find all tour-related keys in localStorage
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.includes('-tour-')) {
        const parts = key.split('-tour-');
        if (parts.length === 2) {
          const tourName = parts[0];
          const property = parts[1];
          
          if (!stats[tourName]) {
            stats[tourName] = {};
          }
          
          try {
            const value = localStorage.getItem(key);
            stats[tourName][property] = property === 'completed' || property === 'features' 
              ? JSON.parse(value) 
              : value;
          } catch (e) {
            stats[tourName][property] = localStorage.getItem(key);
          }
        }
      }
    }
    
    return stats;
  }

  /**
   * Clean up old tour data (useful for maintenance)
   */
  static cleanupOldTours(toursToKeep = []) {
    const allKeys = [];
    for (let i = 0; i < localStorage.length; i++) {
      allKeys.push(localStorage.key(i));
    }
    
    allKeys.forEach(key => {
      if (key && key.includes('-tour-')) {
        const tourName = key.split('-tour-')[0];
        if (!toursToKeep.includes(tourName)) {
          localStorage.removeItem(key);
        }
      }
    });
  }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TourStateManager;
}

// Global availability
window.TourStateManager = TourStateManager; 