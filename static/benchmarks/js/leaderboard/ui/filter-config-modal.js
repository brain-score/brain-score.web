// Filter Configuration Modal
// Phase 2: Basic Modal UI with toggle functionality

class FilterConfigModal {
  constructor() {
    this.modal = null;
    this.isOpen = false;
    this.initialize();
  }
  
  initialize() {
    console.log('🎭 Initializing Filter Configuration Modal...');
    this.createModal();
    this.setupEventListeners();
    console.log('✅ Filter Configuration Modal ready');
  }
  
  createModal() {
    // Remove existing modal if it exists
    const existingModal = document.getElementById('filterConfigModal');
    if (existingModal) {
      existingModal.remove();
    }
    
    // Create modal HTML
    const modalHTML = `
      <div id="filterConfigModal" class="filter-config-modal hidden">
        <div class="modal-overlay"></div>
        <div class="modal-content">
          <div class="modal-header">
            <h3>🔧 Configure Visible Filters</h3>
            <div class="header-controls">
              <button id="toggleAllFilters" class="btn btn-secondary btn-sm">Hide All</button>
              <button class="modal-close" aria-label="Close">×</button>
            </div>
          </div>
          
          <div class="modal-body">
            <p style="margin-bottom: 16px; color: #666; font-size: 14px;">
              Choose which filters to display in the Advanced Filters panel.
            </p>
            
            <div class="filter-categories">
              <!-- Benchmark Filters -->
              <div class="filter-category">
                <h4>📊 Benchmark Filters</h4>
                <div class="filter-list" id="benchmarkFilterList">
                  <!-- Will be populated dynamically -->
                </div>
              </div>
              
              <!-- Model Property Filters -->
              <div class="filter-category">
                <h4>🤖 Model Properties</h4>
                <div class="filter-list" id="modelPropertyFilterList">
                  <!-- Will be populated dynamically -->
                </div>
              </div>
              
              <!-- Benchmark Property Filters -->
              <div class="filter-category">
                <h4>🧠 Benchmark Properties</h4>
                <div class="filter-list" id="benchmarkPropertyFilterList">
                  <!-- Will be populated dynamically -->
                </div>
              </div>
            </div>
            
            <div style="margin-top: 16px; padding: 8px 12px; background: #f8f9fa; border-radius: 4px; font-size: 11px; color: #666;">
              <strong>💡 Tip:</strong> Hide unused filters to simplify the interface. Settings are automatically saved.
            </div>
          </div>
          
          <div class="modal-footer">
            <button id="resetToDefaults" class="btn btn-secondary">🔄 Reset to Defaults</button>
            <button id="applyFilterConfig" class="btn btn-primary">✅ Apply Configuration</button>
            <button id="closeModal" class="btn btn-secondary">❌ Close</button>
          </div>
        </div>
      </div>
    `;
    
    // Add to document
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    this.modal = document.getElementById('filterConfigModal');
    
    // Populate filter list
    this.populateFilterList();
  }
  
  populateFilterList() {
    // Get filters from our registry
    const registry = window.filterVisibilityConfig ? 
      Object.values(FILTER_REGISTRY) : [];
    
    if (registry.length === 0) {
      console.warn('No filters available in registry');
      return;
    }
    
    // Group filters by category
    const filtersByCategory = {
      benchmarks: [],
      model_properties: [],
      benchmark_properties: []
    };
    
    registry.forEach(filter => {
      if (filtersByCategory[filter.category]) {
        filtersByCategory[filter.category].push(filter);
      }
    });
    
    // Populate each category
    this.populateFilterCategory('benchmarkFilterList', filtersByCategory.benchmarks);
    this.populateFilterCategory('modelPropertyFilterList', filtersByCategory.model_properties);
    this.populateFilterCategory('benchmarkPropertyFilterList', filtersByCategory.benchmark_properties);
    
    // Setup toggle event listeners
    this.setupToggleListeners();
  }
  
