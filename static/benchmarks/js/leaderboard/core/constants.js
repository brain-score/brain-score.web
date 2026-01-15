// Constants and configuration for leaderboard

// Cell styling constants
const CELL_ALPHA = 0.85;
const DEFAULT_CELL_BG = '#e0e1e2';

// Runnable status colors
const RUNNABLE_STATUS = {
  FUNCTIONAL: 'runnable-green',
  ISSUES: 'runnable-red',
  UNKNOWN: 'runnable-grey'
};

// Sort values for runnable status
const RUNNABLE_SORT_VALUES = {
  FUNCTIONAL: 2,
  ISSUES: 1,
  UNKNOWN: 0
};

// Tooltip messages for runnable status
const RUNNABLE_TOOLTIPS = {
  FUNCTIONAL: 'Model code is functional and runnable',
  ISSUES: 'Model code has known issues or is non-functional',
  UNKNOWN: 'Model code status unknown'
};

// Column width constants
const COLUMN_WIDTHS = {
  RUNNABLE_STATUS: 80,
  MODEL_COLUMN: 200,
  SCORE_COLUMN: 100
};

// Navigation constants
const NAVIGATION_CLICK_AREA = 0.8; // 80% of header for navigation
const SORT_CLICK_AREA = 0.2; // 20% of header for sorting

// Filter constants
const FILTER_DEBOUNCE_DELAY = 300;
const SLIDER_UPDATE_DELAY = 100;

// Feature flags
const ENABLE_WAYBACK_SLIDER = false;  // Set to true to restore wayback machine functionality

// URL parameter names
const URL_PARAMS = {
  ARCHITECTURE: 'architecture',
  MODEL_FAMILY: 'model_family',
  TRAINING_DATASET: 'training_dataset',
  TASK_SPECIALIZATION: 'task_specialization',
  MAX_PARAM_COUNT: 'max_param_count',
  MAX_MODEL_SIZE: 'max_model_size',
  RUNNABLE_ONLY: 'runnable_only',
  BENCHMARK_REGIONS: 'benchmark_regions',
  BENCHMARK_SPECIES: 'benchmark_species',
  BENCHMARK_TASKS: 'benchmark_tasks',
  PUBLIC_DATA_ONLY: 'public_data_only',
  EXCLUDED_BENCHMARKS: 'excluded_benchmarks'
};

// Export constants
window.LeaderboardConstants = {
  CELL_ALPHA,
  DEFAULT_CELL_BG,
  RUNNABLE_STATUS,
  RUNNABLE_SORT_VALUES,
  RUNNABLE_TOOLTIPS,
  COLUMN_WIDTHS,
  NAVIGATION_CLICK_AREA,
  SORT_CLICK_AREA,
  FILTER_DEBOUNCE_DELAY,
  SLIDER_UPDATE_DELAY,
  URL_PARAMS,
  ENABLE_WAYBACK_SLIDER
};
