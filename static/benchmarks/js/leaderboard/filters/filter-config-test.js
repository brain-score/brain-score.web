// Filter Configuration Testing Utilities
// Phase 1: Simple UI for testing filter state management

// Create a simple test interface
function createFilterTestInterface() {
  // Only create if we're in development/testing mode
  const existingTestPanel = document.getElementById('filterTestPanel');
  if (existingTestPanel) {
    existingTestPanel.remove();
  }
  
  const testPanel = document.createElement('div');
  testPanel.id = 'filterTestPanel';
  testPanel.style.cssText = `
    position: fixed;
    top: 10px;
    right: 10px;
    background: #f8f9fa;
    border: 2px solid #007bff;
    border-radius: 8px;
    padding: 15px;
    z-index: 1000;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    min-width: 250px;
  `;
  
  testPanel.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
      <strong style="color: #007bff;">🧪 Filter Config Test</strong>
      <button id="closeTestPanel" style="background: none; border: none; font-size: 16px; cursor: pointer;">×</button>
    </div>
    
    <div style="margin-bottom: 10px;">
      <strong>Public Data Filter:</strong>
      <span id="publicDataStatus" style="margin-left: 8px; padding: 2px 6px; border-radius: 4px;"></span>
    </div>
    
    <div style="display: flex; gap: 8px; margin-bottom: 10px;">
      <button id="togglePublicData" class="test-btn" style="
        background: #007bff; 
        color: white; 
        border: none; 
        padding: 6px 12px; 
        border-radius: 4px; 
        cursor: pointer;
        font-size: 12px;
      ">Toggle</button>
      
      <button id="resetFilters" class="test-btn" style="
        background: #6c757d; 
        color: white; 
        border: none; 
        padding: 6px 12px; 
        border-radius: 4px; 
        cursor: pointer;
        font-size: 12px;
      ">Reset</button>
    </div>
    
    <div style="font-size: 12px; color: #666;">
      <div>💡 Check browser console for detailed logs</div>
      <div>💡 Try: <code>filterDebug.runBasicTests()</code></div>
    </div>
  `;
  
  document.body.appendChild(testPanel);
  
  // Update status display
  updateTestStatus();
  
  // Setup event listeners
  setupTestEventListeners();
  
  console.log('🧪 Filter test interface created');
}

function updateTestStatus() {
  const statusElement = document.getElementById('publicDataStatus');
  if (!statusElement) return;
  
  const isVisible = window.filterVisibilityConfig.isVisible('public_data_only');
  
  statusElement.textContent = isVisible ? 'VISIBLE' : 'HIDDEN';
  statusElement.style.backgroundColor = isVisible ? '#d4edda' : '#f8d7da';
  statusElement.style.color = isVisible ? '#155724' : '#721c24';
}

function setupTestEventListeners() {
  // Toggle button
  const toggleBtn = document.getElementById('togglePublicData');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function() {
      console.log('🧪 Test button clicked - toggling public data filter');
      window.filterVisibilityConfig.toggle('public_data_only');
      updateTestStatus();
    });
  }
  
  // Reset button
  const resetBtn = document.getElementById('resetFilters');
  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      console.log('🧪 Test button clicked - resetting to defaults');
      window.filterVisibilityConfig.loadDefaults();
      updateTestStatus();
    });
  }
  
  // Close panel button
  const closeBtn = document.getElementById('closeTestPanel');
  if (closeBtn) {
    closeBtn.addEventListener('click', function() {
      const panel = document.getElementById('filterTestPanel');
      if (panel) {
        panel.remove();
        console.log('🧪 Test interface closed');
      }
    });
  }
}

// Function to show/hide the actual public data filter for testing
function testFilterVisibility() {
  const publicDataFilter = document.getElementById('publicDataFilter');
  if (!publicDataFilter) {
    console.warn('⚠️ Public data filter element not found');
    return false;
  }
  
  const filterGroup = publicDataFilter.closest('.filter-group');
  if (!filterGroup) {
    console.warn('⚠️ Filter group container not found');
    return false;
  }
  
  const isVisible = window.filterVisibilityConfig.isVisible('public_data_only');
  
  // Apply visibility
  filterGroup.style.display = isVisible ? 'block' : 'none';
  
  console.log(`🔄 Public data filter visibility applied: ${isVisible ? 'VISIBLE' : 'HIDDEN'}`);
  
  // Add visual indicator for testing
  addVisualIndicator(filterGroup, isVisible);
  
  return true;
}

function addVisualIndicator(element, isVisible) {
  // Remove existing indicator
  const existingIndicator = element.querySelector('.test-indicator');
  if (existingIndicator) {
    existingIndicator.remove();
  }
  
  // Add new indicator
  const indicator = document.createElement('div');
  indicator.className = 'test-indicator';
  indicator.style.cssText = `
    position: absolute;
    top: -10px;
    right: -10px;
    background: ${isVisible ? '#28a745' : '#dc3545'};
    color: white;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: bold;
    z-index: 1000;
    pointer-events: none;
  `;
  indicator.textContent = isVisible ? '👁️ VISIBLE' : '🚫 HIDDEN';
  
  // Make parent relative if needed
  if (window.getComputedStyle(element).position === 'static') {
    element.style.position = 'relative';
  }
  
  element.appendChild(indicator);
}

// Enhanced debug helper that includes actual DOM testing
window.filterDebug.testActualFilter = function() {
  console.log('🧪 Testing actual filter visibility in DOM...');
  
  const success = testFilterVisibility();
  if (success) {
    console.log('✅ Filter visibility test completed');
    console.log('💡 Check the "Public Data Only" filter in the advanced filters panel');
  } else {
    console.log('❌ Filter visibility test failed - filter elements not found');
    console.log('💡 Make sure the advanced filters panel is open');
  }
  
  return success;
};

// Global function to show test interface
window.showFilterTestInterface = function() {
  createFilterTestInterface();
};

// Initialize test utilities immediately
console.log('🧪 Filter test utilities loaded!');
console.log('💡 Try: showFilterTestInterface()');
console.log('💡 Try: filterDebug.testActualFilter()');
console.log('💡 Try: testFilterModal()');

// Try to trigger button setup since we found the button exists
setTimeout(() => {
  console.log('🎯 Attempting to trigger button setup...');
  if (typeof setupConfigureFiltersButton === 'function') {
    setupConfigureFiltersButton();
  } else if (typeof window.setupConfigureFiltersButton === 'function') {
    window.setupConfigureFiltersButton();
  } else {
    console.log('🔍 setupConfigureFiltersButton not found, will rely on modal initialization');
  }
}, 500);

// Setup backup button when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  setTimeout(() => {
    addBackupModalButton();
  }, 1000);
});

// Also try to add backup button after progressive loading
setTimeout(() => {
  if (!document.getElementById('backupConfigureBtn')) {
    addBackupModalButton();
  }
}, 3000);

// Add a backup modal button for testing
function addBackupModalButton() {
  setTimeout(() => {
    // Check if the main button exists
    const mainBtn = document.getElementById('configureFiltersBtn');
    if (!mainBtn) {
      console.log('🚨 Main configure button not found, adding backup button');
      
      const backupBtn = document.createElement('button');
      backupBtn.id = 'backupConfigureBtn';
      backupBtn.innerHTML = '🧪 Test Modal';
      backupBtn.style.cssText = `
        position: fixed;
        top: 60px;
        right: 10px;
        z-index: 999;
        background: #007bff;
        color: white;
        border: none;
        padding: 8px 12px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
      `;
      
      backupBtn.addEventListener('click', function() {
        console.log('🧪 Backup button clicked');
        if (window.testFilterModal) {
          window.testFilterModal();
        } else {
          console.log('🔧 testFilterModal not available');
        }
      });
      
      document.body.appendChild(backupBtn);
      console.log('✅ Backup modal button added');
    } else {
      console.log('✅ Main configure button found:', mainBtn);
    }
  }, 2000);
}
