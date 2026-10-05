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

### Interpreting the output

The command reports context generation time and estimated serialized sizes for
`row_data`, `column_defs` and `benchmark_bibtex_map`. Run it against the intended
environment; model counts and benchmark coverage change over time.

`row_data` contains model identities and scores and is usually the largest
component. Profile database queries and serialization before choosing an
optimization. `column_defs` describes the grid columns, and
`benchmark_bibtex_map` supports citation export.

Leaderboard downloads contain only `leaderboard.csv`. Legacy model/stimuli/data/
metric export maps and the `plugin-info.csv` sidecar are no longer included in
the browser payload. Metadata needed for filtering and tooltips remains available.

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


