// Core state management for leaderboard
// Manages global state variables and initialization

// Global grid API references
window.globalGridApi = null;
window.globalColumnApi = null;

// Global filter state for model properties
window.activeFilters = {
  architecture: [],
  model_family: [],
  training_dataset: [],
  task_specialization: [],
  max_param_count: null,
  max_model_size: null,
  runnable_only: false,
  benchmark_regions: [],
  benchmark_species: [],
  benchmark_tasks: [],
  public_data_only: false,
  min_completeness: 0  // Minimum percentage of benchmark scores required (0-100)
};

// Global state for tracking column expansion
window.columnExpansionState = new Map();

// Track filtered out benchmarks - start with empty set (all benchmarks included)
window.filteredOutBenchmarks = new Set();

// Global search state
window.currentSearchQuery = null;

// Global filtered data state for model property filters
window.currentFilteredData = null;

// Initialize state from window data
function initializeGlobalState() {
  // These are set by the HTML template
  window.originalRowData = window.originalRowData || [];
  window.filterOptions = window.filterOptions || {};
  window.benchmarkTree = window.benchmarkTree || [];
  window.benchmarkMetadata = window.benchmarkMetadata || [];
  window.benchmarkIds = window.benchmarkIds || {};
  window.benchmarkStimuliMetaMap = window.benchmarkStimuliMetaMap || {};
  window.benchmarkDataMetaMap = window.benchmarkDataMetaMap || {};
  window.benchmarkMetricMetaMap = window.benchmarkMetricMetaMap || {};
  window.modelMetadataMap = window.modelMetadataMap || {};
  window.benchmarkMetadataMap = window.benchmarkMetadataMap || {};
}

// Reset global state
function resetGlobalState() {
  window.activeFilters = {
    architecture: [],
    model_family: [],
    training_dataset: [],
    task_specialization: [],
    max_param_count: null,
    max_model_size: null,
    runnable_only: false,
    benchmark_regions: [],
    benchmark_species: [],
    benchmark_tasks: [],
    public_data_only: false,
    min_completeness: 0
  };
  
  window.columnExpansionState.clear();
  window.currentSearchQuery = null;
  window.currentFilteredData = null;
  window.filteredOutBenchmarks.clear();
}

// Export functions for use by other modules
window.LeaderboardState = {
  initializeGlobalState,
  resetGlobalState
};
