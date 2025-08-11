# Wayback Timestamp Filter - Quick Implementation Guide

## Overview
Implement a time-travel filter for Brain-Score leaderboard that shows historical states by filtering scores based on submission timestamps.

## Core Requirements
1. Convert out-of-range scores to 'X'
2. Remove models with all 'X' scores or 'X' global scores
3. Hide columns with all 'X' values (leaf + parent)
4. Accurate parent calculations (exclude dropped columns entirely)
5. URL state persistence

## Data Flow
```
Slider → applyWaybackTimestampFilter → updateFilteredScores → applyGlobalScoreModelRemoval → updateColumnVisibility
```

## Implementation Steps

### 1. Backend - Extract Timestamp Ranges
**File**: `benchmarks/views/leaderboard.py`
```python
# In get_ag_grid_context function
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

### 2. Frontend UI - Hidden Wayback Section
**File**: `benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard.html`
```html
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

### 3. UI Initialization - Show Slider When Data Available
**File**: `static/benchmarks/js/leaderboard/core/template-initialization.js`
```javascript
// In initializeLeaderboardFromTemplate function
if (ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
  const waybackSection = document.getElementById('waybackTimestampSection');
  const waybackSliderContainer = document.querySelector('#waybackTimestampFilter .slider-container');
  const waybackDateMin = document.getElementById('waybackDateMin');
  const waybackDateMax = document.getElementById('waybackDateMax');
  
  if (waybackSection && waybackSliderContainer && waybackDateMin && waybackDateMax) {
    waybackSection.style.display = 'block';
    waybackSliderContainer.dataset.min = ranges.datetime_range.min_unix;
    waybackSliderContainer.dataset.max = ranges.datetime_range.max_unix;
    
    const minHandle = waybackSliderContainer.querySelector('.handle-min');
    const maxHandle = waybackSliderContainer.querySelector('.handle-max');
    
    if (minHandle && maxHandle) {
      minHandle.dataset.value = ranges.datetime_range.min_unix;
      maxHandle.dataset.value = ranges.datetime_range.max_unix;
    }
    
    const minDate = new Date(ranges.datetime_range.min_unix * 1000);
    const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
    
    waybackDateMin.value = minDate.toISOString().split('T')[0];
    waybackDateMax.value = maxDate.toISOString().split('T')[0];
  }
}
```

### 4. Slider Integration - Add Wayback Type
**File**: `static/benchmarks/js/leaderboard/filters/range-filters.js`

Add wayback slider type detection:
```javascript
const sliderType = sliderGroup?.querySelector('#paramCountMin') ? 'paramCount' : 
                   sliderGroup?.querySelector('#modelSizeMin') ? 'modelSize' : 
                   sliderGroup?.querySelector('#stimuliCountMin') ? 'stimuliCount' :
                   sliderGroup?.querySelector('#waybackDateMin') ? 'waybackTimestamp' : 'unknown';
```

