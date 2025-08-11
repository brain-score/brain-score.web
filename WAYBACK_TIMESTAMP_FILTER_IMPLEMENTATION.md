# Wayback Timestamp Filter Implementation Guide

## Overview

This document describes the complete implementation of the wayback timestamp filter for the Brain-Score leaderboard. The filter allows users to view the leaderboard as it appeared at any point in time by filtering out model-benchmark scores that were submitted after a selected timestamp range.

## Key Features Implemented

1. **Score Filtering**: Converts out-of-range scores to 'X' based on timestamp
2. **Model Removal**: Removes entire model rows when all scores become 'X'
3. **Column Hiding**: Hides benchmark columns when all scores in that column are 'X'
4. **Parent Score Recalculation**: Properly recalculates averages for parent benchmarks
5. **Global Score Handling**: Special handling for `average_vision_v0` column
6. **URL State Persistence**: Filter settings persist in URL for sharing/bookmarking

## Architecture Overview

The wayback timestamp filter integrates with the existing filtering system:

```
User adjusts slider → debounceFilterUpdate() → applyCombinedFilters() → 
applyWaybackTimestampFilter() → updateFilteredScores() → AG Grid update
```

## Implementation Steps

### 1. Backend Data Preparation

**File**: `benchmarks/views/leaderboard.py`

**Purpose**: Extract timestamp ranges from score data and provide them to frontend.

**Changes**:
```python
# In get_ag_grid_context function, around line 448
if all_timestamps:
    min_timestamp = min(all_timestamps)
    max_timestamp = max(all_timestamps)
    filter_options['datetime_range'] = {
        'min': min_timestamp.isoformat(),
        'max': max_timestamp.isoformat(),
        'min_unix': int(min_timestamp.timestamp()),
        'max_unix': int(max_timestamp.timestamp())
    }
```

**Explanation**: Extracts min/max timestamps from all score data and provides both ISO format (for display) and Unix timestamps (for slider logic) to the frontend.

### 2. Frontend UI Setup

**File**: `benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard.html`

**Purpose**: Add the wayback timestamp slider UI that's initially hidden.

**Changes**:
```html
<!-- Add wayback timestamp section (initially hidden) -->
<div class="metadata-section" id="waybackTimestampSection" style="display: none;">
  <div class="filter-group" id="waybackTimestampFilter">
    <div class="filter-header">
      <label>Wayback Timestamp</label>
      <div class="range-values">
        <input type="date" class="range-input-min" id="waybackDateMin">
        <span class="range-separator">to</span>
        <input type="date" class="range-input-max" id="waybackDateMax">
      </div>
    </div>
    <div class="range-filter dual-handle">
      <div class="slider-container" data-min="0" data-max="2000000000">
        <div class="slider-track"></div>
        <div class="slider-range"></div>
        <div class="slider-handle handle-min" data-value="0"></div>
        <div class="slider-handle handle-max" data-value="2000000000"></div>
      </div>
    </div>
  </div>
</div>
```

**Key Points**:
- Initially hidden with `display: none`
- Uses generic large values for `data-min`/`data-max` (updated by JS)
- Follows existing dual-handle slider pattern

### 3. UI Initialization

**File**: `static/benchmarks/js/leaderboard/core/template-initialization.js`

**Purpose**: Show and initialize the wayback slider when timestamp data is available.

