# Leaderboard Diagnostic Commands

This directory contains Django management commands for diagnosing and profiling the Brain-Score leaderboard performance.

## Available Commands

| Command | Purpose | Use When |
|---------|---------|----------|
| **profile_leaderboard** | Profiles Python function execution time | Finding slow functions in view code |
| **audit_payload** | Analyzes JSON payload size and structure | Understanding what consumes bandwidth |

---

## 1. profile_leaderboard

**What it does:** Uses cProfile to identify which Python functions consume the most execution time in the leaderboard view.

### Usage

```bash
python manage.py profile_leaderboard [domain] [options]

# Examples:
python manage.py profile_leaderboard vision
python manage.py profile_leaderboard language --top 50
python manage.py profile_leaderboard vision --top 20 --output my_profile.txt
```

**Options:**
- `domain` - Which domain to profile: `vision` or `language` (default: vision)
- `--top N` - Number of top functions to display (default: 30)
- `--output FILE` - Output file for detailed results (default: leaderboard_profile.txt)

### Example Output

```
=== ENVIRONMENT CHECK ===
Database Host: ***.***.us-east-1.rds.amazonaws.com
Cache Backend: django.core.cache.backends.locmem.LocMemCache
✓ Using local memory cache (dev environment)

=== PROFILING get_ag_grid_context() ===
Running cProfile with domain='vision', show_public=True...

Total execution time: 4.235s

=== TOP 30 FUNCTIONS BY CUMULATIVE TIME ===
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.002    0.002    4.235    4.235 leaderboard.py:123(get_ag_grid_context)
        1    0.005    0.005    2.856    2.856 {method 'execute' of 'psycopg2.cursor'}
      493    0.234    0.000    0.876    0.002 leaderboard.py:287(serialize_model)
    64583    0.456    0.000    0.456    0.000 {built-in method builtins.str}
      493    0.123    0.000    0.389    0.001 json.py:179(dumps)
        1    0.089    0.089    0.298    0.298 leaderboard.py:156(build_benchmark_tree)
      200    0.045    0.000    0.187    0.001 leaderboard.py:201(build_column_defs)
     1500    0.098    0.000    0.098    0.000 {method 'append' of 'list' objects}

=== CONTEXT DATA ===
Models in row_data: 493
Columns: 200
row_data size: 6.89 MB
column_defs size: 0.12 MB
Total estimated payload: 7.40 MB

Detailed profiling results saved to: leaderboard_profile.txt
```

### How to Interpret

**Key metrics:**
- **ncalls** - Number of times the function was called
- **tottime** - Total time spent in the function itself (excluding subfunctions)
- **cumtime** - Cumulative time (including subfunctions) - **most important**
- **percall** - Average time per call

**What to look for:**

1. **High cumtime at the top** - These are your biggest bottlenecks
   ```
   cumtime  percall filename:lineno(function)
   2.856s   2.856s  {method 'execute' of 'psycopg2.cursor'}  ← DATABASE QUERY IS SLOW
   ```
   **Fix:** Optimize the SQL query, add indexes, or cache results

2. **High tottime with many calls** - Function called too frequently
   ```
   ncalls  tottime  cumtime  filename:lineno(function)
   64583   0.456s   0.456s   {built-in method builtins.str}  ← EXCESSIVE STRING CONVERSIONS
   ```
   **Fix:** Reduce calls, batch operations, or optimize the function

3. **Serialization overhead** - JSON encoding taking too long
   ```
   ncalls  tottime  cumtime  filename:lineno(function)
   493     0.123s   0.389s   json.py:179(dumps)  ← SERIALIZATION IS SLOW
   ```
   **Fix:** Reduce payload size, simplify data structures

**Common bottlenecks:**

| Symptom | Root Cause | Solution |
|---------|------------|----------|
| `psycopg2.cursor.execute` has high cumtime | Slow database query | Add indexes, optimize SQL, check EXPLAIN plan |
| `json.dumps` appears in top 10 | Large payload serialization | Remove unnecessary fields from payload |
| Many calls to string operations | Inefficient data processing | Use bulk operations, optimize loops |
| High time in template rendering | Complex template logic | Move logic to view, simplify template |

---

## 2. audit_payload

**What it does:** Analyzes the JSON payload sent to the browser, breaking down what consumes bandwidth and identifying optimization opportunities.

### Usage

```bash
python manage.py audit_payload [domain]

# Examples:
python manage.py audit_payload vision
python manage.py audit_payload language
```