Handle date formatting:
```javascript
if (sliderType === 'waybackTimestamp') {
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

Update active filters:
```javascript
} else if (filterId === 'waybackTimestampFilter' || sliderType === 'waybackTimestamp') {
  window.activeFilters.min_wayback_timestamp = minValue;
  window.activeFilters.max_wayback_timestamp = maxValue;
}
```

### 5. Global State - Add Wayback Filters
**File**: `static/benchmarks/js/leaderboard/ui/ui-handlers.js`
```javascript
window.activeFilters = {
  // ... existing filters ...
  min_wayback_timestamp: null,
  max_wayback_timestamp: null
};
```

### 6. Core Filtering Logic
**File**: `static/benchmarks/js/leaderboard/filters/filter-coordinator.js`

#### A. Main Wayback Filter Function
```javascript
function applyWaybackTimestampFilter(rowData) {
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  const isAtFullRange = (minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  if (!minTimestamp || !maxTimestamp || isAtFullRange) {
    return rowData;
  }
  
  const filteredData = rowData.map((row, rowIndex) => {
    const newRow = { ...row };
    let modelHasValidScore = false;
    
    Object.keys(row).forEach(key => {
      if (key === 'id' || key === 'rank' || key === 'model' || key === 'metadata') {
        return;
      }
      
      if (row[key] && typeof row[key] === 'object') {
        const scoreObj = row[key];
        const scoreTimestamp = scoreObj.timestamp;
        
        if (scoreTimestamp) {
          let timestampSeconds;
          if (typeof scoreTimestamp === 'string') {
            const date = new Date(scoreTimestamp);
            timestampSeconds = Math.floor(date.getTime() / 1000);
          } else {
            timestampSeconds = scoreTimestamp;
          }
          
          if (timestampSeconds < minTimestamp || timestampSeconds > maxTimestamp) {
            newRow[key] = {
              ...scoreObj,
              value: 'X',
              raw: scoreObj.raw,
              color: '#e0e1e2'
            };
          } else {
            newRow[key] = { ...scoreObj };
            if (scoreObj.value !== 'X' && scoreObj.value !== null && scoreObj.value !== undefined) {
              modelHasValidScore = true;
            }
          }
        } else {
          newRow[key] = { ...scoreObj };
          if (scoreObj.value !== 'X' && scoreObj.value !== null && scoreObj.value !== undefined) {
            modelHasValidScore = true;
          }
        }
      }
    });
    
    newRow._hasValidScore = modelHasValidScore;
    return newRow;
  });
  
  const filteredWithValidModels = filteredData.filter(row => row._hasValidScore);
  filteredWithValidModels.forEach(row => delete row._hasValidScore);
  
  return filteredWithValidModels;
}
```

#### B. Global Score Model Removal
```javascript
function applyGlobalScoreModelRemoval(rowData) {
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  const isAtFullRange = (minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  if (!minTimestamp || !maxTimestamp || isAtFullRange) {
    return rowData;
  }
  
  return rowData.filter(row => {
    const globalScore = row.average_vision_v0?.value;
    return globalScore !== 'X';
  });
}
```

#### C. Column Exclusion Check
```javascript
function isColumnHiddenByWaybackFiltering(benchmarkId) {
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  if (!isWaybackActive) {
    return false;
  }
  
  const rowData = [];
  if (window.globalGridApi) {
    window.globalGridApi.forEachNode(node => {
      if (node.data) {
        rowData.push(node.data);
      }
    });
  }
  
  const values = rowData.map(row => {
    const cellData = row[benchmarkId];
    return cellData && typeof cellData === 'object' ? cellData.value : cellData;
  }).filter(val => val !== null && val !== undefined && val !== '');
  
  return values.every(val => val === 'X');
}
```

#### D. Update applyCombinedFilters
```javascript
// In applyCombinedFilters function, add these calls:

// Apply wayback timestamp filtering
let timestampFilteredData = filteredData;
if (typeof applyWaybackTimestampFilter === 'function') {
  timestampFilteredData = applyWaybackTimestampFilter(filteredData);
}

// Update filtered scores (preserve wayback changes)
let finalData = timestampFilteredData;
if (typeof updateFilteredScores === 'function') {
  const updatedData = updateFilteredScores(timestampFilteredData);
  if (updatedData) {
    finalData = updatedData;
  }
}

// Remove models with 'X' global scores
if (typeof applyGlobalScoreModelRemoval === 'function') {
  finalData = applyGlobalScoreModelRemoval(finalData);
}
```

#### E. Fix updateFilteredScores - Preserve Wayback Changes
```javascript
// In updateFilteredScores function:

// Replace data restoration with deep copy preservation:
const workingRowData = rowData.map(row => {
  const newRow = { ...row };
  Object.keys(row).forEach(key => {
    if (key !== 'model' && key !== 'rank' && key !== 'metadata' && row[key] && typeof row[key] === 'object') {
      newRow[key] = { ...row[key] };
    }
  });
  return newRow;
});

// Skip original data restoration - preserve wayback changes

// In parent calculation loop, exclude wayback-dropped columns:
children.forEach(childId => {
  if (excludedBenchmarks.has(childId)) {
    return;
  }
  
  if (isColumnHiddenByWaybackFiltering(childId)) {
    return;
  }
  
  if (row[childId]) {
    // ... process normally
  }
});

// Add special average_vision_v0 handling:
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
    row.average_vision_v0 = {
      ...row.average_vision_v0,
      value: 'X',
      color: '#e0e1e2'
    };
  } else {
    const average = validScores.reduce((a, b) => a + b, 0) / validScores.length;
    row.average_vision_v0 = {
      ...row.average_vision_v0,
      value: parseFloat(average.toFixed(3))
    };
  }
}
```

### 7. Enhanced Column Hiding
**File**: `static/benchmarks/js/leaderboard/renderers/header-components.js`

Extend shouldColumnBeVisible for parent columns:
```javascript
} else {
  // For parent columns: check two conditions
  
  // 1. Hide if they have 0 leaf descendants (original logic)
  if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
    const leafCount = window.getFilteredLeafCount(benchmarkId);
    if (leafCount === 0) {
      return false;
    }
  }
  
  // 2. NEW: For wayback filtering, also hide parent columns if all their values are 'X'
  if (shouldHideColumnWithAllXsOrZeros(benchmarkId)) {
    return false;
  }
}
```

Update shouldHideColumnWithAllXsOrZeros for wayback detection:
```javascript
// Check if wayback timestamp filtering is active
const minTimestamp = window.activeFilters?.min_wayback_timestamp;
const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
const ranges = window.filterOptions?.datetime_range;
const fullRangeMin = ranges?.min_unix;
const fullRangeMax = ranges?.max_unix;
const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);

if (isWaybackActive) {
  const allXs = values.every(val => val === 'X');
  return allXs;
} else {
  const allXsOrZeros = values.every(val => val === 'X' || val === 0);
  return allXsOrZeros;
}
```

### 8. URL State Persistence
**File**: `static/benchmarks/js/leaderboard/navigation/url-state.js`

Add to parseURLFilters:
```javascript
window.activeFilters.min_wayback_timestamp = parseFloatParam('min_wayback_timestamp');
window.activeFilters.max_wayback_timestamp = parseFloatParam('max_wayback_timestamp');
```

Add to updateURLFromFilters:
```javascript
addRange('min_wayback_timestamp');
addRange('max_wayback_timestamp');
```

Add wayback handling to applyFiltersToUI:
```javascript
if (window.activeFilters.min_wayback_timestamp !== null || window.activeFilters.max_wayback_timestamp !== null) {
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
}
```

## Key Technical Points

### Critical Issues to Avoid:
1. **Data Overwrite**: updateFilteredScores must preserve wayback changes, not restore original data
2. **Parent Calculations**: Must exclude wayback-dropped columns entirely (not treat as 0)
3. **Global Score Timing**: Model removal based on global scores happens AFTER updateFilteredScores
4. **Column Hiding**: Apply to both leaf AND parent columns when wayback active

### Expected Results:
- Scores outside timestamp range → 'X'
- Models with all 'X' or global 'X' → removed
- Columns with all 'X' → hidden (leaf + parent)
- Parent scores → only include visible children
- Historical accuracy → no future data artifacts

### Exports Required:
```javascript
window.applyWaybackTimestampFilter = applyWaybackTimestampFilter;
window.applyGlobalScoreModelRemoval = applyGlobalScoreModelRemoval;
window.isColumnHiddenByWaybackFiltering = isColumnHiddenByWaybackFiltering;
```
