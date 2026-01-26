# Leaderboard Performance Profiling

This document provides step-by-step instructions for profiling the brain-score.org leaderboard performance.

## Environment Safety

**CRITICAL:** All profiling is done locally, connecting to the **dev database only**.

### Quick Environment Check

```bash
# Verify you're in the right environment
conda activate web-2026
cd brain-score.web

# Check your database connection (should show dev, NOT prod)
python manage.py shell
>>> from django.conf import settings
>>> print(settings.DATABASES['default']['HOST'])  # Should be dev host
>>> exit()
```

## Profiling Tools

### 1. Payload Audit (Recommended First Step)

Analyzes the JSON payload structure and identifies optimization opportunities.

```bash
# Activate environment
conda activate web-2026
cd brain-score.web

# Run audit for vision domain
DEBUG=True python manage.py audit_payload vision

# Or for language domain
DEBUG=True python manage.py audit_payload language
```

**Output includes:**
- Payload size breakdown (row_data, column_defs, metadata maps)
- Number of models and benchmarks
- Sample score object structure
- Optimization recommendations
- Estimated savings from each optimization

**Time:** ~5-30 seconds depending on database connection speed

### 2. Performance Profiling (cProfile)

Identifies bottlenecks in the `get_ag_grid_context()` function.

```bash
# Activate environment
conda activate web-2026
cd brain-score.web

# Run profiling script
DEBUG=True python profile_leaderboard.py
```

**Output includes:**
- Total execution time
- Top 30 functions by cumulative time
- Context data sizes
- Detailed profile saved to `leaderboard_profile.txt`

**Time:** ~10-60 seconds depending on database connection speed

### 3. Django Shell Manual Profiling

For interactive profiling and experimentation:

```bash
# Start Django shell
conda activate web-2026
cd brain-score.web
DEBUG=True python manage.py shell
```

```python
# Inside shell - import profiling tools
import cProfile
import pstats
import io
import time
import json
import sys
from benchmarks.views.leaderboard import get_ag_grid_context

# Time the function
start = time.perf_counter()
context = get_ag_grid_context(user=None, domain='vision', show_public=True)
elapsed = time.perf_counter() - start
print(f"Execution time: {elapsed:.3f}s")

# Check sizes
row_data = json.loads(context['row_data'])
print(f"Models: {len(row_data)}")
print(f"Payload size: {sys.getsizeof(context['row_data']) / 1024 / 1024:.2f} MB")

# Profile specific section
profiler = cProfile.Profile()
profiler.enable()
context = get_ag_grid_context(user=None, domain='vision', show_public=True)
profiler.disable()

# Print stats
s = io.StringIO()
ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
ps.print_stats(20)
print(s.getvalue())
```

## Expected Baseline Results

Based on the optimization plan, here's what to expect:

### Current State (Before Optimization)
- **Payload size:** ~30MB (compressed), ~100MB (raw JSON)
- **Execution time (cold cache):** 3-6 seconds
- **Execution time (warm cache):** 200-800ms
- **Models:** ~3,000
- **Benchmarks:** ~200
- **Total data points:** ~600,000 (3000 × 200)

### After Phase 1 Optimizations
- **Target payload:** 8-10MB
- **Target execution time:** 1-2 seconds (cold cache)
- **Improvements:**
  - Remove pre-computed colors: ~30% reduction
  - Remove optional fields: ~30% reduction
  - Lazy-load metadata: ~7MB reduction

## Troubleshooting

### "Cannot run audit against production database"
This safety check prevents accidental profiling of production. Solutions:
1. Check `DJANGO_ENV` is not set to production
2. Verify AWS credentials point to dev secrets
3. Ensure `DB_CRED` environment variable points to dev

### "ModuleNotFoundError: No module named 'benchmarks'"
You're not in the right directory. Run:
```bash
cd /Users/kartik/Brain-Score\ 2026/brain-score.web
```

### Slow execution (>60 seconds)
This could mean:
- Network latency to database
- Database is under load
- Missing indexes
- Cold database cache

Try running a second time - database caching should speed things up.

### LocMemCache warnings
If you see "Using local memory cache" - this is expected for local development. Redis profiling requires SSH tunnel setup (see MASTER-OPTIMIZATION-PLAN.md for details).

## Next Steps After Profiling

1. **Review results** - Identify the largest payload components
2. **Check optimization plan** - See `MASTER-OPTIMIZATION-PLAN.md` in `future_project_plans/brain-score.web/`
3. **Start with quick wins:**
   - Remove color field from scores
   - Move optional fields (raw, error, timestamp) to separate API
   - Lazy-load metadata maps
4. **Re-profile** - Measure improvements after changes

## Files Created

- `benchmarks/management/commands/audit_payload.py` - Payload audit command
- `profile_leaderboard.py` - cProfile wrapper script
- `PROFILING.md` - This guide (you are here)

## Related Documentation

- Master optimization plan: `../future_project_plans/brain-score.web/MASTER-OPTIMIZATION-PLAN.md`
- Quick reference: `../future_project_plans/brain-score.web/QUICK-REFERENCE.md`
- Environment safety guide: See "Environment Safety Strategy" section in master plan

## Support

For issues or questions:
- Check the optimization plan documents first
- Review Django logs: `./django.log`
- Create GitHub issue with profiling output attached
