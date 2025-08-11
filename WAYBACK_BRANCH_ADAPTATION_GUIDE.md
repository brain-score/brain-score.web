# Adapting webUROP-Wayback-Machine Branch to Complete Solution

## Current State Analysis

The `webUROP-Wayback-Machine` branch has a **basic wayback timestamp filter** with these features:
- ✅ Date slider UI (always visible)
- ✅ Basic timestamp filtering (removes entire models)
- ✅ Date input synchronization
- ✅ Basic backend timestamp range extraction
- ❌ **Missing**: Score-level filtering (converts to 'X')
- ❌ **Missing**: Column hiding functionality
- ❌ **Missing**: Accurate parent score recalculation
- ❌ **Missing**: Global score model removal
- ❌ **Missing**: Unix timestamp handling

## Key Differences from Complete Solution

### Current Implementation:
- **Model-level filtering**: Removes entire models if no scores are within range
- **Visible UI**: Wayback section always shown
- **Date-based**: Uses date objects for filtering
- **Simple logic**: Basic timestamp comparison

### Target Implementation:
- **Score-level filtering**: Individual scores become 'X' when outside range
- **Conditional UI**: Wayback section only shown when data available
- **Unix timestamps**: More efficient numeric comparisons
- **Advanced features**: Column hiding, accurate parent calculations, model removal

## Adaptation Steps

### 1. Update Backend - Add Unix Timestamps
**File**: `benchmarks/views/leaderboard.py`

**Current** (around line 453):
```python
if all_timestamps:
    filter_options['datetime_range'] = {
        'min': min(all_timestamps).isoformat(),
        'max': max(all_timestamps).isoformat()
    }
```

**Replace with**:
```python
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

### 2. Update HTML - Make Wayback Section Conditional
**File**: `benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard.html`

**Current** (around line 36):
```html
<!-- Wayback Timestamp Section -->
<div class="metadata-section">
```

**Replace with**:
```html
<!-- Wayback Timestamp Section -->
<div class="metadata-section" id="waybackTimestampSection" style="display: none;">
```

**Current** (around line 50):
```html
<div
  id="waybackDateSlider"
  class="slider-container"
  data-type="date"
  data-min="1704067200"
  data-max="1767139200">
```

**Replace with**:
```html
<div class="filter-group" id="waybackTimestampFilter">
  <!-- existing date inputs -->
  <div class="range-filter dual-handle">
    <div class="slider-container" data-min="0" data-max="2000000000">
      <div class="slider-track"></div>
      <div class="slider-range"></div>
      <div class="slider-handle handle-min" data-value="0"></div>
      <div class="slider-handle handle-max" data-value="2000000000"></div>
    </div>
  </div>
</div>
```

### 3. Replace JavaScript Implementation
**File**: `static/benchmarks/js/ag-grid-leaderboard.js`

**Remove existing wayback functions** (lines ~534-906):
- `updateWaybackFilters`
- `syncSliderHandlesWithDateInputs`
- `syncSliderWithDateInputs`
- `initializeWaybackDateFilter`
- All slider dragging logic

**Update activeFilters** (line 18-19):
```javascript
// REMOVE:
wayback_min_date: null,
wayback_max_date: null

