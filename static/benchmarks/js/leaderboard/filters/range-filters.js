// Range slider functionality for numeric filters

// ======================
// CONFIGURATION
// ======================
// Set to true to freeze the min handle (start timestamp) for wayback timestamp slider
// Set to false to allow both handles to be adjustable
const FREEZE_WAYBACK_MIN_HANDLE = true;

// Helper function to check if min handle should be frozen
function shouldFreezeMinHandle(sliderType) {
  return FREEZE_WAYBACK_MIN_HANDLE && sliderType === 'waybackTimestamp';
}

// Export for use in other modules
window.shouldFreezeMinHandle = shouldFreezeMinHandle;

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
    // For wayback timestamp, ensure minValue is always locked to minimum if frozen
    if (shouldFreezeMinHandle(sliderType)) {
      minValue = min;
    }
    
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
      // For wayback timestamp, min is locked to minimum if frozen, otherwise use minValue
      window.activeFilters.min_wayback_timestamp = shouldFreezeMinHandle(sliderType) ? min : minValue;
      window.activeFilters.max_wayback_timestamp = maxValue;
      console.log(`🎚️ ${sliderType} filter update:`, {
        minValue: min, // Always minimum (frozen)
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
    // Prevent min handle movement if frozen
    if (shouldFreezeMinHandle(sliderType) && isMin) {
      return;
    }

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
    // Skip adding listeners for disabled min handle if frozen
    if (shouldFreezeMinHandle(sliderType) && isMin) {
      return;
    }

    let isDragging = false;
    let tooltip = null;

    handle.addEventListener('mousedown', (e) => {
      isDragging = true;
      document.addEventListener('mousemove', mouseMoveHandler);
      document.addEventListener('mouseup', mouseUpHandler);
      e.preventDefault();
      
      // Create tooltip for wayback timestamp slider (only for max handle if min is frozen)
      if (sliderType === 'waybackTimestamp' && typeof createTooltip === 'function' && (!shouldFreezeMinHandle(sliderType) || !isMin)) {
        const currentValue = isMin ? minValue : maxValue;
        const date = new Date(currentValue * 1000);
        const dateStr = date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        tooltip = createTooltip(handle, dateStr, {
          type: 'info',
          position: 'top',
          duration: 999999, // Don't auto-hide while dragging
          offset: 25
        });
      }
    });

    function mouseMoveHandler(e) {
      if (isDragging) {
        handleMouseMove(e, handle, isMin);
        
        // Update tooltip for wayback timestamp slider (only for max handle if min is frozen)
        if (sliderType === 'waybackTimestamp' && tooltip && typeof createTooltip === 'function' && (!shouldFreezeMinHandle(sliderType) || !isMin)) {
          const currentValue = isMin ? minValue : maxValue;
          const date = new Date(currentValue * 1000);
          const dateStr = date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
          
          // Update tooltip content and position
          tooltip.remove();
          tooltip = createTooltip(handle, dateStr, {
            type: 'info',
            position: 'top',
            duration: 999999,
            offset: 25
          });
        }
      }
    }

    function mouseUpHandler() {
      isDragging = false;
      document.removeEventListener('mousemove', mouseMoveHandler);
      document.removeEventListener('mouseup', mouseUpHandler);
      
      // Remove tooltip when dragging ends
      if (tooltip) {
        tooltip.remove();
        tooltip = null;
      }
    }
  }

  addMouseListeners(minHandle, true);
  addMouseListeners(maxHandle, false);

  // Input field synchronization
  if (minInput) {
    // Skip event listener for wayback timestamp min input if frozen
    if (!shouldFreezeMinHandle(sliderType)) {
      minInput?.addEventListener('change', () => {
        if (sliderType === 'waybackTimestamp') {
          const ts = new Date(minInput.value).getTime() / 1000;
          if (!isNaN(ts)) {
            minValue = ts;
            minHandle.dataset.value = ts;
            updateSliderPosition();
            updateActiveFilters();
          }
        } else {
          const ts = parseFloat(minInput.value);
          if (!isNaN(ts)) {
            minValue = ts;
            minHandle.dataset.value = ts;
            updateSliderPosition();
            updateActiveFilters();
          }
        }
      });
    }
  }

  if (maxInput) {
    maxInput?.addEventListener('change', () => {
    const ts = new Date(maxInput.value).getTime() / 1000;
    if (!isNaN(ts)) {
      // For wayback timestamp, ensure value doesn't exceed today's date
      if (sliderType === 'waybackTimestamp') {
        const today = new Date();
        today.setHours(23, 59, 59, 999); // End of today
        const todayTs = Math.floor(today.getTime() / 1000);
        if (ts > todayTs) {
          // Clamp to today's date
          maxInput.value = today.toISOString().split('T')[0];
          maxValue = todayTs;
        } else {
          maxValue = ts;
        }
      } else {
        maxValue = ts;
      }
      maxHandle.dataset.value = maxValue;
      updateSliderPosition();
      updateActiveFilters();
    }
    });
  }

  // For minInput
  if (sliderType === 'waybackTimestamp') {
    // For wayback timestamp, lock min value to minimum if frozen
    if (shouldFreezeMinHandle(sliderType)) {
      minValue = min; // Always use the minimum timestamp
      minHandle.dataset.value = minValue;
      // Disable min input and handle for wayback timestamp
      if (minInput) {
        minInput.disabled = true;
        minInput.style.cursor = 'not-allowed';
        minInput.style.opacity = '0.6';
      }
      // Disable min handle dragging
      minHandle.style.cursor = 'not-allowed';
      minHandle.style.opacity = '0.6';
      minHandle.classList.add('handle-disabled');
    } else {
      // If not frozen, initialize normally
      const dateValue = new Date(minInput.value);
      minValue = isNaN(dateValue.getTime()) ? min : Math.floor(dateValue.getTime() / 1000);
      minHandle.dataset.value = minValue;
    }
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
    const isWaybackTimestamp = sliderGroup?.querySelector('#waybackDateMin');
    
    if (sliderGroup?.querySelector('#paramCountMin') && ranges.parameter_ranges?.max) {
      max = ranges.parameter_ranges.max;
      container.dataset.max = max;
    } else if (sliderGroup?.querySelector('#modelSizeMin') && ranges.size_ranges?.max) {
      max = ranges.size_ranges.max;
      container.dataset.max = max;
    } else if (sliderGroup?.querySelector('#stimuliCountMin') && ranges.stimuli_ranges?.max) {
      max = ranges.stimuli_ranges.max;
      container.dataset.max = max;
    } else if (isWaybackTimestamp && ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
      min = ranges.datetime_range.min_unix;
      max = ranges.datetime_range.max_unix;
      container.dataset.min = min;
      container.dataset.max = max;
      // Lock min value for wayback timestamp if frozen
      if (shouldFreezeMinHandle('waybackTimestamp')) {
        const minHandle = container.querySelector('.handle-min');
        const minInput = sliderGroup?.querySelector('.range-input-min');
        if (minHandle) {
          minHandle.dataset.value = min;
          minHandle.style.left = '0%';
          minHandle.style.cursor = 'not-allowed';
          minHandle.style.opacity = '0.6';
          minHandle.classList.add('handle-disabled');
        }
        if (minInput) {
          minInput.disabled = true;
          minInput.style.cursor = 'not-allowed';
          minInput.style.opacity = '0.6';
        }
      }
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

    if (isWaybackTimestamp) {
      // For wayback timestamp, convert Unix timestamps to ISO date strings
      const minDate = new Date(min * 1000);
      const maxDate = new Date(max * 1000);
      if (minInput) minInput.value = minDate.toISOString().split('T')[0];
      if (maxInput) {
        // Ensure max doesn't exceed today's date
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        const maxDateStr = maxDate.toISOString().split('T')[0];
        maxInput.value = maxDateStr > todayStr ? todayStr : maxDateStr;
        maxInput.max = todayStr;
      }
    } else {
      // Standard numeric inputs
      if (minInput) minInput.value = min;
      if (maxInput) maxInput.value = max;
    }
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
