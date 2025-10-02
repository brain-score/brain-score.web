# Wayback Filter Implementation Script
**For Developers with Minimal Frontend/Backend Experience**

This script provides a step-by-step, copy-paste approach to implementing the wayback filter feature. Follow each step carefully and don't skip any parts.

## 🎯 What This Script Does
This script will add a "time travel" feature to your Brain-Score leaderboard, allowing users to see how the leaderboard looked at any point in time based on when models were submitted.

## 📋 Prerequisites Checklist
Before starting, ensure you have:
- [ ] Access to the Brain-Score web application codebase
- [ ] Permission to edit Python and JavaScript files
- [ ] A text editor or IDE (VS Code, PyCharm, etc.)
- [ ] Basic understanding of copy-paste operations

## 🚀 Implementation Steps

### Step 1: Backup Your Files
**⚠️ IMPORTANT: Always backup before making changes!**

Create copies of these files:
```bash
# Navigate to your Brain-Score web directory first
cp benchmarks/views/index.py benchmarks/views/index.py.backup
cp benchmarks/views/leaderboard.py benchmarks/views/leaderboard.py.backup
cp benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard-content.html benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard-content.html.backup
```

### Step 2: Backend Changes (Python Files)

#### Step 2.1: Update `benchmarks/views/index.py`

1. **Find the import section** at the top of the file (around lines 1-20)
2. **Add this import** after the existing imports:
```python
from datetime import datetime
```

3. **Find the line** that says something like `ENGINEERING_ROOT = 'engineering'` (around line 22)
4. **Add this function** right after that line:
```python
def get_datetime_range(models):
    """Extract min and max timestamps from model scores."""
    timestamps = []
    for model in models:
        for score in (model.scores or []):
            ts = score.get("end_timestamp")
            if ts:
                try:
                    timestamps.append(datetime.fromisoformat(ts))
                except Exception:
                    pass  # Ignore malformed timestamps
    if timestamps:
        return {
            "min": min(timestamps).isoformat(),
            "max": max(timestamps).isoformat(),
        }
    return None
```

#### Step 2.2: Update `benchmarks/views/leaderboard.py`

1. **Find the import section** at the top of the file
2. **Replace the existing import line** that mentions `get_context` with:
```python
from .index import get_context, get_datetime_range
```

3. **Add these imports** after the existing imports:
```python
from datetime import datetime
import pytz
```

4. **Find the section** that looks like this (around line 440):
```python
        'stimuli_ranges': {
            'min': 0,
            'max': round_up_aesthetically(benchmark_metadata['stimuli_ranges']['max']) if benchmark_metadata['stimuli_ranges']['max'] > 0 else 1000
        }
    }
```

5. **Add this code** right after that section:
```python

    # Compute datetime range for wayback timestamp filter
    datetime_range = get_datetime_range(context['models'])
    if datetime_range:
        # Parse the timestamps to get Unix timestamps for the slider
        min_timestamp = datetime.fromisoformat(datetime_range['min'])
        max_timestamp = datetime.fromisoformat(datetime_range['max'])
        filter_options['datetime_range'] = {
            'min': datetime_range['min'],
            'max': datetime_range['max'],
            'min_unix': int(min_timestamp.timestamp()),
            'max_unix': int(max_timestamp.timestamp())
        }
```

6. **Find the section** that looks like this (around line 320):
```python
            rd[vid] = {
                'value': score.get('score_ceiled', 'X'),
                'raw': score.get('score_raw'),
                'error': score.get('error'),
                'color': score.get('color'),
                'complete': score.get('is_complete', True),
                'benchmark': minimal_benchmark if minimal_benchmark else None
            }
```

7. **Replace it with**:
```python
            rd[vid] = {
                'value': score.get('score_ceiled', 'X'),
                'raw': score.get('score_raw'),
                'error': score.get('error'),
                'color': score.get('color'),
                'complete': score.get('is_complete', True),
                'benchmark': minimal_benchmark if minimal_benchmark else None,  # Include benchmark metadata for bibtex collection
                'timestamp': score.get('end_timestamp')  # Include end_timestamp for wayback filtering
            }
```

### Step 3: Frontend HTML Template

#### Step 3.1: Update `benchmarks/templates/benchmarks/leaderboard/ag-grid-leaderboard-content.html`