  populateFilterCategory(containerId, filters) {
    const container = document.getElementById(containerId);
    if (!container) {
      console.warn(`Container ${containerId} not found`);
      return;
    }
    
    if (filters.length === 0) {
      container.innerHTML = '<p style="color: #999; font-style: italic;">No filters in this category</p>';
      return;
    }
    
    container.innerHTML = '';
    
    filters.forEach(filter => {
      const isVisible = window.filterVisibilityConfig.isVisible(filter.id);
      
      const filterItem = document.createElement('div');
      filterItem.className = 'filter-item';
      
      // Add type indicator
      const typeIcon = this.getTypeIcon(filter.type);
      
      filterItem.innerHTML = `
        <div class="filter-info">
          <div class="filter-label">${typeIcon} ${filter.label}</div>
          <div class="filter-description">${filter.description || 'No description'}</div>
        </div>
        <div class="filter-toggle">
          <label class="toggle-switch" title="${isVisible ? 'Click to hide' : 'Click to show'}">
            <input type="checkbox" data-filter-id="${filter.id}" ${isVisible ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
        </div>
      `;
      
      container.appendChild(filterItem);
    });
  }
  
  getTypeIcon(type) {
    const icons = {
      'checkbox': '☑️',
      'dropdown': '📋',
      'range_slider': '🎚️',
      'checkbox_group': '☑️',
      'tree': '🌳'
    };
    return icons[type] || '⚙️';
  }
  
  setupToggleListeners() {
    const toggles = this.modal.querySelectorAll('input[data-filter-id]');
    console.log(`🎭 Setting up ${toggles.length} toggle listeners`);
    
    toggles.forEach(toggle => {
      toggle.addEventListener('change', (e) => {
        const filterId = e.target.getAttribute('data-filter-id');
        console.log(`🎭 Modal toggle changed for ${filterId}:`, e.target.checked);
        
        // Check if filterVisibilityConfig exists
        if (!window.filterVisibilityConfig) {
          console.error('❌ filterVisibilityConfig not available!');
          return;
        }
        
        // Update our state
        const currentState = window.filterVisibilityConfig.isVisible(filterId);
        console.log(`🔍 Current state for ${filterId}:`, currentState, '→', e.target.checked);
        
        if (currentState !== e.target.checked) {
          const newState = window.filterVisibilityConfig.toggle(filterId);
          console.log(`✅ Toggled ${filterId} to:`, newState);
        }
        
        // Visual state is handled by the toggle switch itself
      });
    });
  }
  

  
  setupEventListeners() {
    // Wait for modal to be created
    setTimeout(() => {
      if (!this.modal) return;
      
      // Close modal events
      const closeBtn = this.modal.querySelector('.modal-close');
      const closeModalBtn = this.modal.querySelector('#closeModal');
      const overlay = this.modal.querySelector('.modal-overlay');
      
      if (closeBtn) closeBtn.addEventListener('click', () => this.close());
      if (closeModalBtn) closeModalBtn.addEventListener('click', () => this.close());
      if (overlay) overlay.addEventListener('click', () => this.close());
      
      // Escape key handling
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.close();
        }
      });
      
      // Reset to defaults
      const resetBtn = this.modal.querySelector('#resetToDefaults');
      if (resetBtn) {
        resetBtn.addEventListener('click', () => {
          console.log('🎭 Modal: Reset to defaults clicked');
          window.filterVisibilityConfig.loadDefaults();
          this.populateFilterList(); // Refresh the display
        });
      }
      
      // Apply configuration
      const applyBtn = this.modal.querySelector('#applyFilterConfig');
      if (applyBtn) {
        applyBtn.addEventListener('click', () => {
          console.log('🎭 Modal: Apply configuration clicked');
          this.applyConfiguration();
        });
      }
      
