/*
 * Tour Configuration Index
 * ========================
 * 
 * This file serves as the main entry point for the tour system.
 * It ensures all tour components are loaded in the correct order:
 * 
 * 1. tour-helpers.js - Shared state management and helper functions
 * 2. basic-tour-steps.js - Basic introduction tour configuration
 * 3. interactive-tour-steps.js - Advanced filtering demo tour configuration
 * 
 * This modular approach improves maintainability and allows multiple developers
 * to work on different tours simultaneously.
 * 
 * File Structure:
 * ===============
 * tour-configs/
 * ├── tour-helpers.js         (~360 lines) - State management & utilities
 * ├── basic-tour-steps.js     (~140 lines) - Basic tour steps
 * ├── interactive-tour-steps.js (~440 lines) - Interactive demo steps
 * └── leaderboard-steps.js    (this file)   - Index and legacy compatibility
 */

// Legacy compatibility - this file now acts as an index
// All tour configurations are loaded from separate files

// Note: The actual tour configurations are now in:
// - tour-helpers.js (required first for state management)
// - basic-tour-steps.js (for window.tourConfigs.defaultTour)
// - interactive-tour-steps.js (for window.tourConfigs.interactiveBenchmarkTour)

// Ensure tour configs namespace exists (compatibility)
window.tourConfigs = window.tourConfigs || {};

// Export note for developers
console.info('ℹ️ Tour system has been modularized. See tour-helpers.js, basic-tour-steps.js, and interactive-tour-steps.js'); 