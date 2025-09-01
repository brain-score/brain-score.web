// Dynamic Filter Renderer
// Phase 3: Implement actual showing/hiding of filters based on configuration

class FilterRenderer {
  constructor() {
    this.visibilityConfig = window.filterVisibilityConfig;
    this.filterElements = new Map();
    this.initialized = false;
  }
  
  // Initialize the renderer by mapping filters to their DOM elements
  initialize() {
    console.log('🎨 Initializing Filter Renderer...');
    
    // Map filters to their actual DOM elements
    this.mapFilterElements();
    
    this.initialized = true;
    console.log('✅ Filter Renderer initialized with', this.filterElements.size, 'filter elements');
    
    // Apply initial visibility state
    this.applyFilterVisibility();
  }
  
  // Map filter IDs to their actual DOM elements
  mapFilterElements() {
    // Use the registry from our state management
    const registry = window.FILTER_REGISTRY || {};
    
    Object.values(registry).forEach(filter => {
      const selector = `#${filter.elementId}`;
      const element = document.querySelector(selector);
      const container = element?.closest(filter.containerSelector);
      
      if (element && container) {
        this.filterElements.set(filter.id, {
          element,
          container,
          originalDisplay: window.getComputedStyle(container).display,
          filter
        });
        console.log(`🔗 Mapped filter: ${filter.id} (${filter.type}) →`, container);
      } else {
        console.warn(`⚠️ Could not find filter element for: ${filter.id}`);
        console.log('🔍 Selector:', selector);
        console.log('🔍 Element found:', element);
        console.log('🔍 Container found:', container);
        console.log('🔍 Filter config:', filter);
      }
    });
  }
  
  // Apply current filter visibility configuration
  applyFilterVisibility() {
    if (!this.initialized) {
      console.warn('🎨 Renderer not initialized, skipping visibility update');
      return;
    }
    
    console.log('🎨 Applying filter visibility configuration...');
    
    this.filterElements.forEach((elementData, filterId) => {
      const isVisible = this.visibilityConfig.isVisible(filterId);
      this.setFilterVisibility(filterId, isVisible);
    });
    
    console.log('✅ Filter visibility applied');
  }
  
  // Set visibility for a specific filter
  setFilterVisibility(filterId, isVisible) {
    const elementData = this.filterElements.get(filterId);
    if (!elementData) {
      console.warn(`⚠️ No element data for filter: ${filterId}`);
      return;
    }
    
    const { container, originalDisplay } = elementData;
    
    if (isVisible) {
      container.style.display = originalDisplay || 'block';
      container.classList.remove('filter-hidden');
      console.log(`👁️ Showed filter: ${filterId}`);
    } else {
      container.style.display = 'none';
      container.classList.add('filter-hidden');
      console.log(`🚫 Hidden filter: ${filterId}`);
    }
    
    // Add visual indicator for testing
    this.addVisualIndicator(container, isVisible, filterId);
  }
  
  // Add visual indicator for testing (we'll remove this later)
  addVisualIndicator(container, isVisible, filterId) {
    // Remove existing indicator
    const existingIndicator = container.querySelector('.visibility-indicator');
    if (existingIndicator) {
      existingIndicator.remove();
    }
    
    // Get filter info for better indicator
    const elementData = this.filterElements.get(filterId);
    const filterType = elementData?.filter?.type || 'unknown';
    const filterLabel = elementData?.filter?.label || filterId;
    
    // Add new indicator
    const indicator = document.createElement('div');
    indicator.className = 'visibility-indicator';
    indicator.style.cssText = `
      position: absolute;
      top: -5px;
      right: -5px;
      background: ${isVisible ? '#28a745' : '#dc3545'};
      color: white;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 10px;
      font-weight: bold;
      z-index: 1000;
      pointer-events: none;
      transition: all 0.3s ease;
      box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    `;
    
    const typeIcons = {
      'checkbox': '☑️',
      'dropdown': '📋',
      'range_slider': '🎚️',
      'checkbox_group': '☑️',
      'tree': '🌳'
    };
    
    const typeIcon = typeIcons[filterType] || '⚙️';
    indicator.innerHTML = `${typeIcon} ${isVisible ? 'SHOWN' : 'HIDDEN'}`;
    indicator.title = `${filterLabel} (${filterType})`;
    
    // Make container relative if needed
    if (window.getComputedStyle(container).position === 'static') {
      container.style.position = 'relative';
    }
    
    container.appendChild(indicator);
    
    // Remove indicator after 4 seconds
    setTimeout(() => {
      if (indicator.parentNode) {
        indicator.remove();
      }
    }, 4000);
  }
  
