// Range slider functionality for numeric filters

// Initialize all dual-handle range sliders
function initializeDualHandleSliders() {
  const sliderContainers = document.querySelectorAll('.slider-container');
  sliderContainers.forEach(container => {
    initializeDualHandleSlider(container);
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
      console.log(`🎚️ ${sliderType} triggering debounceFilterUpdate`);
      debounceFilterUpdate();
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

// Reset all slider UI to default positions (use correct max values from filterOptions)
function resetSliderUI() {
  const ranges = window.filterOptions || {};
  const sliderContainers = document.querySelectorAll('.slider-container');
  
  sliderContainers.forEach(container => {
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
  resetSliderUI,
  getRangeValues,
  setRangeValues,
  debounceFilterUpdate
};