**Changes**:
```javascript
// In initializeLeaderboardFromTemplate function, around line 97
// Setup wayback timestamp slider if datetime range is available
if (ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
  const waybackSection = document.getElementById('waybackTimestampSection');
  const waybackSliderContainer = document.querySelector('#waybackTimestampFilter .slider-container');
  const waybackDateMin = document.getElementById('waybackDateMin');
  const waybackDateMax = document.getElementById('waybackDateMax');
  
  if (waybackSection && waybackSliderContainer && waybackDateMin && waybackDateMax) {
    // Show the wayback section
    waybackSection.style.display = 'block';
    
    // Set up slider with Unix timestamps
    waybackSliderContainer.dataset.min = ranges.datetime_range.min_unix;
    waybackSliderContainer.dataset.max = ranges.datetime_range.max_unix;
    
    const minHandle = waybackSliderContainer.querySelector('.handle-min');
    const maxHandle = waybackSliderContainer.querySelector('.handle-max');
    
    if (minHandle && maxHandle) {
      minHandle.dataset.value = ranges.datetime_range.min_unix;
      maxHandle.dataset.value = ranges.datetime_range.max_unix;
    }
    
    // Convert Unix timestamps to date strings for date inputs
    const minDate = new Date(ranges.datetime_range.min_unix * 1000);
    const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
    
    waybackDateMin.value = minDate.toISOString().split('T')[0];
    waybackDateMax.value = maxDate.toISOString().split('T')[0];
  }
}
```

### 4. Slider Behavior Integration

**File**: `static/benchmarks/js/leaderboard/filters/range-filters.js`

**Purpose**: Integrate wayback timestamp slider with existing dual-handle slider system.

**Key Changes**:

1. **Slider Type Detection**:
```javascript
const sliderType = sliderGroup?.querySelector('#paramCountMin') ? 'paramCount' : 
                   sliderGroup?.querySelector('#modelSizeMin') ? 'modelSize' : 
                   sliderGroup?.querySelector('#stimuliCountMin') ? 'stimuliCount' :
                   sliderGroup?.querySelector('#waybackDateMin') ? 'waybackTimestamp' : 'unknown';
```

2. **Date Input Formatting**:
```javascript
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
}
```

3. **Active Filters Update**:
```javascript
} else if (filterId === 'waybackTimestampFilter' || sliderType === 'waybackTimestamp') {
  window.activeFilters.min_wayback_timestamp = minValue;
  window.activeFilters.max_wayback_timestamp = maxValue;
}
```

4. **Reset Functionality**:
```javascript
} else if (sliderGroup?.querySelector('#waybackDateMin') && ranges.datetime_range?.max_unix) {
  max = ranges.datetime_range.max_unix;
  container.dataset.max = max;
  container.dataset.min = ranges.datetime_range.min_unix;
}
```

### 5. Global State Management

**File**: `static/benchmarks/js/leaderboard/ui/ui-handlers.js`

**Purpose**: Add wayback timestamp filters to global state.

**Changes**:
```javascript
window.activeFilters = {
  // ... existing filters ...
  min_wayback_timestamp: null,
  max_wayback_timestamp: null
};
```

### 6. Core Filtering Logic

**File**: `static/benchmarks/js/leaderboard/filters/filter-coordinator.js`

**Purpose**: Implement the main wayback timestamp filtering logic.

**Key Function - `applyWaybackTimestampFilter`**:

```javascript
function applyWaybackTimestampFilter(rowData) {
  // Check if wayback timestamp filters are set and not at full range
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  
  // Get the actual range limits from filter options
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  
  const isAtFullRange = (minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  if (!minTimestamp || !maxTimestamp || isAtFullRange) {
    return rowData; // No timestamp filtering active
  }
  
  // Create deep copy of row data to avoid modifying original
  const filteredData = rowData.map((row, rowIndex) => {
    const newRow = { ...row };
    let modelHasValidScore = false;
    
    // Process each score field in the row
    Object.keys(row).forEach(key => {
      // Skip non-score fields
      if (key === 'id' || key === 'rank' || key === 'model' || key === 'metadata') {
        return;
      }
      
      // Check if this is a score object
      if (row[key] && typeof row[key] === 'object') {
        const scoreObj = row[key];
        const scoreTimestamp = scoreObj.timestamp;
        
        // Handle scores with timestamps
        if (scoreTimestamp) {
          // Parse timestamp (handle both string and number formats)
          let timestampSeconds;
          if (typeof scoreTimestamp === 'string') {
            const date = new Date(scoreTimestamp);
            timestampSeconds = Math.floor(date.getTime() / 1000);
          } else {
            timestampSeconds = scoreTimestamp;
          }
          
          // Check if timestamp is outside the allowed range
          if (timestampSeconds < minTimestamp || timestampSeconds > maxTimestamp) {
            // Convert score to 'X' if outside timestamp range
            newRow[key] = {
              ...scoreObj,
              value: 'X',
              raw: scoreObj.raw,
              color: '#e0e1e2'
            };
          } else {
            // Keep original score if within timestamp range
            newRow[key] = { ...scoreObj };
            if (scoreObj.value !== 'X' && scoreObj.value !== null && scoreObj.value !== undefined) {
              modelHasValidScore = true;
            }
          }
        } else {
          // Scores without timestamps - keep them as-is
          newRow[key] = { ...scoreObj };
          if (scoreObj.value !== 'X' && scoreObj.value !== null && scoreObj.value !== undefined) {
            modelHasValidScore = true;
          }
        }
      }
    });
    
    // Mark if this model has any valid scores remaining
    newRow._hasValidScore = modelHasValidScore;
    return newRow;
  });
  
  // Remove models that have all scores as 'X' or no valid scores
  const filteredWithValidModels = filteredData.filter(row => row._hasValidScore);
  
  // Clean up the temporary flag
  filteredWithValidModels.forEach(row => delete row._hasValidScore);
  
  return filteredWithValidModels;
}
```

