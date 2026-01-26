# Database Optimization Scripts

This directory contains SQL scripts for manual database optimization tasks.

## Scripts

### 001_add_fmc_index.sql

**Purpose:** Add index to `mv_final_model_context` to optimize leaderboard queries

**Problem:** Leaderboard query taking ~19 seconds due to missing index

**Solution:** Create partial index on (domain, public) columns

**Expected Impact:** 19s → 1-2s query time (90% reduction)

**Environment:** Run on dev first, then production

**Note:** Index is created but sequential scan may still be used for small datasets (<1000 rows)

### 002_optimize_scores_jsonb.sql

**Purpose:** Remove unnecessary fields from scores JSONB in materialized views

**Problem:** Each score object contains `color`, `error`, `score_raw`, `score_ceiled_raw` fields that bloat the JSONB and cause slow data transfer (17 seconds for ~700 MB)

**Solution:** Rebuild `mv_model_scores_json` and `mv_final_model_context` to exclude these fields, keeping only:
- `score_ceiled` (displayed value)
- `is_complete` (data availability flag)
- `end_timestamp` (for timestamp feature)
- `versioned_benchmark_identifier` (for lookups)

**Expected Impact:**
- Materialized view size: ~700 MB → ~150 MB (79% reduction)
- Data transfer time: 17s → 3-4s (76% faster)
- Total payload: 14.28 MB → 6.88 MB (52% reduction)

**Environment:** Run on dev first, then production

**Note:** Colors are now computed client-side using existing `color-utils.js`

## Usage

### Option 1: Django Migration (Recommended)

```bash
cd brain-score.web

# Apply migration (dev)
python manage.py migrate

# Verify
python manage.py audit_payload vision
```

### Option 2: Manual SQL Execution

```bash
# Connect to database
psql -h <db-host> -U <username> -d <database>

# Run the script
\i db_optimization_scripts/001_add_fmc_index.sql

# Or copy-paste commands from the file
```

### Option 3: Django Shell

```bash
python manage.py dbshell

# Then paste SQL commands
```

## Safety

All index creation uses `CONCURRENTLY` to avoid blocking table access during creation.

## Verification

After applying the index:

```bash
# Run payload audit to measure improvement
python manage.py audit_payload vision

# Run database diagnostics
python manage.py diagnose_db vision
```

Expected improvements:
- Database query: 19.25s → 1-2s
- Total TTFB: 22.9s → 2-3s

## Rollback

If issues occur, the index can be dropped:

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_fmc_domain_public;
```

## Migration Order

1. **Dev environment**: Test migration
2. **Staging**: Validate with production-like load
3. **Production**: Deploy during off-peak hours

## Questions?

See `PAYLOAD_REDUCTION_PLAN.md` for complete optimization strategy.