**Options:**
- `domain` - Which domain to audit: `vision` or `language` (default: vision)

### Example Output

```
=== ENVIRONMENT CHECK ===
Database Host: ***.***.us-east-1.rds.amazonaws.com
Cache Backend: django.core.cache.backends.locmem.LocMemCache
✓ Using local memory cache (dev environment)

=== PROFILING DOMAIN: VISION ===

Context generation time: 4.123s

=== PAYLOAD SIZE BREAKDOWN ===

row_data:
  Size: 6.89 MB (7,223,456 bytes)
  Models: 493
  Fields per model: 206
    - Score fields: ~200
    - Base fields: 6 (id, rank, model, public, metadata, is_owner)
  Sample score object keys: ['score_ceiled', 'error', 'benchmark_type_id']
  Estimated score data size: ~6.45 MB

column_defs:
  Size: 0.12 MB (125,678 bytes)
  Columns: 200

metadata_maps:
  benchmarkStimuliMetaMap: 0.15 MB (157,824 bytes)
  benchmarkDataMetaMap: 0.08 MB (83,968 bytes)
  benchmarkMetricMetaMap: 0.05 MB (52,480 bytes)
  model_metadata_map: 0.24 MB (251,904 bytes)
  benchmark_bibtex_map: 0.06 MB (62,976 bytes)

TOTAL ESTIMATED PAYLOAD: 7.59 MB

=== OPTIMIZATION OPPORTUNITIES ===

Score object fields found:
  - score_ceiled: float
  - error: float
  - benchmark_type_id: int

Potential optimizations:
  2. [HIGH IMPACT] Move optional fields to on-demand API: error
     Estimated savings: ~30% of score data
  3. [MEDIUM IMPACT] Lazy-load metadata maps on demand
     Estimated savings: 0.58 MB

=== SUMMARY ===

Current payload: 7.59 MB
Target (Phase 1): < 10 MB
Reduction needed: 0.00 MB (0.0%)

Next steps:
  1. Profile with: python -m cProfile -o leaderboard.prof manage.py shell
  2. Implement payload reduction (remove color, move optional fields)
  3. Re-run this audit to measure improvements
```

### How to Interpret

**1. Payload Size Breakdown**

The payload has three main components:

```
row_data: 6.89 MB          ← MODEL SCORES (biggest component)
├─ 493 models
├─ ~200 score fields per model
└─ 3 keys per score object

column_defs: 0.12 MB       ← COLUMN DEFINITIONS (small)
└─ 200 columns with headers, formatters

metadata_maps: 0.58 MB     ← METADATA LOOKUPS (medium)
├─ benchmarkStimuliMetaMap
├─ model_metadata_map
└─ etc.
```

**What to optimize first:** Always start with the largest component (row_data).

**2. Understanding Score Object Structure**

```
Sample score object keys: ['score_ceiled', 'error', 'benchmark_type_id']
                          └─ 3 fields × 200 benchmarks × 493 models = ~296,400 values
```

**Each field has a cost:**
- `score_ceiled` (float) - **Essential** - The actual score value
- `error` (float) - **Optional** - Can be loaded on-demand for error bars
- `benchmark_type_id` (int) - **Essential** - Links score to benchmark

**3. Optimization Impact Estimates**

The command suggests optimizations with impact ratings:

| Priority | Optimization | Savings | Trade-off |
|----------|--------------|---------|-----------|
| HIGH IMPACT | Move `error` to on-demand API | ~30% of score data (~2 MB) | Error bars load on hover instead of immediately |
| MEDIUM IMPACT | Lazy-load metadata maps | ~0.6 MB | Metadata loads when user expands tree nodes |
| LOW IMPACT | Compress column_defs | ~50 KB | Minimal gain, not worth complexity |

**4. Target Analysis**

```
Current payload: 7.59 MB
Target (Phase 1): < 10 MB    ← Already achieved!
Reduction needed: 0.00 MB
```

If you're **above target**, focus on HIGH IMPACT optimizations first.

**5. When Payload is Too Large**

If payload exceeds target:

```
Current payload: 14.28 MB
Target (Phase 1): < 10 MB
Reduction needed: 4.28 MB (30.0%)
```

**Action plan:**
1. Remove pre-computed colors (if present) - saves ~50% of score data
2. Move `error` field to on-demand API - saves ~30% more
3. Lazy-load metadata maps - saves ~0.5-1 MB