      // Toggle all filters
      const toggleAllBtn = this.modal.querySelector('#toggleAllFilters');
      if (toggleAllBtn) {
        toggleAllBtn.addEventListener('click', () => {
          this.toggleAllFilters();
        });
      }
      
    }, 100);
  }
  
  open() {
    if (!this.modal) {
      console.warn('🎭 Modal not initialized');
      return;
    }
    
    console.log('🎭 Opening filter configuration modal');
    
    // Refresh filter list with current state
    this.populateFilterList();
    
    // Update toggle all button text
    this.updateToggleAllButton();
    
    // Show modal
    this.modal.classList.remove('hidden');
    this.isOpen = true;
    document.body.style.overflow = 'hidden';
    
    // Focus management for accessibility
    const closeBtn = this.modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.focus();
  }
  
  updateToggleAllButton() {
    const registry = Object.values(FILTER_REGISTRY);
    const visibleCount = registry.filter(filter => window.filterVisibilityConfig.isVisible(filter.id)).length;
    const totalCount = registry.length;
    
    const toggleAllBtn = this.modal.querySelector('#toggleAllFilters');
    if (toggleAllBtn) {
      if (visibleCount === 0) {
        toggleAllBtn.textContent = 'Show All';
      } else if (visibleCount === totalCount) {
        toggleAllBtn.textContent = 'Hide All';
      } else {
        toggleAllBtn.textContent = `Hide All (${visibleCount}/${totalCount})`;
      }
    }
  }
  
  close() {
    if (!this.modal) return;
    
    console.log('🎭 Closing filter configuration modal');
    
    this.modal.classList.add('hidden');
    this.isOpen = false;
    document.body.style.overflow = '';
  }
  
  toggleAllFilters() {
    console.log('🎭 Toggle all filters clicked');
    
    // Get current state of all filters
    const registry = Object.values(FILTER_REGISTRY);
    const visibleCount = registry.filter(filter => window.filterVisibilityConfig.isVisible(filter.id)).length;
    const totalCount = registry.length;
    
    // If most filters are visible, hide all. If most are hidden, show all
    const shouldShowAll = visibleCount < totalCount / 2;
    
    console.log(`🎭 ${visibleCount}/${totalCount} filters visible, ${shouldShowAll ? 'showing' : 'hiding'} all`);
    
    // Update all filters
    registry.forEach(filter => {
      const currentlyVisible = window.filterVisibilityConfig.isVisible(filter.id);
      if (currentlyVisible !== shouldShowAll) {
        window.filterVisibilityConfig.toggle(filter.id);
      }
    });
    
    // Refresh the modal display
    this.populateFilterList();
    
    // Update button text
    this.updateToggleAllButton();
  }
  
  applyConfiguration() {
    console.log('🎭 Applying filter configuration...');
    console.log('📊 Current state:', window.filterVisibilityConfig.getState());
    
    // Phase 3: Apply actual filter visibility using the renderer
    if (window.filterRenderer) {
      console.log('🎨 Using filter renderer to apply changes...');
      window.filterRenderer.applyFilterVisibility();
      console.log('✅ Configuration applied with dynamic rendering!');
    } else {
      console.warn('🎨 Filter renderer not available, trying to initialize...');
      // Try to initialize renderer if it doesn't exist
      if (typeof initializeFilterRenderer === 'function') {
        initializeFilterRenderer();
        setTimeout(() => {
          if (window.filterRenderer) {
            window.filterRenderer.applyFilterVisibility();
            console.log('✅ Configuration applied after renderer initialization!');
          } else {
            console.log('⚠️ Could not initialize filter renderer');
          }
        }, 200);
      } else {
        console.log('⚠️ Filter renderer functionality not available (Phase 2 mode)');
      }
    }
    
    this.close();
  }
}

