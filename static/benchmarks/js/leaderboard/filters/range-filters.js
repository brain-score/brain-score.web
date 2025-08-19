// Range slider functionality for numeric filters

// Initialize all dual-handle range sliders
function initializeDualHandleSliders() {
  const dualSliderContainers = document.querySelectorAll('.range-filter.dual-handle .slider-container');
  dualSliderContainers.forEach(container => {
    initializeDualHandleSlider(container);
  });
  
  // Initialize single-handle sliders
  const singleSliderContainers = document.querySelectorAll('.range-filter.single-handle .slider-container');
  singleSliderContainers.forEach(container => {
    initializeSingleHandleSlider(container);
  });
}

// Initialize a single dual-handle range slider
function initializeDualHandleSlider(container) {
  const minHandle = container.querySelector('.handle-min');
  const maxHandle = container.querySelector('.handle-max');
  const range = container.querySelector('.slider-range');
  
  if (!minHandle || !maxHandle || !range) return;
  
  const min = parseFloat(container.dataset.min) || 0;
  const max = parseFloat(container.dataset.max) || 100;
  
  let minValue = parseFloat(minHandle.dataset.value) || min;
  let maxValue = parseFloat(maxHandle.dataset.value) || max;
  
  // Find associated input fields
  const sliderGroup = container.closest('.filter-group');
  const sliderType = sliderGroup?.querySelector('#paramCountMin') ? 'paramCount' : 
                     sliderGroup?.querySelector('#modelSizeMin') ? 'modelSize' : 
                     sliderGroup?.querySelector('#stimuliCountMin') ? 'stimuliCount' : 'unknown';
  
  const minInput = sliderGroup?.querySelector('.range-input-min');
  const maxInput = sliderGroup?.querySelector('.range-input-max');
  
  function updateSliderPosition() {
    const minPercent = ((minValue - min) / (max - min)) * 100;
    const maxPercent = ((maxValue - min) / (max - min)) * 100;
    
    minHandle.style.left = `${minPercent}%`;
    maxHandle.style.left = `${maxPercent}%`;
    
    range.style.left = `${minPercent}%`;
    range.style.width = `${maxPercent - minPercent}%`;
    
    // Update input fields
    if (minInput) minInput.value = Math.round(minValue);
    if (maxInput) maxInput.value = Math.round(maxValue);
  }
  
  function updateActiveFilters(skipDebounce = false) {
    const filterId = container.closest('.filter-group').id;
    
    if (filterId === 'paramCountMin' || filterId === 'paramCountMax' || 
        sliderGroup?.querySelector('#paramCountMin') || sliderGroup?.querySelector('#paramCountMax')) {
      const oldValue = window.activeFilters.max_param_count;
      window.activeFilters.max_param_count = maxValue < max ? maxValue : null;
      console.log(`🎚️ ${sliderType} filter update:`, {
        maxValue,
        max,
        isLessThan: maxValue < max,
        oldFilterValue: oldValue,
        newFilterValue: window.activeFilters.max_param_count,
        skipDebounce
      });
    } else if (filterId === 'modelSizeMin' || filterId === 'modelSizeMax' ||
               sliderGroup?.querySelector('#modelSizeMin') || sliderGroup?.querySelector('#modelSizeMax')) {
      const oldValue = window.activeFilters.max_model_size;
      window.activeFilters.max_model_size = maxValue < max ? maxValue : null;
      console.log(`🎚️ ${sliderType} filter update:`, {
        maxValue,
        max,
        isLessThan: maxValue < max,
        oldFilterValue: oldValue,
        newFilterValue: window.activeFilters.max_model_size,
        skipDebounce
      });
    }
    
    // Apply filters with debouncing - but not during initial setup
    if (!skipDebounce) {
      // Stimuli count affects benchmark filtering, others are model-only
      if (sliderType === 'stimuliCount') {
        console.log(`🎚️ ${sliderType} triggering debounceFilterUpdate (benchmark-level)`);
        // Update benchmark filters for stimuli count
        if (typeof window.LeaderboardBenchmarkFilters?.updateBenchmarkFilters === 'function') {
          window.LeaderboardBenchmarkFilters.updateBenchmarkFilters();
        }
        debounceFilterUpdate();
      } else {
        console.log(`🎚️ ${sliderType} triggering debounceModelFilterUpdate (model-level)`);
        // Model properties (param count, model size) should skip benchmark filtering
        debounceModelFilterUpdate();
      }
    }
  }
  
  function handleMouseMove(e, handle, isMin) {
    const rect = container.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const value = min + percent * (max - min);
    
    if (isMin) {
      minValue = Math.min(value, maxValue - 1);
    } else {
      maxValue = Math.max(value, minValue + 1);
    }
    
    updateSliderPosition();
    updateActiveFilters();
  }
  
  function addMouseListeners(handle, isMin) {
    let isDragging = false;
    
    handle.addEventListener('mousedown', (e) => {
      isDragging = true;
      document.addEventListener('mousemove', mouseMoveHandler);
      document.addEventListener('mouseup', mouseUpHandler);
      e.preventDefault();
    });
    
    function mouseMoveHandler(e) {
      if (isDragging) {
        handleMouseMove(e, handle, isMin);
      }
    }
    
    function mouseUpHandler() {
      isDragging = false;
      document.removeEventListener('mousemove', mouseMoveHandler);
      document.removeEventListener('mouseup', mouseUpHandler);
    }
  }
  
  addMouseListeners(minHandle, true);
  addMouseListeners(maxHandle, false);
  
  // Input field synchronization
  if (minInput) {
    minInput.addEventListener('input', () => {
      const value = parseFloat(minInput.value) || min;
      minValue = Math.max(min, Math.min(value, maxValue - 1));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
  
  if (maxInput) {
    maxInput.addEventListener('input', () => {
      const value = parseFloat(maxInput.value) || max;
      maxValue = Math.min(max, Math.max(value, minValue + 1));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
  
  // Initial position - don't trigger filters during setup
  updateSliderPosition();
  
  // Update active filters without debouncing during initial setup
  updateActiveFilters(true);
}

// Initialize a single-handle range slider (for completeness filter)
function initializeSingleHandleSlider(container) {
  const handle = container.querySelector('.handle-single');
  const range = container.querySelector('.slider-range-single');
  
  if (!handle || !range) return;
  
  const min = parseFloat(container.dataset.min) || 0;
  const max = parseFloat(container.dataset.max) || 100;
  
  let value = parseFloat(handle.dataset.value) || min;
  
  // Find associated input field
  const sliderGroup = container.closest('.filter-group');
  const input = sliderGroup?.querySelector('#completenessThreshold');
  
  function updateSliderPosition() {
    const percent = ((value - min) / (max - min)) * 100;
    
    handle.style.left = `${percent}%`;
    range.style.width = `${percent}%`;
    
    // Update input field
    if (input) input.value = Math.round(value);
  }
  
  function updateActiveFilters(skipDebounce = false) {
    const oldValue = window.activeFilters.min_completeness;
    window.activeFilters.min_completeness = value;
    
    console.log('🎚️ Completeness filter update:', {
      value,
      oldFilterValue: oldValue,
      newFilterValue: window.activeFilters.min_completeness,
      skipDebounce
    });
    
    // Apply filters with debouncing - but not during initial setup
    if (!skipDebounce) {
      console.log('🎚️ Completeness triggering debounceModelFilterUpdate');
      debounceModelFilterUpdate();
    }
  }
  
  function handleMouseMove(e) {
    const rect = container.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    value = min + percent * (max - min);
    
    updateSliderPosition();
    updateActiveFilters();
  }
  
  let isDragging = false;
  
  handle.addEventListener('mousedown', (e) => {
    isDragging = true;
    document.addEventListener('mousemove', mouseMoveHandler);
    document.addEventListener('mouseup', mouseUpHandler);
    e.preventDefault();
  });
  
  function mouseMoveHandler(e) {
    if (isDragging) {
      handleMouseMove(e);
    }
  }
  
  function mouseUpHandler() {
    isDragging = false;
    document.removeEventListener('mousemove', mouseMoveHandler);
    document.removeEventListener('mouseup', mouseUpHandler);
  }
  
  // Input field synchronization
  if (input) {
    input.addEventListener('input', () => {
      const inputValue = parseFloat(input.value) || min;
      value = Math.max(min, Math.min(inputValue, max));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
  
  // Initial position - don't trigger filters during setup
  updateSliderPosition();
  
  // Update active filters without debouncing during initial setup
  updateActiveFilters(true);
}

// Debounced filter update
let filterUpdateTimeout;
function debounceFilterUpdate() {
  clearTimeout(filterUpdateTimeout);
  filterUpdateTimeout = setTimeout(() => {
    if (typeof window.applyCombinedFilters === 'function') {
      window.applyCombinedFilters();
    }
  }, window.LeaderboardConstants.SLIDER_UPDATE_DELAY);
}

// Debounced model-only filter update (for completeness and other model properties)
let modelFilterUpdateTimeout;
function debounceModelFilterUpdate() {
  clearTimeout(modelFilterUpdateTimeout);
  modelFilterUpdateTimeout = setTimeout(() => {
    if (typeof window.applyCombinedFilters === 'function') {
      // Skip benchmark filters since this is model-only filtering
      window.applyCombinedFilters(false, false, true);
    }
  }, window.LeaderboardConstants.SLIDER_UPDATE_DELAY);
}

// Reset all slider UI to default positions (use correct max values from filterOptions)
function resetSliderUI() {
  const ranges = window.filterOptions || {};
  
  // Reset dual-handle sliders
  const dualSliderContainers = document.querySelectorAll('.range-filter.dual-handle .slider-container');
  dualSliderContainers.forEach(container => {
    const minHandle = container.querySelector('.handle-min');
    const maxHandle = container.querySelector('.handle-max');
    const range = container.querySelector('.slider-range');
    
    if (!minHandle || !maxHandle || !range) return;
    
    const min = parseFloat(container.dataset.min) || 0;
    let max = parseFloat(container.dataset.max) || 100;
    
    // Use correct max values from filterOptions
    const sliderGroup = container.closest('.filter-group');
    if (sliderGroup?.querySelector('#paramCountMin') && ranges.parameter_ranges?.max) {
      max = ranges.parameter_ranges.max;
      container.dataset.max = max;
    } else if (sliderGroup?.querySelector('#modelSizeMin') && ranges.size_ranges?.max) {
      max = ranges.size_ranges.max;
      container.dataset.max = max;
    } else if (sliderGroup?.querySelector('#stimuliCountMin') && ranges.stimuli_ranges?.max) {
      max = ranges.stimuli_ranges.max;
      container.dataset.max = max;
    }
    
    // Reset to full range
    minHandle.style.left = '0%';
    maxHandle.style.left = '100%';
    range.style.left = '0%';
    range.style.width = '100%';
    
    // Update data attributes
    minHandle.dataset.value = min;
    maxHandle.dataset.value = max;
    
    // Update input fields
    const minInput = sliderGroup?.querySelector('.range-input-min');
    const maxInput = sliderGroup?.querySelector('.range-input-max');
    
    if (minInput) minInput.value = min;
    if (maxInput) maxInput.value = max;
  });
  
  // Reset single-handle sliders
  const singleSliderContainers = document.querySelectorAll('.range-filter.single-handle .slider-container');
  singleSliderContainers.forEach(container => {
    const handle = container.querySelector('.handle-single');
    const range = container.querySelector('.slider-range-single');
    
    if (!handle || !range) return;
    
    const min = parseFloat(container.dataset.min) || 0;
    
    // Reset to minimum value (0% completeness)
    handle.style.left = '0%';
    range.style.width = '0%';
    
    // Update data attribute
    handle.dataset.value = min;
    
    // Update input field
    const sliderGroup = container.closest('.filter-group');
    const input = sliderGroup?.querySelector('.range-input-single');
    if (input) input.value = min;
  });
}

// Get current range values for a specific filter
function getRangeValues(filterId) {
  const container = document.querySelector(`#${filterId}`)?.closest('.filter-group')?.querySelector('.slider-container');
  if (!container) return null;
  
  const minHandle = container.querySelector('.handle-min');
  const maxHandle = container.querySelector('.handle-max');
  
  if (!minHandle || !maxHandle) return null;
  
  return {
    min: parseFloat(minHandle.dataset.value) || 0,
    max: parseFloat(maxHandle.dataset.value) || 100
  };
}

// Set range values for a specific filter
function setRangeValues(filterId, minVal, maxVal) {
  const container = document.querySelector(`#${filterId}`)?.closest('.filter-group')?.querySelector('.slider-container');
  if (!container) return;
  
  const minHandle = container.querySelector('.handle-min');
  const maxHandle = container.querySelector('.handle-max');
  const range = container.querySelector('.slider-range');
  
  if (!minHandle || !maxHandle || !range) return;
  
  const min = parseFloat(container.dataset.min) || 0;
  const max = parseFloat(container.dataset.max) || 100;
  
  const minValue = Math.max(min, Math.min(minVal, max));
  const maxValue = Math.max(min, Math.min(maxVal, max));
  
  minHandle.dataset.value = minValue;
  maxHandle.dataset.value = maxValue;
  
  const minPercent = ((minValue - min) / (max - min)) * 100;
  const maxPercent = ((maxValue - min) / (max - min)) * 100;
  
  minHandle.style.left = `${minPercent}%`;
  maxHandle.style.left = `${maxPercent}%`;
  range.style.left = `${minPercent}%`;
  range.style.width = `${maxPercent - minPercent}%`;
  
  // Update input fields
  const sliderGroup = container.closest('.filter-group');
  const minInput = sliderGroup?.querySelector('.range-input-min');
  const maxInput = sliderGroup?.querySelector('.range-input-max');
  
  if (minInput) minInput.value = Math.round(minValue);
  if (maxInput) maxInput.value = Math.round(maxValue);
}

// Export functions for use by other modules
window.LeaderboardRangeFilters = {
  initializeDualHandleSliders,
  initializeDualHandleSlider,
  initializeSingleHandleSlider,
  resetSliderUI,
  getRangeValues,
  setRangeValues,
  debounceFilterUpdate,
  debounceModelFilterUpdate
};