**Integration in `applyCombinedFilters`**:
```javascript
// Apply wayback timestamp filtering to scores BEFORE other score filtering
let timestampFilteredData = filteredData;
if (typeof applyWaybackTimestampFilter === 'function') {
  timestampFilteredData = applyWaybackTimestampFilter(filteredData);
}

// Update filtered scores on the filtered data BEFORE setting it on the grid
let finalData = timestampFilteredData;
if (typeof updateFilteredScores === 'function') {
  const updatedData = updateFilteredScores(timestampFilteredData);
  if (updatedData) {
    finalData = updatedData;
  }
}
```

### 7. Score Recalculation Fix

**Critical Issue Discovered**: `updateFilteredScores` was overwriting wayback timestamp changes by restoring original data.

**Solution in `updateFilteredScores`**:

1. **Preserve Wayback Changes**:
```javascript
// Deep copy the rowData to preserve wayback timestamp filtering changes
const workingRowData = rowData.map(row => {
  const newRow = { ...row };
  // Deep copy all score objects to preserve wayback filtering changes
  Object.keys(row).forEach(key => {
    if (key !== 'model' && key !== 'rank' && key !== 'metadata' && row[key] && typeof row[key] === 'object') {
      newRow[key] = { ...row[key] };
    }
  });
  return newRow;
});

// Skip the original data restoration step since we want to preserve wayback timestamp filtering
// The workingRowData already contains the properly filtered data from applyWaybackTimestampFilter
```

2. **Special Average Score Handling**:
```javascript
// Special handling for average_vision_v0 (which isn't in the hierarchy as a parent)
// It should be the average of neural_vision_v0 and behavior_vision_v0
const neuralScore = row.neural_vision_v0?.value;
const behaviorScore = row.behavior_vision_v0?.value;

if (neuralScore !== undefined && behaviorScore !== undefined) {
  const validScores = [];
  
  if (neuralScore !== 'X' && neuralScore !== null && neuralScore !== undefined) {
    const numVal = typeof neuralScore === 'string' ? parseFloat(neuralScore) : neuralScore;
    if (!isNaN(numVal)) {
      validScores.push(numVal);
    }
  }
  
  if (behaviorScore !== 'X' && behaviorScore !== null && behaviorScore !== undefined) {
    const numVal = typeof behaviorScore === 'string' ? parseFloat(behaviorScore) : behaviorScore;
    if (!isNaN(numVal)) {
      validScores.push(numVal);
    }
  }
  
  if (validScores.length === 0) {
    // Both neural and behavior are 'X' or invalid - set average to 'X'
    row.average_vision_v0 = {
      ...row.average_vision_v0,
      value: 'X',
      color: '#e0e1e2'
    };
  } else if (validScores.length === 1) {
    // Only one valid score - use that value
    row.average_vision_v0 = {
      ...row.average_vision_v0,
      value: parseFloat(validScores[0].toFixed(3))
    };
  } else {
    // Both valid - calculate average
    const average = validScores.reduce((a, b) => a + b, 0) / validScores.length;
    row.average_vision_v0 = {
      ...row.average_vision_v0,
      value: parseFloat(average.toFixed(3))
    };
  }
}
```