1. **Find the section** that looks like this (around line 210):
```html
      <!-- Benchmark Stimuli Section -->
      <div class="metadata-section">
        <div class="filter-group">
          <div class="filter-header">
            <label>Number of Stimuli</label>
            <div class="range-values">
              <input type="number" class="range-input-min" id="stimuliCountMin" min="0" max="1000" value="0">
              <span class="range-separator">-</span>
              <input type="number" class="range-input-max" id="stimuliCountMax" min="0" max="1000" value="1000">
            </div>
          </div>
          <div class="range-filter dual-handle">
            <div class="slider-container" data-min="0" data-max="1000">
              <div class="slider-track"></div>
              <div class="slider-range"></div>
              <div class="slider-handle handle-min" data-value="0"></div>
              <div class="slider-handle handle-max" data-value="1000"></div>
            </div>
          </div>
        </div>
      </div>
```

2. **Add this code** right after that section:
```html

      <!-- Wayback Timestamp Section -->
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

### Step 4: JavaScript Files (Frontend Logic)

#### Step 4.1: Update `static/benchmarks/js/leaderboard/core/template-initialization.js`

1. **Find the section** that looks like this (around line 127):
```javascript
        }
      }
    }
    
    // Initialize grid
```

2. **Replace it with**:
```javascript
        }
      }
    }

    // Initialize wayback timestamp filter if datetime_range data is available
    if (ranges.datetime_range?.min_unix && ranges.datetime_range?.max_unix) {
      const waybackSection = document.getElementById('waybackTimestampSection');
      const waybackSliderContainer = document.querySelector('#waybackTimestampFilter .slider-container');
      const waybackDateMin = document.getElementById('waybackDateMin');
      const waybackDateMax = document.getElementById('waybackDateMax');

      if (waybackSection && waybackSliderContainer && waybackDateMin && waybackDateMax) {
        // Show the wayback section
        waybackSection.style.display = 'block';
        
        // Set slider range using Unix timestamps
        waybackSliderContainer.dataset.min = ranges.datetime_range.min_unix;
        waybackSliderContainer.dataset.max = ranges.datetime_range.max_unix;
        
        // Set initial handle positions
        const minHandle = waybackSliderContainer.querySelector('.handle-min');
        const maxHandle = waybackSliderContainer.querySelector('.handle-max');
        if (minHandle && maxHandle) {
          minHandle.dataset.value = ranges.datetime_range.min_unix;
          maxHandle.dataset.value = ranges.datetime_range.max_unix;
        }
        
        // Set date input values
        const minDate = new Date(ranges.datetime_range.min_unix * 1000);
        const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
        waybackDateMin.value = minDate.toISOString().split('T')[0];
        waybackDateMax.value = maxDate.toISOString().split('T')[0];
        
        console.log('Wayback timestamp filter initialized:', {
          min_unix: ranges.datetime_range.min_unix,
          max_unix: ranges.datetime_range.max_unix,
          min_date: waybackDateMin.value,
          max_date: waybackDateMax.value
        });
      }
    }
    
    // Initialize grid
```

#### Step 4.2: Update `static/benchmarks/js/leaderboard/filters/range-filters.js`

**🔍 Finding the Right Sections**: This file has several sections to update. Use your text editor's "Find" function (Ctrl+F or Cmd+F) to locate each section.

1. **Find this line** (around line 30):
```javascript
                     sliderGroup?.querySelector('#stimuliCountMin') ? 'stimuliCount' : 'unknown';
```

2. **Replace it with**:
```javascript
                     sliderGroup?.querySelector('#stimuliCountMin') ? 'stimuliCount' :
                     sliderGroup?.querySelector('#waybackDateMin') ? 'waybackTimestamp' : 'unknown';
```

3. **Find this section** (around line 45):
```javascript
    // Update input fields
    if (minInput) minInput.value = Math.round(minValue);
    if (maxInput) maxInput.value = Math.round(maxValue);
```

4. **Replace it with**:
```javascript
    // Update input fields
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
```

5. **Find this section** (around line 90):
```javascript
        skipDebounce
      });
    }
    
    // Apply filters with debouncing - but not during initial setup