// CSS Styles for the modal and advanced filters header
const modalStyles = `
<style>
/* Advanced Filters Gear Icon */
#advancedFiltersPanel {
  position: relative;
}

.configure-filters-gear {
  position: absolute;
  top: 4px;
  right: 4px;
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  color: #666;
  padding: 4px;
  margin: 0;
  line-height: 1;
  z-index: 10;
}

.filter-config-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter-config-modal.hidden {
  display: none;
}

.filter-config-modal .modal-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(2px);
}

.filter-config-modal .modal-content {
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  max-width: 700px;
  max-height: 85vh;
  width: 95%;
  overflow: hidden;
  position: relative;
  z-index: 1001;
}

.filter-config-modal .modal-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e9ecef;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8f9fa;
}

.filter-config-modal .modal-header h3 {
  margin: 0;
  color: #333;
  font-size: 1.25rem;
}

.filter-config-modal .header-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.filter-config-modal .btn-sm {
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 4px;
  border: 1px solid #dee2e6;
  background: white;
  color: #495057;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-config-modal .btn-sm:hover {
  background: #e9ecef;
  border-color: #adb5bd;
}

.filter-config-modal .modal-close {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #666;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.filter-config-modal .modal-close:hover {
  background: #e9ecef;
  color: #333;
}

.filter-config-modal .modal-body {
  padding: 16px 20px;
  max-height: 60vh;
  overflow-y: auto;
}

.filter-config-modal .filter-category h4 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 1rem;
  padding-bottom: 6px;
  border-bottom: 2px solid #e9ecef;
}

.filter-config-modal .filter-category {
  margin-bottom: 20px;
}

.filter-config-modal .filter-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f8f9fa;
}

.filter-config-modal .filter-item:last-child {
  border-bottom: none;
}

.filter-config-modal .filter-info {
  flex: 1;
  min-width: 0;
}

.filter-config-modal .filter-label {
  font-weight: 500;
  color: #333;
  margin-bottom: 2px;
  font-size: 14px;
}

.filter-config-modal .filter-description {
  font-size: 12px;
  color: #666;
  line-height: 1.3;
  margin: 0;
}

.filter-config-modal .filter-status {
  font-size: 0.8rem;
  color: #888;
}

.filter-config-modal .status-indicator.visible {
  color: #28a745;
  font-weight: bold;
}

.filter-config-modal .status-indicator.hidden {
  color: #dc3545;
  font-weight: bold;
}

.filter-config-modal .filter-toggle {
  margin-left: 16px;
}

.filter-config-modal .toggle-switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 24px;
}

.filter-config-modal .toggle-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.filter-config-modal .toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: 0.3s;
  border-radius: 24px;
}

.filter-config-modal .toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

.filter-config-modal input:checked + .toggle-slider {
  background-color: #007bff;
}

.filter-config-modal input:checked + .toggle-slider:before {
  transform: translateX(26px);
}

.filter-config-modal .modal-footer {
  padding: 12px 20px;
  border-top: 1px solid #e9ecef;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  background: #f8f9fa;
}

.filter-config-modal .btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.filter-config-modal .btn-primary {
  background: #007bff;
  color: white;
}

.filter-config-modal .btn-primary:hover {
  background: #0056b3;
}

.filter-config-modal .btn-secondary {
  background: #6c757d;
  color: white;
}

.filter-config-modal .btn-secondary:hover {
  background: #545b62;
}
</style>
`;

// Add styles to document
document.head.insertAdjacentHTML('beforeend', modalStyles);

// Global instance
window.filterConfigModal = null;

// Initialize filter configuration system
function initializeFilterConfigSystem() {
  console.log('🎭 Initializing Filter Configuration System...');
  
  if (window.filterVisibilityConfig) {
    window.filterConfigModal = new FilterConfigModal();
    console.log('🎭 Filter Configuration Modal initialized!');
    console.log('💡 Try: filterConfigModal.open()');
    
    // Setup the configure filters button
    setupConfigureFiltersButtonWithRetry();
  } else {
    console.warn('🎭 filterVisibilityConfig not available');
  }
}