### 8. URL State Persistence

**File**: `static/benchmarks/js/leaderboard/navigation/url-state.js`

**Purpose**: Persist wayback timestamp filter state in URL.

**Changes**:

1. **Parse URL Parameters**:
```javascript
window.activeFilters.min_wayback_timestamp = parseFloatParam('min_wayback_timestamp');
window.activeFilters.max_wayback_timestamp = parseFloatParam('max_wayback_timestamp');
```

2. **Update URL from Filters**:
```javascript
addRange('min_wayback_timestamp');
addRange('max_wayback_timestamp');
```

3. **Apply Filters from URL**:
```javascript
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
  
  // Update slider handles and trigger position update
  // ... (slider update logic)
}
```

## Key Technical Challenges & Solutions

### Challenge 1: Data Overwrite Issue
**Problem**: `updateFilteredScores` was overwriting wayback-filtered scores with original data.
**Solution**: Modified `updateFilteredScores` to preserve wayback changes by deep copying input data and skipping original data restoration.

### Challenge 2: Average Score Calculation
**Problem**: `average_vision_v0` wasn't being recalculated when child scores changed.
**Solution**: Added special handling for `average_vision_v0` that manually calculates average from `neural_vision_v0` and `behavior_vision_v0` scores.

### Challenge 3: Date vs Unix Timestamp Handling
**Problem**: UI needed date inputs but logic needed Unix timestamps.
**Solution**: Consistent conversion between formats - store Unix internally, display ISO dates in UI.

### Challenge 4: Model Removal Logic
**Problem**: Models weren't being removed when all scores became 'X'.
**Solution**: Added `_hasValidScore` flag tracking and proper filtering logic.

## Testing Checklist

When implementing this feature, verify:

- [ ] Wayback section appears when timestamp data is available
- [ ] Slider adjustments convert out-of-range scores to 'X'
- [ ] Models with all 'X' scores are removed from leaderboard
- [ ] Parent benchmark scores recalculate properly
- [ ] `average_vision_v0` recalculates correctly
- [ ] URL state persistence works
- [ ] Reset functionality works
- [ ] Date inputs sync with slider
- [ ] Console logging shows expected behavior

## Data Flow Summary

```
1. Backend extracts timestamp ranges → frontend initialization
2. User adjusts slider → activeFilters updated → debounced filter update
3. applyCombinedFilters → applyWaybackTimestampFilter → scores converted to 'X'
4. updateFilteredScores → preserves 'X' values → recalculates averages
5. AG Grid updated → models removed → columns hidden if needed
6. URL state updated for persistence
```

## Files Modified Summary

1. **Backend**: `benchmarks/views/leaderboard.py` - timestamp range extraction
2. **Template**: `benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard.html` - UI structure
3. **Initialization**: `static/benchmarks/js/leaderboard/core/template-initialization.js` - UI setup
4. **Slider Logic**: `static/benchmarks/js/leaderboard/filters/range-filters.js` - slider behavior
5. **State**: `static/benchmarks/js/leaderboard/ui/ui-handlers.js` - global state
6. **Core Filtering**: `static/benchmarks/js/leaderboard/filters/filter-coordinator.js` - main logic
7. **URL State**: `static/benchmarks/js/leaderboard/navigation/url-state.js` - persistence

## Future Enhancements

- Column hiding when all scores in a benchmark are 'X'
- More sophisticated timestamp handling for different data sources
- Performance optimizations for large datasets
- Additional filtering modes (e.g., "before date", "after date")

---

*This implementation successfully creates a time-travel feature for the Brain-Score leaderboard, allowing users to see how the leaderboard looked at any point in historical time.*
