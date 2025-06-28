/*
 * Enhanced Tour State Management System
 * =====================================
 * 
 * This system provides comprehensive state tracking and restoration for interactive tours:
 * 
 * 1. INITIALIZATION:
 *    - tourStepState.initialize() captures the complete initial state when tour starts
 *    - Original values stored for all checkboxes, tree nodes, columns, and expansions
 * 
 * 2. STEP TRACKING:
 *    - Each beforeShow callback calls recordCurrentStateForStep() before making changes
 *    - State snapshots stored for each step to enable accurate backward navigation
 * 
 * 3. NAVIGATION:
 *    - Forward: Changes applied and state recorded automatically
 *    - Backward: Previous step state restored via onPrevClick() → restoreState()
 * 
 * 4. CLEANUP:
 *    - Tour completion/cancellation: resetToOriginal() restores complete initial state
 *    - All filters, expansions, and selections returned to starting configuration
 * 
 * 5. FALLBACK SUPPORT:
 *    - Enhanced system preferred, legacy restoration methods as fallback
 *    - Comprehensive error handling and validation throughout
 */

// Initialize tour configurations namespace
window.tourConfigs = window.tourConfigs || {};

// Helper Functions for Tour
// Expand header columns to show child benchmarks
function expandBenchmarkHeaders(columnIds) {
  columnIds.forEach(columnId => {
    // Find the header cell by column ID
    const headerCell = document.querySelector(`.ag-header-cell[col-id="${columnId}"]`);
    if (headerCell) {
      const expandToggle = headerCell.querySelector('.expand-toggle');
      if (expandToggle && expandToggle.textContent === '▾') {
        // Only click if it's currently collapsed (showing downward arrow)
        expandToggle.click();
      }
    }
  });
}

