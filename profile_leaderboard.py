#!/usr/bin/env python
"""
Profiling script for leaderboard performance analysis.

Usage:
    conda activate web-2026
    cd brain-score.web
    DEBUG=True python profile_leaderboard.py

This script profiles the get_ag_grid_context function and outputs detailed timing information.
"""

import cProfile
import pstats
import io
import time
import django
import os
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
os.environ['DEBUG'] = 'True'
django.setup()

from django.conf import settings
from benchmarks.views.leaderboard import get_ag_grid_context

def main():
    # Environment check
    print("=" * 70)
    print("ENVIRONMENT CHECK")
    print("=" * 70)
    db_host = settings.DATABASES['default']['HOST']
    cache_backend = settings.CACHES['default']['BACKEND']

    print(f"Database Host: {db_host}")
    print(f"Cache Backend: {cache_backend}")

    if 'prod' in db_host.lower() or 'production' in db_host.lower():
        print("\n❌ ERROR: Attempting to profile against PRODUCTION database!")
        print("Set DJANGO_ENV or DB_CRED to point to dev/test database.")
        sys.exit(1)

    if 'LocMemCache' in cache_backend:
        print("✓ Using local memory cache (dev environment)")
    else:
        print("⚠  Using Redis cache")

    print()

    # Profile the function
    print("=" * 70)
    print("PROFILING get_ag_grid_context()")
    print("=" * 70)
    print("Running cProfile with domain='vision', show_public=True...")
    print()

    profiler = cProfile.Profile()
    profiler.enable()

    # Run the function
    start_time = time.perf_counter()
    context = get_ag_grid_context(user=None, domain='vision', show_public=True)
    elapsed_time = time.perf_counter() - start_time

    profiler.disable()

    # Print timing
    print(f"Total execution time: {elapsed_time:.3f}s")
    print()

    # Generate stats
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')

    print("=" * 70)
    print("TOP 30 FUNCTIONS BY CUMULATIVE TIME")
    print("=" * 70)
    ps.print_stats(30)
    print(s.getvalue())

    # Print context size
    print("=" * 70)
    print("CONTEXT DATA")
    print("=" * 70)

    import json
    row_data = json.loads(context['row_data'])
    column_defs = json.loads(context['column_defs'])

    print(f"Models in row_data: {len(row_data)}")
    print(f"Columns: {len(column_defs)}")
    print(f"row_data size: {sys.getsizeof(context['row_data']) / 1024 / 1024:.2f} MB")
    print(f"column_defs size: {sys.getsizeof(context['column_defs']) / 1024 / 1024:.2f} MB")

    # Calculate total context size
    total_size = 0
    for key, value in context.items():
        if isinstance(value, str):
            total_size += sys.getsizeof(value)

    print(f"Total estimated payload: {total_size / 1024 / 1024:.2f} MB")
    print()

    # Save detailed stats to file
    output_file = 'leaderboard_profile.txt'
    with open(output_file, 'w') as f:
        ps = pstats.Stats(profiler, stream=f).sort_stats('cumulative')
        ps.print_stats()

    print(f"Detailed profiling results saved to: {output_file}")
    print()

    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("1. Review top time-consuming functions above")
    print("2. Run: python manage.py audit_payload")
    print("3. Check database query performance with django-silk or pg_stat_statements")
    print("4. Consider optimizations:")
    print("   - Remove pre-computed color strings")
    print("   - Move optional score fields to on-demand API")
    print("   - Lazy-load metadata maps")
    print()


if __name__ == '__main__':
    main()
