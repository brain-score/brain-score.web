// UI handlers for advanced filters panel and other UI interactions

// Setup all UI handlers
function setupUIHandlers(panel, container, advancedFilterBtn, layoutToggleBtn) {
  console.log('🎛️ Setting up UI handlers...');
  
  // Advanced filters panel toggle
  if (advancedFilterBtn && panel) {
    advancedFilterBtn.addEventListener('click', function() {
      console.log('Advanced filters button clicked');
      const textWrapper = advancedFilterBtn.querySelector('.text-wrapper');
      if (panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
        if (textWrapper) {
          textWrapper.textContent = 'Hide Filters';
        } else {
          advancedFilterBtn.textContent = 'Hide Filters';
        }
      } else {
        panel.classList.add('hidden');
        if (textWrapper) {
          textWrapper.textContent = 'Advanced Filters';
        } else {
          advancedFilterBtn.textContent = 'Advanced Filters';
        }
      }
    });
    console.log('✅ Advanced filters button handler set up');
  } else {
    console.warn('⚠️ Advanced filters button or panel not found');
  }
  
  // Layout toggle button
  if (layoutToggleBtn && panel && container) {
    layoutToggleBtn.addEventListener('click', function() {
      const toggleText = layoutToggleBtn.querySelector('.toggle-text');
      if (container.classList.contains('sidebar-mode')) {
        container.classList.remove('sidebar-mode');
        if (toggleText) toggleText.textContent = 'Sidebar Mode';
      } else {
        container.classList.add('sidebar-mode');
        if (toggleText) toggleText.textContent = 'Normal Mode';
      }
    });
    console.log('✅ Layout toggle button handler set up');
  }
  
  // Reset all filters button
  const resetAllFiltersBtn = document.getElementById('resetAllFiltersBtn');
  if (resetAllFiltersBtn) {
    resetAllFiltersBtn.addEventListener('click', function() {
      console.log('Reset all filters clicked');
      if (typeof window.resetAllFilters === 'function') {
        window.resetAllFilters();
      }
    });
    console.log('✅ Reset all filters button handler set up');
  }
  
  // Reset benchmarks link
  const resetBenchmarksLink = document.getElementById('resetBenchmarksLink');
  if (resetBenchmarksLink) {
    resetBenchmarksLink.addEventListener('click', function(e) {
      e.preventDefault();
      console.log('Reset benchmarks link clicked');
      
      // Check all benchmark checkboxes
      const checkboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
      checkboxes.forEach(cb => {
        cb.checked = true;
      });
      
      // Clear filtered benchmarks
      if (window.filteredOutBenchmarks) {
        window.filteredOutBenchmarks.clear();
      }
      
      // Apply filters (skip auto-sort since this is a reset operation, but allow column visibility updates)
      if (typeof window.applyCombinedFilters === 'function') {
        window.applyCombinedFilters(false, true);
      }
    });
    console.log('✅ Reset benchmarks link handler set up');
  }
  
  console.log('✅ All UI handlers set up successfully');
}

// Initialize filters from URL parameters or set defaults
function initializeFilters() {
  console.log('🔧 Initializing filters...');
  
  // Try to parse URL filters first
  if (typeof window.LeaderboardURLState?.parseURLFilters === 'function') {
    try {
      window.LeaderboardURLState.parseURLFilters();
      console.log('✅ URL filters parsed successfully');
    } catch (e) {
      console.warn('⚠️ Error parsing URL filters:', e);
    }
  }
  
  // If no URL filters, ensure filters are in default state
  if (!window.activeFilters) {
    console.log('📝 Setting default filter state...');
    window.activeFilters = {
      architecture: [],
      model_family: [],
      training_dataset: [],
      task_specialization: [],
      min_param_count: null,
      max_param_count: null,
      min_model_size: null,
      max_model_size: null,
      min_score: null,
      max_score: null,
      runnable_only: false,
      benchmark_regions: [],
      benchmark_species: [],
      benchmark_tasks: [],
      public_data_only: false
    };
  }
  
  // Initialize filtered benchmarks set if not exists
  if (!window.filteredOutBenchmarks) {
    window.filteredOutBenchmarks = new Set();
  }
  
  // Apply initial filters (skip column toggle during initialization)
  if (typeof window.applyCombinedFilters === 'function') {
    setTimeout(() => {
      window.applyCombinedFilters(true);
    }, 100);
  }
  
  console.log('✅ Filters initialized successfully');
}

// Export functions for use by other modules
window.LeaderboardUIHandlers = {
  setupUIHandlers,
  initializeFilters
};

// Make functions globally available for compatibility
window.setupUIHandlers = setupUIHandlers;
window.initializeFilters = initializeFilters;

// Log successful module load
console.log('📦 LeaderboardUIHandlers module loaded successfully');