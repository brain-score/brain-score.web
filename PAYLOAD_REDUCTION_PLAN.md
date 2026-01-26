# Payload Reduction Implementation Plan

**Goal:** Reduce leaderboard payload from 14.28 MB to ~4-5 MB (65% reduction)

**Status:** Code changes ready for review - DO NOT IMPLEMENT YET

---

## Changes Summary

### Fields to Remove from Score Objects

| Field | Current Size | Action | Impact |
|-------|-------------|--------|--------|
| `color` | ~7-8 MB | Remove → compute client-side | 50-60% reduction |
| `error` | ~0.5 MB | Remove (unused) | 3-4% reduction |
| `raw` | ~2-3 MB | Remove (benchmark pages fetch separately) | 15-20% reduction |
| **Total** | **~10-11 MB** | | **~70% reduction** |

**Keep:**
- `value` - Displayed score
- `complete` - Data availability flag
- `timestamp` - Needed for upcoming feature

---

## Code Changes Required

### 1. Backend: benchmarks/views/leaderboard.py

**Current code (line 337-344):**
```python
rd[vid] = {
    'value': score.get('score_ceiled', 'X'),
    'raw': score.get('score_raw'),
    'error': score.get('error'),
    'color': score.get('color'),
    'complete': score.get('is_complete', True),
    'timestamp': score.get('end_timestamp')
}
```

**Optimized code:**
```python
rd[vid] = {
    'value': score.get('score_ceiled', 'X'),
    'complete': score.get('is_complete', True),
    'timestamp': score.get('end_timestamp')
}
```

**Changes:**
- ✅ Remove `raw` field
- ✅ Remove `error` field
- ✅ Remove `color` field

### 2. Frontend: Use Existing Color Computation

**✅ Good news: The frontend already has color computation capability!**

The file `static/benchmarks/js/leaderboard/utilities/color-utils.js` already contains:
- `calculateRepresentativeColor(value, minValue, maxValue, rootParent)` - Sophisticated color calculation with gamma correction, alpha blending, and engineering vs. non-engineering palettes
- `recalculateColorsForBenchmark(rowData, benchmarkId, hierarchyMap, rootParentCache)` - Batch color recalculation

**What we need to do:**

1. **Ensure color-utils.js is loaded** in the leaderboard template
2. **Compute min/max values per benchmark** when data loads
3. **Update score cell renderer** to use `calculateRepresentativeColor()` instead of pre-computed colors

**Implementation:**

```javascript
// In leaderboard.js - Add benchmark min/max computation on data load

/**
 * Compute min/max values for all benchmarks
 * Called once when data loads, cached for performance
 */
function computeBenchmarkMinMax(rowData, columnDefs) {
    const benchmarkStats = {};

    // Get all benchmark column IDs (exclude rank, model, etc.)
    const benchmarkIds = columnDefs
        .filter(col => col.field !== 'rank' && col.field !== 'model' && col.field !== 'public_toggle')
        .map(col => col.field);

    benchmarkIds.forEach(benchmarkId => {
        const values = [];

        rowData.forEach(row => {
            const scoreData = row[benchmarkId];
            if (scoreData && scoreData.value !== 'X' && scoreData.value !== null) {
                const numValue = typeof scoreData.value === 'string'
                    ? parseFloat(scoreData.value)
                    : scoreData.value;

                if (!isNaN(numValue)) {
                    values.push(numValue);
                }
            }
        });

        if (values.length > 0) {
            benchmarkStats[benchmarkId] = {
                min: Math.min(...values),
                max: Math.max(...values)
            };
        } else {
            benchmarkStats[benchmarkId] = { min: 0, max: 1 };
        }
    });

    return benchmarkStats;
}

// Store stats globally for cell renderer access
window.benchmarkStats = null;

// Call after data loads
function onDataLoaded(rowData, columnDefs) {
    window.benchmarkStats = computeBenchmarkMinMax(rowData, columnDefs);
}
```

**Update the score cell renderer:**

```javascript
// In scoreCellRenderer function
function scoreCellRenderer(params) {
    const scoreData = params.value;
    if (!scoreData) {
        return '<span style="color: #999;">-</span>';
    }

    const value = scoreData.value;
    const complete = scoreData.complete;

    if (value === 'X' || value === null || value === '') {
        return '<span style="color: #999;">X</span>';
    }

    // Get benchmark stats (min/max)
    const benchmarkId = params.colDef.field;
    const stats = window.benchmarkStats && window.benchmarkStats[benchmarkId];

    if (!stats) {
        // Fallback if stats not available
        return `<span>${value}</span>`;
    }

    // Get root parent for color palette selection
    const rootParent = params.colDef.context?.rootParent || null;

    // Use existing color-utils.js function
    const colorCss = window.LeaderboardColorUtils.calculateRepresentativeColor(
        parseFloat(value),
        stats.min,
        stats.max,
        rootParent
    );

    // Apply styling (colorCss format: "background-color: rgb(...); background-color: rgba(...);")
    const displayValue = complete ? value : `${value}*`;

    return `<span style="${colorCss} padding: 4px 8px; border-radius: 3px;">${displayValue}</span>`;
}
```

### 3. API Versioning (Backward Compatibility)

**Add version parameter to the API endpoint:**

