// URL state management for leaderboard filters

// Parse URL parameters and apply filters
function parseURLFilters() {
  const urlParams = new URLSearchParams(window.location.search);
  
  // Parse multi-select filters
  const parseList = (param) => {
    const value = urlParams.get(param);
    return value ? value.split(',').map(v => v.trim()) : [];
  };
  
  window.activeFilters.architecture = parseList('architecture');
  window.activeFilters.model_family = parseList('model_family');
  window.activeFilters.training_dataset = parseList('training_dataset');
  window.activeFilters.task_specialization = parseList('task_specialization');
  window.activeFilters.benchmark_regions = parseList('benchmark_regions');
  window.activeFilters.benchmark_species = parseList('benchmark_species');
  window.activeFilters.benchmark_tasks = parseList('benchmark_tasks');
  
  // Parse boolean filters
  window.activeFilters.public_data_only = urlParams.get('public_data_only') === 'true';
  window.activeFilters.runnable_only = urlParams.get('runnable_only') === 'true';
  
  // Parse range filters
  const parseFloatParam = (param) => {
    const value = urlParams.get(param);
    return value ? parseFloat(value) : null;
  };
  
  window.activeFilters.min_param_count = parseFloatParam('min_param_count');
  window.activeFilters.max_param_count = parseFloatParam('max_param_count');
  window.activeFilters.min_model_size = parseFloatParam('min_model_size');
  window.activeFilters.max_model_size = parseFloatParam('max_model_size');
  window.activeFilters.min_score = parseFloatParam('min_score');
  window.activeFilters.max_score = parseFloatParam('max_score');
  window.activeFilters.min_stimuli_count = parseFloatParam('min_stimuli_count');
  window.activeFilters.max_stimuli_count = parseFloatParam('max_stimuli_count');
  window.activeFilters.min_wayback_timestamp = parseFloatParam('min_wayback_timestamp');
  window.activeFilters.max_wayback_timestamp = parseFloatParam('max_wayback_timestamp');
  
  // Apply filters to UI
  applyFiltersToUI();
  
  // Parse benchmark exclusions
  const excludedBenchmarks = urlParams.get('excluded_benchmarks');
  if (excludedBenchmarks) {
    window.filteredOutBenchmarks = new Set(decodeBenchmarkFilters(excludedBenchmarks));
  }
  
  // Update benchmark tree checkboxes
  updateBenchmarkTreeFromURL();
  
  // Apply all filters
  if (typeof window.applyCombinedFilters === 'function') {
    window.applyCombinedFilters();
  }
}

// Apply parsed filters to UI elements
function applyFiltersToUI() {
  // Update dropdown inputs
  updateDropdownInput('architectureFilter', window.activeFilters.architecture);
  updateDropdownInput('modelFamilyFilter', window.activeFilters.model_family);
  updateDropdownInput('trainingDatasetFilter', window.activeFilters.training_dataset);
  updateDropdownInput('taskSpecFilter', window.activeFilters.task_specialization);
  
  // Update checkboxes
  updateCheckboxes('.region-checkbox', window.activeFilters.benchmark_regions);
  updateCheckboxes('.species-checkbox', window.activeFilters.benchmark_species);
  updateCheckboxes('.task-checkbox', window.activeFilters.benchmark_tasks);
  
  // Update boolean checkboxes
  const publicDataCheckbox = document.getElementById('publicDataFilter');
  if (publicDataCheckbox) {
    publicDataCheckbox.checked = window.activeFilters.public_data_only;
  }
  
  // Update range inputs
  updateRangeInput('paramCountMin', window.activeFilters.min_param_count);
  updateRangeInput('paramCountMax', window.activeFilters.max_param_count);
  updateRangeInput('modelSizeMin', window.activeFilters.min_model_size);
  updateRangeInput('modelSizeMax', window.activeFilters.max_model_size);
  updateRangeInput('stimuliCountMin', window.activeFilters.min_stimuli_count);
  updateRangeInput('stimuliCountMax', window.activeFilters.max_stimuli_count);
  
  // Update range sliders
  if (typeof window.LeaderboardRangeFilters?.setRangeValues === 'function') {
    if (window.activeFilters.min_param_count !== null || window.activeFilters.max_param_count !== null) {
      const min = window.activeFilters.min_param_count || 0;
      const max = window.activeFilters.max_param_count || 100;
      window.LeaderboardRangeFilters.setRangeValues('paramCountMin', min, max);
    }
    
    if (window.activeFilters.min_model_size !== null || window.activeFilters.max_model_size !== null) {
      const min = window.activeFilters.min_model_size || 0;
      const max = window.activeFilters.max_model_size || 1000;
      window.LeaderboardRangeFilters.setRangeValues('modelSizeMin', min, max);
    }
    
    if (window.activeFilters.min_stimuli_count !== null || window.activeFilters.max_stimuli_count !== null) {
      const min = window.activeFilters.min_stimuli_count || 0;
      const max = window.activeFilters.max_stimuli_count || 1000;
      window.LeaderboardRangeFilters.setRangeValues('stimuliCountMin', min, max);
    }
  }

  // Update wayback timestamp slider if values are set
  if (window.activeFilters.min_wayback_timestamp !== null || window.activeFilters.max_wayback_timestamp !== null) {
    // Update date inputs
    const waybackDateMin = document.getElementById('waybackDateMin');
    const waybackDateMax = document.getElementById('waybackDateMax');
    
    if (waybackDateMin && window.activeFilters.min_wayback_timestamp) {
      const minDate = new Date(window.activeFilters.min_wayback_timestamp * 1000);
      waybackDateMin.value = minDate.toISOString().split('T')[0];
    }
    
    if (waybackDateMax && window.activeFilters.max_wayback_timestamp) {
      const maxDate = new Date(window.activeFilters.max_wayback_timestamp * 1000);
      waybackDateMax.value = maxDate.toISOString().split('T')[0];
    }
    
    // Update slider handles through the range filter system
    if (typeof window.LeaderboardRangeFilters?.setRangeValues === 'function') {
      const min = window.activeFilters.min_wayback_timestamp || 0;
      const max = window.activeFilters.max_wayback_timestamp || 2000000000;
      window.LeaderboardRangeFilters.setRangeValues('waybackDateMin', min, max);
    }
  }
}