---

## Typical Diagnostic Workflow

### Scenario 1: Page is Loading Slowly

**Step 1: Profile to find bottleneck**
```bash
python manage.py profile_leaderboard vision
```

**Look for:**
- Is database query slow? (psycopg2.cursor.execute > 2s)
- Is serialization slow? (json.dumps in top 10)
- Is Python processing slow? (high cumtime in view functions)

**Step 2: Audit payload if serialization is slow**
```bash
python manage.py audit_payload vision
```

**Look for:**
- Is payload > 10 MB?
- Are there redundant fields in score objects?
- Can metadata be lazy-loaded?

### Scenario 2: Making Optimizations

**Before changes:**
```bash
python manage.py profile_leaderboard vision > before_profile.txt
python manage.py audit_payload vision > before_payload.txt
```

**Make changes** (e.g., remove color field from scores)

**After changes:**
```bash
python manage.py profile_leaderboard vision > after_profile.txt
python manage.py audit_payload vision > after_payload.txt

# Compare
diff before_payload.txt after_payload.txt
```

**Expected improvements:**
```diff
- row_data size: 12.45 MB
+ row_data size: 6.89 MB

- TOTAL ESTIMATED PAYLOAD: 13.22 MB
+ TOTAL ESTIMATED PAYLOAD: 7.59 MB
```

---

## Performance Targets

### Phase 1 (Current - Completed)
- ✅ Database query: < 3s (achieved: 2.4s)
- ✅ Payload size: < 10 MB (achieved: 6.89 MB)
- ✅ Total execution time: < 5s (achieved: ~4s)

### Phase 2 (Planned)
- Database query: < 1s
- Payload size: < 5 MB
- Total execution time: < 2s

### Phase 3 (Future)
- Database query: < 500ms
- Payload size: < 3 MB
- Total execution time: < 1s

---

## Tips for Effective Profiling

### Do's
- ✅ Always run in DEBUG=True mode to see query details
- ✅ Use local environment with dev database (production parity)
- ✅ Run multiple times and average results (variance can be 10-20%)
- ✅ Compare before/after on the same machine
- ✅ Profile during typical load (not empty cache)

### Don'ts
- ❌ Never run against production database
- ❌ Don't profile with cold cache (results won't be representative)
- ❌ Don't compare results across different machines
- ❌ Don't optimize without profiling first (premature optimization)

### Reading cProfile Output

```
ncalls  tottime  percall  cumtime  percall filename:lineno(function)
  493    0.234    0.000    0.876    0.002 serialize_model
   ↑      ↑        ↑        ↑        ↑
   │      │        │        │        └─ Average cumulative time per call
   │      │        │        └────────── Total time including subfunctions (KEY METRIC)
   │      │        └─────────────────── Average time per call (self only)
   │      └──────────────────────────── Time in function itself (excluding subfunctions)
   └─────────────────────────────────── Number of times called
```

**Focus on cumtime** - it tells you where the total time is going.

---

## Interpreting Results: Quick Reference

### Database is the Bottleneck
```
cumtime: 2.5s → psycopg2.cursor.execute
```
**Fix:** Optimize SQL query, add indexes, or implement caching

### Payload is Too Large
```
row_data size: 14.28 MB
TOTAL ESTIMATED PAYLOAD: 15.50 MB
```
**Fix:** Remove unnecessary fields, move data to on-demand APIs

### Python Processing is Slow
```
cumtime: 1.2s → serialize_model (493 calls)
```
**Fix:** Optimize serialization logic, reduce per-model processing

### Many Small Operations
```
ncalls: 64,583 → string conversions
tottime: 0.45s
```
**Fix:** Batch operations, use list comprehensions instead of loops

---

## Troubleshooting

### "ERROR: Cannot profile against production database"

**Cause:** Your database connection is pointing to production.

**Fix:**
```bash
# Check your database configuration
echo $DJANGO_ENV
# Should be "dev" or "local", not "prod"

# Or check Django settings
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['HOST'])"
```

### Payload size seems wrong

**Cause:** `sys.getsizeof()` measures Python object size, not actual JSON size.

**Reality check:**
```bash
# Get actual JSON size
python manage.py shell
>>> from benchmarks.views.leaderboard import get_ag_grid_context
>>> import json
>>> context = get_ag_grid_context(user=None, domain='vision', show_public=True)
>>> len(context['row_data']) / 1024 / 1024
6.89  # Actual MB
```