// Enhanced state management for tour step navigation and cleanup
window.tourStepState = {
  currentStep: 0,
  states: new Map(),
  initialState: null,
  originalValues: new Map(),
  
  // Initialize and capture the starting state
  initialize() {
    this.clear();
    this.captureOriginalValues();
    this.initialState = this.getCurrentState();
  },
  
  // Capture original values for complete reset
  captureOriginalValues() {
    this.originalValues.clear();
    
    // Capture all benchmark checkbox states
    document.querySelectorAll('input[type="checkbox"][value]').forEach(checkbox => {
      this.originalValues.set(`checkbox_${checkbox.value}`, checkbox.checked);
    });
    
    // Capture all tree node expansion states
    document.querySelectorAll('.benchmark-node').forEach((node, index) => {
      const input = node.querySelector('input[value]');
      const identifier = input ? `node_${input.value}` : `node_${index}`;
      this.originalValues.set(identifier, !node.classList.contains('collapsed'));
    });
    
    // Capture AG-Grid column states if available
    if (window.globalGridApi) {
      const allColumns = window.globalGridApi.getColumns();
      if (allColumns) {
        allColumns.forEach(column => {
          this.originalValues.set(`column_${column.getColId()}`, column.isVisible());
        });
      }
    }
    
    // Capture column expansion states
    if (window.columnExpansionState) {
      window.columnExpansionState.forEach((expanded, colId) => {
        this.originalValues.set(`expansion_${colId}`, expanded);
      });
    }
  },
  
  // Record the state before making changes
  recordState(stepIndex, stateData) {
    this.states.set(stepIndex, stateData);
  },
  
  // Helper function to record state before making changes in a beforeShow callback
  recordCurrentStateForStep(stepIndex) {
    if (!this.states.has(stepIndex)) {
      this.recordState(stepIndex, this.getCurrentState());
    }
  },
  
  // Restore state when going backward
  restoreState(stepIndex) {
    const state = this.states.get(stepIndex);
    if (!state) return;
    
    // Restore collapsed/expanded states
    if (state.collapsedNodes) {
      state.collapsedNodes.forEach(nodeSelector => {
        const node = document.querySelector(nodeSelector);
        if (node && !node.classList.contains('collapsed')) {
          const toggle = node.querySelector('.tree-toggle');
          if (toggle) toggle.click();
        }
      });
    }
    
    // Restore checkbox states
    if (state.checkboxStates) {
      state.checkboxStates.forEach((checked, selector) => {
        const checkbox = document.querySelector(selector);
        if (checkbox && checkbox.checked !== checked) {
          checkbox.checked = checked;
          
          // Trigger change event
          const changeEvent = new Event('change', { bubbles: true });
          checkbox.dispatchEvent(changeEvent);
        }
      });
      
      // Update grid after checkbox changes
      setTimeout(() => {
        if (window.updateExclusions) window.updateExclusions();
        if (window.applyCombinedFilters) window.applyCombinedFilters();
      }, 100);
    }
    
    // Restore AG-Grid column visibility states
    if (state.columnStates && window.globalGridApi) {
      const columnStateArray = [];
      state.columnStates.forEach((visible, colId) => {
        columnStateArray.push({ colId, hide: !visible });
      });
      
      if (columnStateArray.length > 0) {
        window.globalGridApi.applyColumnState({ state: columnStateArray });
      }
    }
    
    // Restore column expansion states
    if (state.expandedColumns && window.columnExpansionState) {
      // First, collapse all columns that should be collapsed
      const keyColumns = ['neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0', 'V1_v0', 'V2_v0', 'V4_v0', 'IT_v0'];
      keyColumns.forEach(colId => {
        if (!state.expandedColumns.has(colId) && window.columnExpansionState.get(colId) === true) {
          // Column should be collapsed but is currently expanded
          const headerCell = document.querySelector(`.ag-header-cell[col-id="${colId}"]`);
          if (headerCell) {
            const expandToggle = headerCell.querySelector('.expand-toggle');
            if (expandToggle && expandToggle.textContent === '▴') {
              expandToggle.click();
            }
          }
        }
      });
    }
  },
  
  // Get current DOM state for recording
  getCurrentState() {
    const collapsedNodes = [];
    const checkboxStates = new Map();
    const columnStates = new Map();
    const expandedColumns = new Set();
    
    // Record expanded/collapsed benchmark nodes
    document.querySelectorAll('.benchmark-node.collapsed').forEach(node => {
      const input = node.querySelector('input[value]');
      if (input) {
        collapsedNodes.push(`input[value="${input.value}"]`);
      }
    });
    
    // Record checkbox states for key benchmarks
    const keyCheckboxes = [
      'input[value="neural_vision_v0"]',
      'input[value="V1_v0"]', 
      'input[value="FreemanZiemba2013.V1-pls_v2"]',
      'input[value="behavior_vision_v0"]',
      'input[value="engineering_vision_v0"]'
    ];
    
    keyCheckboxes.forEach(selector => {
      const checkbox = document.querySelector(selector);
      if (checkbox) {
        checkboxStates.set(selector, checkbox.checked);
      }
    });
    
    // Record AG-Grid column visibility states for key columns
    if (window.globalGridApi) {
      const keyColumns = ['neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0', 'V1_v0', 'V2_v0', 'V4_v0', 'IT_v0'];
      keyColumns.forEach(colId => {
        const column = window.globalGridApi.getColumn(colId);
        if (column) {
          columnStates.set(colId, column.isVisible());
        }
      });
      
      // Record expanded column states
      if (window.columnExpansionState) {
        keyColumns.forEach(colId => {
          if (window.columnExpansionState.get(colId) === true) {
            expandedColumns.add(colId);
          }
        });
      }
    }
    
    return { collapsedNodes, checkboxStates, columnStates, expandedColumns };
  },
  
  // Restore to original state (complete reset)
  resetToOriginal() {
    // Reset all checkboxes to original state
    this.originalValues.forEach((originalValue, key) => {
      if (key.startsWith('checkbox_')) {
        const value = key.replace('checkbox_', '');
        const checkbox = document.querySelector(`input[type="checkbox"][value="${value}"]`);
        if (checkbox && checkbox.checked !== originalValue) {
          checkbox.checked = originalValue;
          
          // Trigger change event
          const changeEvent = new Event('change', { bubbles: true });
          checkbox.dispatchEvent(changeEvent);
        }
      }
    });
    
    // Reset tree node expansion states
    this.originalValues.forEach((originalExpanded, key) => {
      if (key.startsWith('node_')) {
        const value = key.replace('node_', '');
        const node = document.querySelector(`input[value="${value}"]`)?.closest('.benchmark-node');
        if (node) {
          const isCurrentlyExpanded = !node.classList.contains('collapsed');
          if (isCurrentlyExpanded !== originalExpanded) {
            const toggle = node.querySelector('.tree-toggle');
            if (toggle) toggle.click();
          }
        }
      }
    });
    
    // Reset AG-Grid column visibility
    if (window.globalGridApi) {
      const columnStateArray = [];
      this.originalValues.forEach((originalVisible, key) => {
        if (key.startsWith('column_')) {
          const colId = key.replace('column_', '');
          columnStateArray.push({ colId, hide: !originalVisible });
        }
      });
      
      if (columnStateArray.length > 0) {
        window.globalGridApi.applyColumnState({ state: columnStateArray });
      }
    }
    
    // Reset column expansion states
    if (window.columnExpansionState) {
      this.originalValues.forEach((originalExpanded, key) => {
        if (key.startsWith('expansion_')) {
          const colId = key.replace('expansion_', '');
          const currentExpanded = window.columnExpansionState.get(colId) === true;
          
          if (currentExpanded !== originalExpanded) {
            const headerCell = document.querySelector(`.ag-header-cell[col-id="${colId}"]`);
            if (headerCell) {
              const expandToggle = headerCell.querySelector('.expand-toggle');
              if (expandToggle) {
                expandToggle.click();
              }
            }
          }
        }
      });
    }
    
    // Close advanced filters if they were opened during tour
    const advancedFilters = document.getElementById('advanced-filters');
    if (advancedFilters && !advancedFilters.classList.contains('hidden')) {
      const toggleButton = document.querySelector('button[onclick="toggleAdvancedFilters()"]');
      if (toggleButton) toggleButton.click();
    }
    
    // Update grid after all changes
    setTimeout(() => {
      if (window.updateExclusions) window.updateExclusions();
      if (window.applyCombinedFilters) window.applyCombinedFilters();
    }, 200);
  },
  
  // Clear all tracked state
  clear() {
    this.states.clear();
    this.currentStep = 0;
    this.initialState = null;
    this.originalValues.clear();
  }
};

