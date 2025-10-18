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
                     sliderGroup?.querySelector('#stimuliCountMin') ? 'stimuliCount' :
                     sliderGroup?.querySelector('#waybackDateMin') ? 'waybackTimestamp' : 'unknown';

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

    if (sliderType === 'waybackTimestamp') {
      // Convert Unix timestamps to date strings for date inputs
      if (minInput) {
        const minDate = new Date(minValue * 1000);
        minInput.value = minDate.toISOString().split('T')[0];
      }
      if (maxInput) {
        const maxDate = new Date(maxValue * 1000);
        maxInput.value = maxDate.toISOString().split('T')[0];
      }
    } else {
      // Standard numeric inputs
      if (minInput) minInput.value = Math.round(minValue);
      if (maxInput) maxInput.value = Math.round(maxValue);
    }
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
    } else if (filterId === 'waybackTimestampFilter' || sliderType === 'waybackTimestamp') {
      window.activeFilters.min_wayback_timestamp = minValue;
      window.activeFilters.max_wayback_timestamp = maxValue;
      console.log(`🎚️ ${sliderType} filter update:`, {
        minValue,
        maxValue,
        min: min,
        max: max,
        isAtFullRange: (minValue <= min && maxValue >= max),
        skipDebounce
      });
    }

    // Apply filters with debouncing - but not during initial setup
    if (!skipDebounce) {
      console.log(`🎚️ ${sliderType} triggering debounceFilterUpdate`);

      // If this is the stimuli count slider, also update benchmark filters
      if (sliderType === 'stimuliCount') {
        if (typeof window.LeaderboardBenchmarkFilters?.updateBenchmarkFilters === 'function') {
          window.LeaderboardBenchmarkFilters.updateBenchmarkFilters();
        }
      }

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
    minInput?.addEventListener('change', () => {
      const ts = new Date(minInput.value).getTime() / 1000;
      if (!isNaN(ts)) {
        minValue = ts;
        minHandle.dataset.value = ts;
        updateSliderPosition();
        updateActiveFilters();
      }
    });
  }

  if (maxInput) {
    maxInput?.addEventListener('change', () => {
    const ts = new Date(maxInput.value).getTime() / 1000;
    if (!isNaN(ts)) {
      maxValue = ts;
      maxHandle.dataset.value = ts;
      updateSliderPosition();
      updateActiveFilters();
    }
    });
  }

  // For minInput
  if (sliderType === 'waybackTimestamp') {
    // Convert date string to Unix timestamp
    const dateValue = new Date(minInput.value);
    minValue = isNaN(minDateValue.getTime()) ? min : Math.floor(minDateValue.getTime() / 1000);
    minHandle.dataset.value = minValue;
  } else {
    minValue = parseFloat(minInput.value) || min;
    minHandle.dataset.value = minValue;
  }

  // For maxInput
  if (sliderType === 'waybackTimestamp') {
    // Convert date string to Unix timestamp
    const dateValue = new Date(maxInput.value);
    maxValue = isNaN(dateValue.getTime()) ? max : Math.floor(dateValue.getTime() / 1000);
    maxHandle.dataset.value = maxValue;
  } else {
    maxValue = parseFloat(maxInput.value) || max;
    maxHandle.dataset.value = maxValue;
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