// Hook into the leaderboard initialization process
// Since setupEventHandlers is defined inline, we'll hook into initializeLeaderboardFromTemplate instead
if (typeof window.LeaderboardTemplateInitialization === 'undefined') {
  window.LeaderboardTemplateInitialization = {};
}

// Store the original initializeLeaderboardFromTemplate if it exists
const originalInitializeLeaderboardFromTemplate = window.initializeLeaderboardFromTemplate;

// Override initializeLeaderboardFromTemplate to include our initialization
window.initializeLeaderboardFromTemplate = function() {
  // Call the original function first
  if (originalInitializeLeaderboardFromTemplate) {
    originalInitializeLeaderboardFromTemplate();
  }
  
  // Add our filter configuration system after everything else is set up
  console.log('🎭 Setting up filter configuration system...');
  setTimeout(() => {
    initializeFilterConfigSystem();
  }, 200);
};

// Fallback: Also try to initialize when DOM is ready (for cases where progressive loader doesn't run)
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(() => {
    if (!window.filterConfigModal) {
      console.log('🎭 Fallback initialization...');
      initializeFilterConfigSystem();
    }
  }, 2000);
});

// Also provide a manual way to test the modal
window.testFilterModal = function() {
  console.log('🧪 Manual modal test...');
  if (window.filterConfigModal) {
    window.filterConfigModal.open();
  } else {
    console.log('🔧 Creating modal manually...');
    initializeFilterConfigSystem();
    setTimeout(() => {
      if (window.filterConfigModal) {
        window.filterConfigModal.open();
      }
    }, 100);
  }
};

// Setup the configure filters button
function setupConfigureFiltersButton() {
  console.log('🔍 Looking for configureFiltersBtn...');
  
  const configBtn = document.getElementById('configureFiltersBtn');
  console.log('🔍 Found button:', configBtn);
  
  if (configBtn) {
    console.log('🔍 Button innerHTML:', configBtn.innerHTML);
    
    // Check if event listener is already attached
    if (configBtn.hasAttribute('data-modal-listener')) {
      console.log('🔍 Button already has event listener');
      return;
    }
    
    configBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      console.log('🎭 Configure Filters button clicked!');
      
      if (window.filterConfigModal) {
        console.log('🎭 Opening modal...');
        window.filterConfigModal.open();
      } else {
        console.warn('🎭 Filter configuration modal not available, creating it...');
        console.log('🔍 window.filterConfigModal is:', window.filterConfigModal);
        // Try to create modal on demand
        if (window.filterVisibilityConfig) {
          window.filterConfigModal = new FilterConfigModal();
          setTimeout(() => {
            if (window.filterConfigModal) {
              window.filterConfigModal.open();
            }
          }, 100);
        }
      }
    });
    
    // Mark that we've added the listener
    configBtn.setAttribute('data-modal-listener', 'true');
    
    // Also add a test click handler
    configBtn.style.cursor = 'pointer';
    configBtn.title = 'Configure which filters are visible (Phase 2 Testing)';
    
    console.log('✅ Configure Filters button connected to modal');
  } else {
    console.warn('🎭 Configure Filters button not found');
    console.log('🔍 All buttons on page:', document.querySelectorAll('button'));
  }
}

// Alternative setup function that tries multiple times
function setupConfigureFiltersButtonWithRetry() {
  // Since the button was found, just set it up directly
  console.log('🔄 Setting up configure button...');
  setupConfigureFiltersButton();
  
  // But also add a fallback timer in case we need to retry
  setTimeout(() => {
    const configBtn = document.getElementById('configureFiltersBtn');
    if (configBtn && !configBtn.hasAttribute('data-modal-listener')) {
      console.log('🔄 Retry: Setting up configure button...');
      setupConfigureFiltersButton();
    }
  }, 1000);
}
