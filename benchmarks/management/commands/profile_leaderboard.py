"""
Management command to profile leaderboard performance with cProfile.

Usage:
    python manage.py profile_leaderboard [domain]
    python manage.py profile_leaderboard vision
    python manage.py profile_leaderboard language

This command uses cProfile to identify Python-level performance bottlenecks
in the leaderboard view function. It shows which functions consume the most time.
"""

import cProfile
import pstats
import io
import time
import json
import sys
from django.core.management.base import BaseCommand
from django.conf import settings

from benchmarks.views.leaderboard import get_ag_grid_context


class Command(BaseCommand):
    help = 'Profile leaderboard performance using cProfile'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            nargs='?',
            type=str,
            default='vision',
            help='Domain to profile (vision or language, default: vision)'
        )
        parser.add_argument(
            '--top',
            type=int,
            default=30,
            help='Number of top functions to display (default: 30)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='leaderboard_profile.txt',
            help='Output file for detailed profiling results'
        )

    def handle(self, *args, **options):
        domain = options['domain']
        top_n = options['top']
        output_file = options['output']

        # Environment check
        self.stdout.write(self.style.WARNING('=== ENVIRONMENT CHECK ==='))
        db_host = settings.DATABASES['default']['HOST']
        cache_backend = settings.CACHES['default']['BACKEND']

        self.stdout.write(f"Database Host: {db_host}")
        self.stdout.write(f"Cache Backend: {cache_backend}")

        if 'prod' in db_host.lower() or 'production' in db_host.lower():
            self.stderr.write(self.style.ERROR('ERROR: Cannot profile against production database'))
            return

        if 'LocMemCache' in cache_backend:
            self.stdout.write(self.style.SUCCESS('✓ Using local memory cache (dev environment)'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Using Redis cache'))

        self.stdout.write('')

        # Profile the function
        self.stdout.write(self.style.SUCCESS('=== PROFILING get_ag_grid_context() ==='))
        self.stdout.write(f"Running cProfile with domain='{domain}', show_public=True...")
        self.stdout.write('')

        profiler = cProfile.Profile()
        profiler.enable()

        # Run the function
        start_time = time.perf_counter()
        context = get_ag_grid_context(user=None, domain=domain, show_public=True)
        elapsed_time = time.perf_counter() - start_time

        profiler.disable()

        # Print timing
        self.stdout.write(f"Total execution time: {elapsed_time:.3f}s")
        self.stdout.write('')

        # Generate stats
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')

        self.stdout.write(self.style.SUCCESS(f'=== TOP {top_n} FUNCTIONS BY CUMULATIVE TIME ==='))
        ps.print_stats(top_n)
        self.stdout.write(s.getvalue())

        # Print context size
        self.stdout.write(self.style.SUCCESS('=== CONTEXT DATA ==='))

        row_data = json.loads(context['row_data'])
        column_defs = json.loads(context['column_defs'])

        self.stdout.write(f"Models in row_data: {len(row_data)}")
        self.stdout.write(f"Columns: {len(column_defs)}")
        self.stdout.write(f"row_data size: {sys.getsizeof(context['row_data']) / 1024 / 1024:.2f} MB")
        self.stdout.write(f"column_defs size: {sys.getsizeof(context['column_defs']) / 1024 / 1024:.2f} MB")

        # Calculate total context size
        total_size = 0
        for key, value in context.items():
            if isinstance(value, str):
                total_size += sys.getsizeof(value)

        self.stdout.write(f"Total estimated payload: {total_size / 1024 / 1024:.2f} MB")
        self.stdout.write('')

        # Save detailed stats to file
        with open(output_file, 'w') as f:
            ps = pstats.Stats(profiler, stream=f).sort_stats('cumulative')
            ps.print_stats()

        self.stdout.write(self.style.SUCCESS(f'Detailed profiling results saved to: {output_file}'))
        self.stdout.write('')

        # Next steps
        self.stdout.write(self.style.SUCCESS('=== NEXT STEPS ==='))
        self.stdout.write('1. Review top time-consuming functions above')
        self.stdout.write('2. Run: python manage.py audit_payload')
        self.stdout.write('3. Run: python manage.py diagnose_db')
        self.stdout.write('4. Consider optimizations based on findings')
        self.stdout.write('')