// Update dropdown input with selected values
function updateDropdownInput(filterId, selectedValues) {
  const filter = document.getElementById(filterId);
  if (!filter || !selectedValues || selectedValues.length === 0) return;
  
  const input = filter.querySelector('.filter-input');
  if (input) {
    input.value = selectedValues.join(', ');
  }
}

// Update checkboxes with selected values
function updateCheckboxes(selector, selectedValues) {
  const checkboxes = document.querySelectorAll(selector);
  checkboxes.forEach(checkbox => {
    checkbox.checked = selectedValues.includes(checkbox.value);
  });
}

// Update range input with value
function updateRangeInput(inputId, value) {
  const input = document.getElementById(inputId);
  if (input && value !== null) {
    input.value = value;
  }
}

// Update benchmark tree checkboxes based on URL exclusions
function updateBenchmarkTreeFromURL() {
  const allCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
  
  allCheckboxes.forEach(checkbox => {
    if (window.filteredOutBenchmarks && window.filteredOutBenchmarks.has(checkbox.value)) {
      checkbox.checked = false;
    } else {
      checkbox.checked = true;
    }
  });
}

// Update URL with current filter state
function updateURLFromFilters() {
  const params = new URLSearchParams();
  
  // Add list parameters
  const addList = (key, urlParam) => {
    const param = urlParam || key;
    if (window.activeFilters[key]?.length > 0) {
      params.set(param, window.activeFilters[key].join(','));
    }
  };
  
  addList('architecture');
  addList('model_family');
  addList('training_dataset');
  addList('task_specialization');
  addList('benchmark_regions');
  addList('benchmark_species');
  addList('benchmark_tasks');
  
  // Add boolean parameters
  if (window.activeFilters.public_data_only) {
    params.set('public_data_only', 'true');
  }
  
  if (window.activeFilters.runnable_only) {
    params.set('runnable_only', 'true');
  }
  
  // Add range parameters
  const addRange = (key) => {
    if (window.activeFilters[key] !== null && window.activeFilters[key] !== undefined) {
      params.set(key, window.activeFilters[key].toString());
    }
  };
  
  addRange('min_param_count');
  addRange('max_param_count');
  addRange('min_model_size');
  addRange('max_model_size');
  addRange('min_score');
  addRange('max_score');
  addRange('min_stimuli_count');
  addRange('max_stimuli_count');
  addRange('min_wayback_timestamp');
  addRange('max_wayback_timestamp');
  
  // Add benchmark exclusions
  const excludedBenchmarks = encodeBenchmarkFilters();
  if (excludedBenchmarks) {
    params.set('excluded_benchmarks', excludedBenchmarks);
  }
  
  // Update URL without page reload
  const newURL = `${window.location.pathname}?${params.toString()}`;
  window.history.replaceState({}, '', newURL);
}

// Encode benchmark filters for URL
function encodeBenchmarkFilters() {
  if (!window.filteredOutBenchmarks || window.filteredOutBenchmarks.size === 0) {
    return null;
  }
  
  return Array.from(window.filteredOutBenchmarks).join(',');
}

// Decode benchmark filters from URL
function decodeBenchmarkFilters(encodedFilters) {
  if (!encodedFilters) return [];
  
  return encodedFilters.split(',').map(id => id.trim()).filter(id => id);
}

// Clear URL parameters
function clearURLParameters() {
  const newURL = window.location.pathname;
  window.history.replaceState({}, '', newURL);
}

// Get current URL parameters as object
function getCurrentURLParams() {
  const params = new URLSearchParams(window.location.search);
  const result = {};
  
  for (const [key, value] of params.entries()) {
    result[key] = value;
  }
  
  return result;
}

// Check if URL has any filter parameters
function hasURLFilters() {
  const params = new URLSearchParams(window.location.search);
  const filterParams = [
    'architecture', 'model_family', 'training_dataset', 'task_specialization',
    'benchmark_regions', 'benchmark_species', 'benchmark_tasks',
    'public_data_only', 'runnable_only', 'excluded_benchmarks',
    'min_param_count', 'max_param_count', 'min_model_size', 'max_model_size',
    'min_score', 'max_score', 'min_stimuli_count', 'max_stimuli_count'
  ];
  
  return filterParams.some(param => params.has(param));
}

// Export functions for use by other modules
window.LeaderboardURLState = {
  parseURLFilters,
  applyFiltersToUI,
  updateURLFromFilters,
  encodeBenchmarkFilters,
  decodeBenchmarkFilters,
  clearURLParameters,
  getCurrentURLParams,
  hasURLFilters
};