```python
# In benchmarks/views/leaderboard.py

@cache_get_context(timeout=7 *24 * 60 * 60, key_prefix="leaderboard", use_compression=True)
def get_ag_grid_context(user=None, domain="vision", benchmark_filter=None, model_filter=None,
                        show_public=False, force_user_cache=False, is_profile_view=False,
                        api_version='v2'):  # NEW PARAMETER
    """
    Get processed context data for AG Grid leaderboard.

    Args:
        api_version: 'v1' (legacy, includes color/raw/error) or 'v2' (optimized)
    """
    # ... existing code ...

    # Build score object based on API version
    if api_version == 'v1':
        # Legacy format (for backward compatibility during transition)
        rd[vid] = {
            'value': score.get('score_ceiled', 'X'),
            'raw': score.get('score_raw'),
            'error': score.get('error'),
            'color': score.get('color'),
            'complete': score.get('is_complete', True),
            'timestamp': score.get('end_timestamp')
        }
    else:  # v2 (default)
        # Optimized format
        rd[vid] = {
            'value': score.get('score_ceiled', 'X'),
            'complete': score.get('is_complete', True),
            'timestamp': score.get('end_timestamp')
        }
```

**Update view to pass version:**

```python
def ag_grid_leaderboard_content(request, domain: str):
    # ... existing code ...

    # Allow clients to request legacy format during transition
    api_version = request.GET.get('api_version', 'v2')

    context = get_ag_grid_context(
        user=user,
        domain=domain,
        show_public=show_public,
        force_user_cache=force_user_cache,
        is_profile_view=user_view,
        api_version=api_version  # NEW
    )
```

---

## Testing Plan

### 1. Local Testing

```bash
# 1. Apply changes
git checkout -b optimize/payload-reduction

# 2. Test locally
DEBUG=True python manage.py runserver

# 3. Open http://localhost:8000/vision/leaderboard
# 4. Verify:
#    - Scores display correctly
#    - Colors match previous appearance
#    - Sorting works
#    - Filtering works
#    - No console errors
```

### 2. Payload Verification

```bash
# Run audit before changes
python manage.py audit_payload vision > before.txt

# Apply changes
# ... make code changes ...

# Clear cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()

# Run audit after changes
python manage.py audit_payload vision > after.txt

# Compare
diff before.txt after.txt
```

**Expected results:**
- Payload: 14.28 MB → 4-5 MB
- Models: 493 (same)
- Execution time: Similar or slightly faster

### 3. Visual Regression Testing

**Checklist:**
- [ ] Score cells have colors (not all white)
- [ ] Colors match previous gradient (red → yellow → green)
- [ ] Missing scores show as gray/empty
- [ ] Incomplete scores show asterisk (*)
- [ ] Sorting by scores works correctly
- [ ] Column expansion works
- [ ] Filters work (model metadata, benchmark metadata)
- [ ] Timestamp filter works (if enabled)

### 4. Performance Testing

```bash
# Time the function execution
python manage.py shell
>>> from benchmarks.views.leaderboard import get_ag_grid_context
>>> import time
>>>
>>> start = time.time()
>>> context = get_ag_grid_context(domain='vision', show_public=True, api_version='v2')
>>> print(f"Execution: {time.time() - start:.2f}s")
>>>
>>> import sys, json
>>> payload_size = sys.getsizeof(context['row_data']) / 1024 / 1024
>>> print(f"Payload: {payload_size:.2f} MB")
```

---

## Rollback Plan

If issues arise after deployment:

### Option 1: Use Legacy API Version
```javascript
// In frontend, temporarily request v1 format
fetch('/vision/leaderboard/content?api_version=v1')
```

### Option 2: Git Revert
```bash
git revert <commit-hash>
git push
```

### Option 3: Feature Flag
Add to settings.py:
```python
ENABLE_PAYLOAD_OPTIMIZATION = os.getenv('ENABLE_PAYLOAD_OPTIMIZATION', 'false') == 'true'
```

Then in leaderboard.py:
```python
api_version = 'v2' if settings.ENABLE_PAYLOAD_OPTIMIZATION else 'v1'
```

---

## Deployment Strategy

### Phase 1: Dev Environment (Week 1)
1. Apply changes to dev branch
2. Deploy to dev environment
3. Test thoroughly
4. Monitor for issues

### Phase 2: Staging (Week 2)
1. Merge to staging branch
2. Deploy to staging
3. Run full test suite
4. Performance testing with realistic load

### Phase 3: Production (Week 3)
1. Deploy during off-peak hours
2. Monitor metrics closely:
   - Payload size (should be ~4-5 MB)
   - Response time
   - Error rate
   - Cache hit rate
3. Have rollback plan ready
4. Clear Redis cache after deployment

---

## Success Criteria

- [ ] Payload reduced from 14.28 MB to < 6 MB
- [ ] No visual regressions (colors look the same)
- [ ] No functional regressions (sorting, filtering work)
- [ ] No performance degradation
- [ ] No errors in browser console
- [ ] No errors in server logs

---

## Estimated Impact

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Payload Size | 14.28 MB | 4-5 MB | 65-70% |
| Network Transfer | ~14 MB | ~4-5 MB | 65-70% |
| Parse Time | ~500ms | ~150ms | 70% |
| Memory Usage | High | Lower | Significant |

**Combined with database index:**
- Database query: 19s → 1-2s
- Total TTFB: 22s → 2-3s (cold cache)
- **Total improvement: 87-90%**

---

## Next Steps

1. **Review this plan** - Verify approach looks good
2. **Apply database index first** - Fix the 19s query
3. **Implement payload changes** - Apply code changes above
4. **Test locally** - Verify everything works
5. **Deploy to dev** - Validate with production-scale data
6. **Monitor metrics** - Ensure improvements are realized

---

**Status: READY FOR IMPLEMENTATION**
**Estimated effort: 1-2 days coding + testing**