// Step handlers for complex interactions
window.tourConfigs.stepHandlers = {
  // Show advanced filters panel
  showAdvancedFilters: () => {
    const btn = document.getElementById('advancedFilterBtn');
    const panel = document.getElementById('advancedFiltersPanel');
    if (btn && panel && panel.classList.contains('hidden')) {
      btn.click();
    }
  },

  // Expand specific benchmark column
  expandBenchmark: (benchmarkId) => {
    if (window.globalGridApi) {
      const allCols = window.globalGridApi.getAllGridColumns();
      const targetCol = allCols.find(col => col.getColId() === benchmarkId);
      if (targetCol) {
        const colDef = targetCol.getColDef();
        const toggle = document.querySelector(`[data-benchmark="${benchmarkId}"] .expand-toggle`);
        if (toggle && colDef.context?.parentField) {
          toggle.click();
        }
      }
    }
  },

  // Set optimal layout for tour
  setTourLayout: () => {
    const container = document.querySelector('.leaderboard-container');
    const panel = document.getElementById('advancedFiltersPanel');
    
    // Ensure we're in horizontal mode for better tour experience
    if (container && container.classList.contains('sidebar-mode')) {
      const toggleBtn = document.getElementById('toggleLayoutBtn');
      if (toggleBtn) {
        toggleBtn.click();
      }
    }
    
    // Hide filters panel initially
    if (panel && !panel.classList.contains('hidden')) {
      const advancedBtn = document.getElementById('advancedFilterBtn');
      if (advancedBtn) {
        advancedBtn.click();
      }
    }
  },

  // Ensure key columns are visible
  showKeyColumns: () => {
    if (window.globalGridApi) {
      window.globalGridApi.applyColumnState({
        state: [
          { colId: 'model', hide: false },
          { colId: 'rank', hide: false },
          { colId: 'average_vision_v0', hide: false },
          { colId: 'neural_vision_v0', hide: false },
          { colId: 'behavior_vision_v0', hide: false },
          { colId: 'engineering_vision_v0', hide: false }
        ]
      });
    }
  }
};

// Export for global usage
window.expandBenchmarkHeaders = expandBenchmarkHeaders; 