// ADD:
min_wayback_timestamp: null,
max_wayback_timestamp: null
```

**Remove wayback initialization call** (around line 348):
```javascript
// REMOVE this setTimeout block:
setTimeout(() => {
  if (typeof initializeWaybackDateFilter === 'function') {
    console.log(' Delayed init of Wayback calendar inputs...');
    initializeWaybackDateFilter();
  } else {
    console.warn(' initializeWaybackDateFilter not defined yet.');
  }
}, 300);
```

### 4. Replace Filter Logic in filter-coordinator.js
**File**: `static/benchmarks/js/leaderboard/filters/filter-coordinator.js`

**Remove existing wayback filter** (lines 113-129):
```javascript
// REMOVE this entire block:
// Wayback Timestamp filter
if (window.activeFilters.wayback_min_date || window.activeFilters.wayback_max_date) {
  const scores = Object.values(row).filter(v => v && typeof v === 'object' && v.timestamp);
  const minDate = window.activeFilters.wayback_min_date ? new Date(window.activeFilters.wayback_min_date) : null;
  const maxDate = window.activeFilters.wayback_max_date ? new Date(window.activeFilters.wayback_max_date) : null;

  let withinRange = false;
  for (const score of scores) {
    const ts = score.timestamp ? new Date(score.timestamp) : null;
    if (ts && (!minDate || ts >= minDate) && (!maxDate || ts <= maxDate)) {
      withinRange = true;
      break;
    }
  }

  if (!withinRange) return false;
}
```

### 5. Add Complete Implementation Files

**Create these new files from the complete solution**:

1. **`static/benchmarks/js/leaderboard/core/template-initialization.js`**
   - Add wayback UI initialization logic

2. **`static/benchmarks/js/leaderboard/filters/range-filters.js`** 
   - Modify existing file to add wayback timestamp slider support

3. **`static/benchmarks/js/leaderboard/ui/ui-handlers.js`**
   - Add wayback timestamp filters to global state

4. **`static/benchmarks/js/leaderboard/renderers/header-components.js`**
   - Add column hiding functionality

5. **`static/benchmarks/js/leaderboard/navigation/url-state.js`**
   - Add URL state persistence

### 6. Add Complete Filter Functions
**File**: `static/benchmarks/js/leaderboard/filters/filter-coordinator.js`

**Add these functions** (copy from complete solution):
```javascript
// Add before applyCombinedFilters:
function isColumnHiddenByWaybackFiltering(benchmarkId) { /* ... */ }

// Add after existing functions:
function applyWaybackTimestampFilter(rowData) { /* ... */ }
function applyGlobalScoreModelRemoval(rowData) { /* ... */ }
```

**Update applyCombinedFilters** to call new functions:
```javascript
// Add after existing filteredData logic:
let timestampFilteredData = filteredData;
if (typeof applyWaybackTimestampFilter === 'function') {
  timestampFilteredData = applyWaybackTimestampFilter(filteredData);
}

// Update the updateFilteredScores call:
let finalData = timestampFilteredData;
if (typeof updateFilteredScores === 'function') {
  const updatedData = updateFilteredScores(timestampFilteredData);
  if (updatedData) {
    finalData = updatedData;
  }
}

// Add global score model removal:
if (typeof applyGlobalScoreModelRemoval === 'function') {
  finalData = applyGlobalScoreModelRemoval(finalData);
}
```

**Update updateFilteredScores** to preserve wayback changes and exclude dropped columns.

### 7. Update Range Filters Integration
**File**: `static/benchmarks/js/leaderboard/filters/range-filters.js`

**Find the existing dual handle slider initialization** and modify it to:
- Detect wayback timestamp slider type
- Handle Unix timestamp to date conversion
- Update `window.activeFilters.min_wayback_timestamp` and `max_wayback_timestamp`

### 8. Add Column Visibility System
**File**: `static/benchmarks/js/leaderboard/renderers/header-components.js`

This file likely doesn't exist in the current branch. Copy the complete implementation:
- `updateColumnVisibility()` function
- `shouldHideColumnWithAllXsOrZeros()` function
- Enhanced parent column hiding logic

## Migration Strategy

### Phase 1: Quick Migration (Core Functionality)
1. Update backend timestamp extraction
2. Replace JavaScript filter logic with score-level filtering
3. Add basic column hiding
4. Test core wayback functionality

### Phase 2: Advanced Features
1. Add accurate parent score recalculation
2. Add global score model removal
3. Add enhanced column hiding for parent columns
4. Add URL state persistence

### Phase 3: Polish
1. Add proper UI initialization
2. Add debugging and console logging
3. Add reset functionality
4. Performance optimizations

## Key Migration Points

### ⚠️ **Critical Changes Required**:
1. **Filter Logic**: Change from model-level to score-level filtering
2. **Data Handling**: Switch from Date objects to Unix timestamps
3. **UI Integration**: Remove custom slider code, use existing dual-handle system
4. **File Structure**: Add missing modular JavaScript files

### ✅ **Can Reuse**:
1. Basic HTML structure (with modifications)
2. Backend timestamp extraction pattern (with Unix addition)
3. General filter integration approach

### 🔄 **Architecture Shift**:
- **From**: Simple model removal based on timestamp ranges
- **To**: Complex score transformation with accurate recalculations

This adaptation transforms the basic timestamp filter into a complete time-travel feature with historical accuracy and advanced functionality.