```

6. **Replace it with**:
```javascript
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
```

7. **Find this section** (around line 160):
```javascript
  if (minInput) {
    minInput.addEventListener('input', () => {
      const value = parseFloat(minInput.value) || min;
      minValue = Math.max(min, Math.min(value, maxValue - 1));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
```

8. **Replace it with**:
```javascript
  if (minInput) {
    minInput.addEventListener('input', () => {
      let value;
      if (sliderType === 'waybackTimestamp') {
        // Convert date string to Unix timestamp
        const dateValue = new Date(minInput.value);
        value = isNaN(dateValue.getTime()) ? min : Math.floor(dateValue.getTime() / 1000);
      } else {
        value = parseFloat(minInput.value) || min;
      }
      minValue = Math.max(min, Math.min(value, maxValue - 1));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
```

9. **Find this section** (around line 176):
```javascript
  if (maxInput) {
    maxInput.addEventListener('input', () => {
      const value = parseFloat(maxInput.value) || max;
      maxValue = Math.min(max, Math.max(value, minValue + 1));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
```

10. **Replace it with**:
```javascript
  if (maxInput) {
    maxInput.addEventListener('input', () => {
      let value;
      if (sliderType === 'waybackTimestamp') {
        // Convert date string to Unix timestamp
        const dateValue = new Date(maxInput.value);
        value = isNaN(dateValue.getTime()) ? max : Math.floor(dateValue.getTime() / 1000);
      } else {
        value = parseFloat(maxInput.value) || max;
      }
      maxValue = Math.min(max, Math.max(value, minValue + 1));
      updateSliderPosition();
      updateActiveFilters();
    });
  }
```

11. **Find this section** (around line 233):
```javascript
    } else if (sliderGroup?.querySelector('#stimuliCountMin') && ranges.stimuli_ranges?.max) {
      max = ranges.stimuli_ranges.max;
      container.dataset.max = max;
    }
```

12. **Add this code** right after that section:
```javascript
    } else if (sliderGroup?.querySelector('#waybackDateMin') && ranges.datetime_range?.max_unix) {
      max = ranges.datetime_range.max_unix;
      container.dataset.max = max;
```

13. **Find this section** (around line 270):
```javascript
    if (minInput) minInput.value = min;
    if (maxInput) maxInput.value = max;
```

14. **Replace it with**:
```javascript
    // Check if this is a wayback timestamp slider
    const isWaybackSlider = sliderGroup?.querySelector('#waybackDateMin');
    
    if (isWaybackSlider) {
      // Convert Unix timestamps to date strings for date inputs
      if (minInput && ranges.datetime_range?.min_unix) {
        const minDate = new Date(ranges.datetime_range.min_unix * 1000);
        minInput.value = minDate.toISOString().split('T')[0];
      }
      if (maxInput && ranges.datetime_range?.max_unix) {
        const maxDate = new Date(ranges.datetime_range.max_unix * 1000);
        maxInput.value = maxDate.toISOString().split('T')[0];
      }
    } else {
      // Standard numeric inputs
      if (minInput) minInput.value = min;
      if (maxInput) maxInput.value = max;
    }
```

#### Step 4.3: Update `static/benchmarks/js/leaderboard/filters/filter-coordinator.js`

**⚠️ This is the most complex file. Take your time and be very careful with copy-paste.**

1. **Find this section** (around line 170):
```javascript
    public_data_only: false
  };
```

2. **Replace it with**:
```javascript
    public_data_only: false,
    min_wayback_timestamp: null,
    max_wayback_timestamp: null
  };
```

3. **Find this section** (around line 116):
```javascript
  // Update filtered scores on the filtered data BEFORE setting it on the grid
  let finalData = filteredData;
  if (typeof updateFilteredScores === 'function') {
    const updatedData = updateFilteredScores(filteredData);
    if (updatedData) {
      finalData = updatedData;
    }
  }
```

4. **Replace it with**:
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

  // Additional pass: Remove models where global score (average_vision_v0) is 'X'
  // This happens after updateFilteredScores because that's where average_vision_v0 gets recalculated
  if (typeof applyGlobalScoreModelRemoval === 'function') {
    finalData = applyGlobalScoreModelRemoval(finalData);
  }
```

5. **Find this section** (around line 327):
```javascript
  const workingRowData = rowData.map(row => ({ ...row }));
  
  // First restore original data for all columns
  workingRowData.forEach((row) => {
    const originalRow = window.originalRowData.find(origRow => origRow.id === row.id);
    if (!originalRow) return;
    
    Object.keys(originalRow).forEach(key => {
      if (key !== 'model' && key !== 'rank' && originalRow[key] && typeof originalRow[key] === 'object') {
        row[key] = { ...originalRow[key] };
      }
    });
  });
```

6. **Replace it with**:
```javascript
  console.log('updateFilteredScores called - checking for wayback timestamp changes...');
  
  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  const hierarchyMap = window.buildHierarchyFromTree(window.benchmarkTree);
  
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

7. **Find this section** (around line 382):
```javascript
        children.forEach(childId => {
          if (!excludedBenchmarks.has(childId) && row[childId]) {
            const childScore = row[childId].value;
            const hasValidScore = childScore !== null && childScore !== undefined && 
                                 childScore !== '' && childScore !== 'X' &&
                                 !isNaN(parseFloat(childScore));
            childInfo.push({ childId, childScore, hasValidScore });
          }
        });
```

8. **Replace it with**:
```javascript
        children.forEach(childId => {
          // Check if column is hidden by wayback filtering
          const isHiddenByWayback = typeof isColumnHiddenByWaybackFiltering === 'function' && 
                                   isColumnHiddenByWaybackFiltering(childId);
          
          if (!excludedBenchmarks.has(childId) && !isHiddenByWayback && row[childId]) {
            const childScore = row[childId].value;
            const hasValidScore = childScore !== null && childScore !== undefined && 
                                 childScore !== '' && childScore !== 'X' &&
                                 !isNaN(parseFloat(childScore));
            childInfo.push({ childId, childScore, hasValidScore });
          }
        });
```

9. **Find this section** (around line 424):
```javascript
          children.forEach(childId => {
            if (!excludedBenchmarks.has(childId) && row[childId]) {
              validChildrenCount++;
              const childScore = row[childId].value;
              if (childScore !== null && childScore !== undefined && childScore !== '' && childScore !== 'X') {
                const numVal = typeof childScore === 'string' ? parseFloat(childScore) : childScore;
                if (!isNaN(numVal) && numVal > 0) {
                  nonZeroChildrenCount++;
                }
              }
            }
          });
```

10. **Replace it with**:
```javascript
          children.forEach(childId => {
            // Check if column is hidden by wayback filtering
            const isHiddenByWayback = typeof isColumnHiddenByWaybackFiltering === 'function' && 
                                     isColumnHiddenByWaybackFiltering(childId);
            
            if (!excludedBenchmarks.has(childId) && !isHiddenByWayback && row[childId]) {
              validChildrenCount++;
              const childScore = row[childId].value;
              if (childScore !== null && childScore !== undefined && childScore !== '' && childScore !== 'X') {
                const numVal = typeof childScore === 'string' ? parseFloat(childScore) : childScore;
                if (!isNaN(numVal) && numVal > 0) {
                  nonZeroChildrenCount++;
                }
              }
            }
          });
```

11. **Find the very end of the file** (around line 700) where you see something like:
```javascript
window.updateFilteredScores = updateFilteredScores;
window.toggleFilteredScoreColumn = toggleFilteredScoreColumn;
```

12. **Add this LARGE block of code** right before those lines:
```javascript

// Check if column is hidden by wayback filtering
function isColumnHiddenByWaybackFiltering(benchmarkId) {
  // Only check for wayback filtering if it's active
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  if (!isWaybackActive) {
    return false; // No wayback filtering, column not hidden
  }
  
  // Get current row data from the grid
  const rowData = [];
  if (window.globalGridApi) {
    window.globalGridApi.forEachNode(node => {
      if (node.data) {
        rowData.push(node.data);
      }
    });
  }
  
  if (rowData.length === 0) {
    return false;
  }
  
  // Check if all values in this column are 'X'
  const values = rowData.map(row => {
    const cellData = row[benchmarkId];
    return cellData && typeof cellData === 'object' ? cellData.value : cellData;
  }).filter(val => val !== null && val !== undefined && val !== '');
  
  if (values.length === 0) {
    return false; // Don't hide if no values
  }
  
  const allXs = values.every(val => val === 'X');
  return allXs;
}

// Apply wayback timestamp filtering
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
  
  console.log('Applying wayback timestamp filter:', {
    minTimestamp,
    maxTimestamp,
    minDate: new Date(minTimestamp * 1000).toISOString(),
    maxDate: new Date(maxTimestamp * 1000).toISOString()
  });
  
  let totalScoresProcessed = 0;
  let scoresWithTimestamps = 0;
  let scoresWithoutTimestamps = 0;
  let scoresFilteredOut = 0;
  
  const filteredData = rowData.map(row => {
    const newRow = { ...row };
    let hasValidScores = false;
    let allScoresX = true;
    
    // Process each score field in the row
    Object.keys(row).forEach(key => {
      // Skip non-score fields
      if (key === 'id' || key === 'rank' || key === 'model' || key === 'metadata') {
        return;
      }
      
      const scoreData = row[key];
      if (scoreData && typeof scoreData === 'object' && scoreData.value !== undefined) {
        totalScoresProcessed++;
        
        // Check if this score has a timestamp
        const timestamp = scoreData.timestamp;
        if (timestamp) {
          scoresWithTimestamps++;
          
          try {
            // Parse the timestamp and convert to Unix timestamp
            const scoreTime = new Date(timestamp).getTime() / 1000;
            
            // Check if the score timestamp is within the wayback range
            if (scoreTime >= minTimestamp && scoreTime <= maxTimestamp) {
              // Score is within range, keep it
              newRow[key] = { ...scoreData };
              if (scoreData.value !== 'X') {
                hasValidScores = true;
                allScoresX = false;
              }
            } else {
              // Score is outside range, convert to 'X'
              newRow[key] = {
                ...scoreData,
                value: 'X',
                raw: null,
                error: null
              };
              scoresFilteredOut++;
            }
          } catch (error) {
            console.warn('Error parsing timestamp:', timestamp, error);
            // On error, treat as if no timestamp (convert to X)
            newRow[key] = {
              ...scoreData,
              value: 'X',
              raw: null,
              error: null
            };
            scoresFilteredOut++;
          }
        } else {
          // No timestamp, convert to 'X'
          scoresWithoutTimestamps++;
          newRow[key] = {
            ...scoreData,
            value: 'X',
            raw: null,
            error: null
          };
          scoresFilteredOut++;
        }
      }
    });
    
    return newRow;
  });
  
  // Filter out models where all individual scores became 'X'
  const filteredWithValidModels = filteredData.filter(row => {
    // Check if model has at least one non-'X' individual score
    const hasValidScore = Object.keys(row).some(key => {
      if (key === 'id' || key === 'rank' || key === 'model' || key === 'metadata') {
        return false;
      }
      
      const scoreData = row[key];
      if (scoreData && typeof scoreData === 'object') {
        return scoreData.value !== 'X' && scoreData.value !== null && scoreData.value !== undefined;
      }
      return false;
    });
    
    return hasValidScore;
  });
  
  const originalCount = rowData.length;
  const filteredCount = filteredWithValidModels.length;
  const removedCount = originalCount - filteredCount;
  
  console.log('Wayback timestamp filtering results:', {
    originalRows: originalCount,
    filteredRows: filteredCount,
    removedRows: removedCount,
    totalScoresProcessed,
    scoresWithTimestamps,
    scoresWithoutTimestamps,
    scoresFilteredOut,
    percentageScoresWithTimestamps: ((scoresWithTimestamps / totalScoresProcessed) * 100).toFixed(1) + '%',
    percentageScoresFilteredOut: ((scoresFilteredOut / totalScoresProcessed) * 100).toFixed(1) + '%'
  });
  
  return filteredWithValidModels;
}

// Apply global score model removal
function applyGlobalScoreModelRemoval(rowData) {
  // Only apply this additional filtering if wayback timestamp filtering is active
  const minTimestamp = window.activeFilters?.min_wayback_timestamp;
  const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
  
  // Get the actual range limits from filter options
  const ranges = window.filterOptions?.datetime_range;
  const fullRangeMin = ranges?.min_unix;
  const fullRangeMax = ranges?.max_unix;
  
  const isAtFullRange = (minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
  
  if (!minTimestamp || !maxTimestamp || isAtFullRange) {
    return rowData; // No wayback filtering active, don't remove any models
  }
  
  const originalCount = rowData.length;
  
  // Filter out models where average_vision_v0 is 'X'
  const filteredData = rowData.filter(row => {
    const globalScore = row.average_vision_v0?.value;
    return globalScore !== 'X';
  });
  
  const removedCount = originalCount - filteredData.length;
  
  console.log('Global score model removal:', {
    originalModels: originalCount,
    modelsWithXGlobalScore: removedCount,
    remainingModels: filteredData.length,
    removedModels: removedCount > 0 ? rowData.filter(row => row.average_vision_v0?.value === 'X').slice(0, 3).map(row => row.model?.name || 'Unknown') : []
  });
  
  return filteredData;
}
```

13. **Find the section** where you see exports like:
```javascript
window.LeaderboardFilterCoordinator = {
  applyCombinedFilters,
  resetAllFilters,
  updateFilteredScores,
  toggleFilteredScoreColumn
};
```

14. **Replace it with**:
```javascript
window.LeaderboardFilterCoordinator = {
  applyCombinedFilters,
  resetAllFilters,
  updateFilteredScores,
  toggleFilteredScoreColumn,
  isColumnHiddenByWaybackFiltering,
  applyWaybackTimestampFilter,
  applyGlobalScoreModelRemoval
};
```

15. **Find the section** where you see:
```javascript
window.applyCombinedFilters = applyCombinedFilters;
window.resetAllFilters = resetAllFilters;
window.updateFilteredScores = updateFilteredScores;
window.toggleFilteredScoreColumn = toggleFilteredScoreColumn;
```

16. **Replace it with**:
```javascript
window.applyCombinedFilters = applyCombinedFilters;
window.resetAllFilters = resetAllFilters;
window.updateFilteredScores = updateFilteredScores;
window.toggleFilteredScoreColumn = toggleFilteredScoreColumn;
window.isColumnHiddenByWaybackFiltering = isColumnHiddenByWaybackFiltering;
window.applyWaybackTimestampFilter = applyWaybackTimestampFilter;
window.applyGlobalScoreModelRemoval = applyGlobalScoreModelRemoval;
```

#### Step 4.4: Update `static/benchmarks/js/leaderboard/navigation/url-state.js`

1. **Find this section** (around line 38):
```javascript
  window.activeFilters.min_stimuli_count = parseFloatParam('min_stimuli_count');
  window.activeFilters.max_stimuli_count = parseFloatParam('max_stimuli_count');
  
  // Apply filters to UI
```

2. **Replace it with**:
```javascript
  window.activeFilters.min_stimuli_count = parseFloatParam('min_stimuli_count');
  window.activeFilters.max_stimuli_count = parseFloatParam('max_stimuli_count');
  window.activeFilters.min_wayback_timestamp = parseFloatParam('min_wayback_timestamp');
  window.activeFilters.max_wayback_timestamp = parseFloatParam('max_wayback_timestamp');
  
  // Apply filters to UI
```

3. **Find this section** (around line 104):
```javascript
      const max = window.activeFilters.max_stimuli_count || 1000;
      window.LeaderboardRangeFilters.setRangeValues('stimuliCountMin', min, max);
    }
  }
```

4. **Add this code** right after that section:
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
    
    // Update slider handles through the range filter system
    if (typeof window.LeaderboardRangeFilters?.setRangeValues === 'function') {
      const min = window.activeFilters.min_wayback_timestamp || 0;
      const max = window.activeFilters.max_wayback_timestamp || 2000000000;
      window.LeaderboardRangeFilters.setRangeValues('waybackDateMin', min, max);
    }
  }
```

5. **Find this section** (around line 216):
```javascript
  addRange('min_stimuli_count');
  addRange('max_stimuli_count');
  
  // Add benchmark exclusions
```

6. **Replace it with**:
```javascript
  addRange('min_stimuli_count');
  addRange('max_stimuli_count');
  addRange('min_wayback_timestamp');
  addRange('max_wayback_timestamp');
  
  // Add benchmark exclusions
```

#### Step 4.5: Update `static/benchmarks/js/leaderboard/ui/ui-handlers.js`

1. **Find this section** (around line 108):
```javascript
      benchmark_tasks: [],
      public_data_only: false
    };
```

2. **Replace it with**:
```javascript
      benchmark_tasks: [],
      public_data_only: false,
      min_wayback_timestamp: null,
      max_wayback_timestamp: null
    };
```

#### Step 4.6: Update `static/benchmarks/js/leaderboard/renderers/header-components.js`

1. **Find this section** (around line 144):
```javascript
    } else {
      // For parent columns: hide if they have 0 leaf descendants
      if (window.getFilteredLeafCount && typeof window.getFilteredLeafCount === 'function') {
        const leafCount = window.getFilteredLeafCount(benchmarkId);
        if (leafCount === 0) {
          return false;
        }
      }
    }
```

2. **Replace it with**:
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

3. **Find this section** (around line 200):
```javascript
    // Check if all values are 'X' or 0
    const allXsOrZeros = values.every(val => val === 'X' || val === 0);
    
    
    return allXsOrZeros;
```

4. **Replace it with**:
```javascript
    // Check if wayback timestamp filtering is active
    const minTimestamp = window.activeFilters?.min_wayback_timestamp;
    const maxTimestamp = window.activeFilters?.max_wayback_timestamp;
    const ranges = window.filterOptions?.datetime_range;
    const fullRangeMin = ranges?.min_unix;
    const fullRangeMax = ranges?.max_unix;
    const isWaybackActive = minTimestamp && maxTimestamp && !(minTimestamp <= fullRangeMin && maxTimestamp >= fullRangeMax);
    
    if (isWaybackActive) {
      // For wayback filtering: hide only if ALL values are 'X' (not 0s, since 0s are legitimate scores)
      const allXs = values.every(val => val === 'X');
      
      // Determine if this is a parent or leaf column for better logging
      const hierarchyMap = window.cachedHierarchyMap || new Map();
      const children = hierarchyMap.get(benchmarkId) || [];
      const columnType = children.length === 0 ? 'leaf' : 'parent';
      
      console.log(`Column visibility check for ${columnType} ${benchmarkId}:`, {
        columnType,
        totalValues: values.length,
        allXs,
        sampleValues: values.slice(0, 5),
        isWaybackActive,
        willHide: allXs
      });
      return allXs;
    }
    
    // For non-wayback filtering: hide if all values are 'X' or 0 (original logic)
    const allXsOrZeros = values.every(val => val === 'X' || val === 0);
    return allXsOrZeros;
```

### Step 5: Testing Your Implementation

1. **Restart your Django server**:
```bash
python manage.py runserver
```

2. **Open your browser** and navigate to the leaderboard

3. **Open Developer Tools** (F12 in most browsers)

4. **Check the Console tab** for these messages:
   - "Wayback timestamp filter initialized" (if you have data with timestamps)
   - No error messages

5. **Look for the wayback filter** in the Advanced Filters panel - it should appear if you have timestamp data

### Step 6: Verification Checklist

- [ ] No console errors appear
- [ ] Wayback filter section appears (if timestamp data exists)
- [ ] Date inputs synchronize with slider movement
- [ ] Filtering works when you adjust the slider
- [ ] URL updates when you change wayback filter settings

## 🚨 Troubleshooting

### If the wayback filter doesn't appear:
- Check if your data has timestamp information
- Look for console errors
- Verify all files were updated correctly

### If you get JavaScript errors:
- Double-check that you copied all code exactly
- Make sure you didn't miss any sections
- Verify file paths match your project structure

### If filtering doesn't work:
- Check browser console for error messages
- Verify that scores have timestamp data
- Make sure all JavaScript functions were added

## 🆘 Getting Help

If you encounter issues:

1. **Check the browser console** for error messages
2. **Verify each file** was updated correctly
3. **Compare your changes** with the original tutorial
4. **Test one section at a time** to isolate problems

## 🎉 Success!

If everything works, you should now have a fully functional wayback filter that allows users to "time travel" through your leaderboard history!

The filter will:
- Show a slider for selecting date ranges
- Filter scores based on submission timestamps
- Hide columns/models that don't have data in the selected timeframe
- Preserve URL state for sharing filtered views
- Provide detailed console logging for debugging

Congratulations on implementing this advanced feature!