  // Toggle visibility for a filter
  toggleFilterVisibility(filterId) {
    const currentVisibility = this.visibilityConfig.isVisible(filterId);
    const newVisibility = this.visibilityConfig.toggle(filterId);
    
    this.setFilterVisibility(filterId, newVisibility);
    
    return newVisibility;
  }
  
  // Refresh renderer (re-scan for elements and apply visibility)
  refresh() {
    console.log('🔄 Refreshing filter renderer...');
    this.filterElements.clear();
    this.mapFilterElements();
    this.applyFilterVisibility();
  }
  
  // Get status of all filters
  getFilterStatus() {
    const status = {};
    
    this.filterElements.forEach((elementData, filterId) => {
      const isVisible = this.visibilityConfig.isVisible(filterId);
      const container = elementData.container;
      const actuallyVisible = container.style.display !== 'none';
      
      status[filterId] = {
        configuredVisible: isVisible,
        actuallyVisible: actuallyVisible,
        element: elementData.element,
        container: container,
        inSync: isVisible === actuallyVisible
      };
    });
    
    return status;
  }
}

// Global filter renderer instance
window.filterRenderer = null;

// Initialize the filter renderer
function initializeFilterRenderer() {
  console.log('🎨 Creating Filter Renderer...');
  
  if (!window.filterVisibilityConfig) {
    console.warn('🎨 filterVisibilityConfig not available, cannot initialize renderer');
    return null;
  }
  
  window.filterRenderer = new FilterRenderer();
  
  // Small delay to ensure all DOM elements are ready
  setTimeout(() => {
    window.filterRenderer.initialize();
  }, 100);
  
  return window.filterRenderer;
}

// Update the modal's applyConfiguration to actually render filters
if (window.filterConfigModal) {
  const originalApplyConfiguration = window.filterConfigModal.applyConfiguration;
  window.filterConfigModal.applyConfiguration = function() {
    console.log('🎭 Applying filter configuration with rendering...');
    console.log('📊 Current state:', window.filterVisibilityConfig.getState());
    
    // Apply the filter visibility
    if (window.filterRenderer) {
      window.filterRenderer.applyFilterVisibility();
    } else {
      console.warn('🎨 Filter renderer not available, initializing...');
      initializeFilterRenderer();
      setTimeout(() => {
        if (window.filterRenderer) {
          window.filterRenderer.applyFilterVisibility();
        }
      }, 200);
    }
    
    console.log('✅ Configuration applied with rendering!');
    this.close();
  };
}

// Debug helpers
window.filterRendererDebug = {
  showStatus() {
    if (!window.filterRenderer) {
      console.log('❌ Filter renderer not initialized');
      return;
    }
    
    const status = window.filterRenderer.getFilterStatus();
    console.log('🎨 Filter Renderer Status:', status);
    return status;
  },
  
  testToggle(filterId) {
    if (!window.filterRenderer) {
      console.log('❌ Filter renderer not initialized');
      return;
    }
    
    console.log(`🧪 Testing toggle for ${filterId}...`);
    const newVisibility = window.filterRenderer.toggleFilterVisibility(filterId);
    console.log(`✅ ${filterId} is now ${newVisibility ? 'VISIBLE' : 'HIDDEN'}`);
    
    return newVisibility;
  },
  
  refresh() {
    if (!window.filterRenderer) {
      console.log('❌ Filter renderer not initialized');
      return;
    }
    
    window.filterRenderer.refresh();
  },
  
  initialize() {
    initializeFilterRenderer();
  }
};

console.log('🎨 Filter Renderer loaded!');
console.log('💡 Try: filterRendererDebug.showStatus()');
console.log('💡 Try: filterRendererDebug.testToggle("public_data_only")');

// Auto-initialize when leaderboard template initialization completes
if (typeof window.setupEventHandlers === 'function') {
  const originalSetupEventHandlers = window.setupEventHandlers;
  
  window.setupEventHandlers = function() {
    // Call original function
    if (originalSetupEventHandlers) {
      originalSetupEventHandlers();
    }
    
    // Initialize filter renderer after a delay
    setTimeout(() => {
      if (!window.filterRenderer) {
        console.log('🎨 Auto-initializing filter renderer...');
        initializeFilterRenderer();
      }
    }, 300);
  };
}
