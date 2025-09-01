// Filter Configuration State Management
// Phase 1: Minimal implementation for testing

// Complete filter registry for all available filters
const FILTER_REGISTRY = {
  // Benchmark Filters
  'benchmark_tree': {
    id: 'benchmark_tree',
    category: 'benchmarks',
    label: 'Benchmark Selection Tree',
    description: 'Interactive tree for selecting specific benchmarks',
    type: 'tree',
    elementId: 'benchmarkFilterPanel',
    containerSelector: '.benchmark-column',
    defaultVisible: true,
    required: false
  },
  
  // Model Property Filters
  'architecture': {
    id: 'architecture',
    category: 'model_properties',
    label: 'Architecture',
    description: 'Filter by model architecture type (e.g., ResNet, ViT)',
    type: 'dropdown',
    elementId: 'architectureFilter',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'model_family': {
    id: 'model_family',
    category: 'model_properties',
    label: 'Model Family',
    description: 'Filter by model family or series',
    type: 'dropdown',
    elementId: 'modelFamilyFilter',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'param_count': {
    id: 'param_count',
    category: 'model_properties',
    label: 'Parameter Count (M)',
    description: 'Filter by model parameter count range',
    type: 'range_slider',
    elementId: 'paramCountMin',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'model_size': {
    id: 'model_size',
    category: 'model_properties',
    label: 'Model Size (MB)',
    description: 'Filter by model size in megabytes',
    type: 'range_slider',
    elementId: 'modelSizeMin',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  
  // Benchmark Property Filters
  'public_data_only': {
    id: 'public_data_only',
    category: 'benchmark_properties',
    label: 'Public Data Only',
    description: 'Show only benchmarks with publicly available data',
    type: 'checkbox',
    elementId: 'publicDataFilter',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'brain_region': {
    id: 'brain_region',
    category: 'benchmark_properties',
    label: 'Brain Region',
    description: 'Filter by brain region (V1, V2, V4, IT)',
    type: 'checkbox_group',
    elementId: 'regionFilter',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'species': {
    id: 'species',
    category: 'benchmark_properties',
    label: 'Species',
    description: 'Filter by species (Human, Simian)',
    type: 'checkbox_group',
    elementId: 'speciesFilter',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'tasks': {
    id: 'tasks',
    category: 'benchmark_properties',
    label: 'Task Type',
    description: 'Filter by task or experiment type',
    type: 'checkbox_group',
    elementId: 'taskFilter',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  },
  'stimuli_count': {
    id: 'stimuli_count',
    category: 'benchmark_properties',
    label: 'Number of Stimuli',
    description: 'Filter by number of stimuli in benchmark',
    type: 'range_slider',
    elementId: 'stimuliCountMin',
    containerSelector: '.filter-group',
    defaultVisible: true,
    required: false
  }
};

// Keep backward compatibility
const MINIMAL_FILTER_REGISTRY = FILTER_REGISTRY;

// Global filter visibility configuration
window.filterVisibilityConfig = {
  // Set of visible filter IDs
  visible: new Set(),
  
  // Initialize from localStorage or defaults
  initialize() {
    console.log('🔧 Initializing filter visibility configuration...');
    
    const saved = localStorage.getItem('leaderboard_filter_visibility');
    if (saved) {
      try {
        const config = JSON.parse(saved);
        if (config.visible && Array.isArray(config.visible)) {
          this.visible = new Set(config.visible);
          console.log('✅ Loaded saved configuration:', Array.from(this.visible));
          return;
        }
      } catch (e) {
        console.warn('⚠️ Failed to parse saved configuration, using defaults');
      }
    }
    
    this.loadDefaults();
    console.log('✅ Initialized with defaults:', Array.from(this.visible));
  },
  
  // Load default visibility settings
  loadDefaults() {
    this.visible.clear();
    Object.values(FILTER_REGISTRY)
      .filter(filter => filter.defaultVisible)
      .forEach(filter => this.visible.add(filter.id));
    
    // Save defaults to localStorage
    this.save();
  },
  
  // Save configuration to localStorage
  save() {
    try {
      const config = {
        visible: Array.from(this.visible),
        timestamp: Date.now(),
        version: '1.0'
      };
      localStorage.setItem('leaderboard_filter_visibility', JSON.stringify(config));
      console.log('💾 Saved filter configuration to localStorage');
    } catch (e) {
      console.warn('⚠️ Failed to save filter configuration:', e);
    }
  },
  
  // Toggle filter visibility
  toggle(filterId) {
    const wasVisible = this.visible.has(filterId);
    
    if (wasVisible) {
      this.visible.delete(filterId);
      console.log(`🔄 Hidden filter: ${filterId}`);
    } else {
      this.visible.add(filterId);
      console.log(`🔄 Showed filter: ${filterId}`);
    }
    
    // Auto-save changes
    this.save();
    
    console.log('📊 Current visible filters:', Array.from(this.visible));
    return !wasVisible; // Return new visibility state
  },
  
  // Check if filter is visible
  isVisible(filterId) {
    return this.visible.has(filterId);
  },
  
  // Get current state as plain object (for debugging)
  getState() {
    return {
      visible: Array.from(this.visible),
      registry: MINIMAL_FILTER_REGISTRY
    };
  }
};

// Debug helper for console testing
window.filterDebug = {
  showCurrentState() {
    const state = window.filterVisibilityConfig.getState();
    console.log('🔍 Current Filter State:', state);
    return state;
  },
  
  testToggle(filterId) {
    console.log(`🧪 Testing toggle for: ${filterId}`);
    console.log('Before:', this.showCurrentState().visible);
    
    const newState = window.filterVisibilityConfig.toggle(filterId);
    
    console.log('After:', this.showCurrentState().visible);
    console.log(`Result: ${filterId} is now ${newState ? 'VISIBLE' : 'HIDDEN'}`);
    
    return newState;
  },
  
  resetToDefaults() {
    console.log('🔄 Resetting to defaults...');
    window.filterVisibilityConfig.loadDefaults();
    console.log('✅ Reset complete:', this.showCurrentState().visible);
  },
  
  // Test all available operations
  runBasicTests() {
    console.log('🧪 Running basic filter configuration tests...');
    console.log('');
    
    // Test 1: Initial state
    console.log('📋 Test 1: Initial State');
    this.showCurrentState();
    console.log('');
    
    // Test 2: Toggle off
    console.log('📋 Test 2: Toggle Public Data Filter OFF');
    this.testToggle('public_data_only');
    console.log('');
    
    // Test 3: Toggle on
    console.log('📋 Test 3: Toggle Public Data Filter ON');
    this.testToggle('public_data_only');
    console.log('');
    
    // Test 4: Reset
    console.log('📋 Test 4: Reset to Defaults');
    this.resetToDefaults();
    console.log('');
    
    console.log('🎉 Basic tests completed!');
    console.log('💡 Try: filterDebug.testToggle("public_data_only")');
    console.log('💡 Try: filterDebug.showCurrentState()');
  }
};

// Auto-initialize when script loads (immediately, not waiting for DOM)
console.log('🔧 Loading Filter Configuration State Management...');

try {
  // Make FILTER_REGISTRY globally available for debugging
  window.FILTER_REGISTRY = FILTER_REGISTRY;
  console.log('✅ FILTER_REGISTRY loaded with', Object.keys(FILTER_REGISTRY).length, 'filters');
  
  window.filterVisibilityConfig.initialize();
  console.log('✅ filterVisibilityConfig initialized successfully');
} catch (error) {
  console.error('❌ Error initializing filter configuration:', error);
  console.log('🔍 FILTER_REGISTRY:', FILTER_REGISTRY);
  console.log('🔍 filterVisibilityConfig:', window.filterVisibilityConfig);
}

// Add helpful console message
console.log('🚀 Filter Configuration System Loaded!');
console.log('💡 Try: filterDebug.runBasicTests()');
console.log('💡 Try: filterDebug.testToggle("public_data_only")');

// Also initialize when DOM is ready as fallback
document.addEventListener('DOMContentLoaded', function() {
  if (!window.filterVisibilityConfig.visible || window.filterVisibilityConfig.visible.size === 0) {
    console.log('🔄 Re-initializing filter config (DOM ready fallback)');
    window.filterVisibilityConfig.initialize();
  }
});
