"""
Management command to audit leaderboard payload size and structure.

Usage:
    python manage.py audit_payload [domain]
    python manage.py audit_payload vision
    python manage.py audit_payload language
"""

import json
import sys
import time
from django.core.management.base import BaseCommand
from django.conf import settings

from benchmarks.views.leaderboard import get_ag_grid_context


class Command(BaseCommand):
    help = 'Audit leaderboard payload size and structure'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            nargs='?',
            type=str,
            default='vision',
            help='Domain to audit (vision or language, default: vision)'
        )

    def handle(self, *args, **options):
        domain = options['domain']

        # Safety check: ensure not running against production
        db_host = settings.DATABASES['default']['HOST']
        cache_backend = settings.CACHES['default']['BACKEND']

        self.stdout.write(self.style.WARNING('=== ENVIRONMENT CHECK ==='))
        self.stdout.write(f"Database Host: {db_host}")
        self.stdout.write(f"Cache Backend: {cache_backend}")

        if 'prod' in db_host.lower() or 'production' in db_host.lower():
            self.stderr.write(self.style.ERROR('ERROR: Cannot run audit against production database'))
            return

        if 'LocMemCache' in cache_backend:
            self.stdout.write(self.style.SUCCESS('✓ Using local memory cache (dev environment)'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Using Redis cache (staging/prod)'))

        self.stdout.write('')

        # Run the profiling
        self.stdout.write(self.style.SUCCESS(f'\n=== PROFILING DOMAIN: {domain.upper()} ===\n'))

        # Time the context generation
        start_time = time.perf_counter()
        context = get_ag_grid_context(user=None, domain=domain, show_public=True)
        elapsed_time = time.perf_counter() - start_time

        self.stdout.write(f"Context generation time: {elapsed_time:.3f}s")
        self.stdout.write('')

        # Parse JSON strings back to objects for analysis
        row_data = json.loads(context['row_data'])
        column_defs = json.loads(context['column_defs'])
        benchmark_tree = json.loads(context['benchmark_tree'])
        filter_options = json.loads(context['filter_options'])

        # Analyze sizes
        self.stdout.write(self.style.SUCCESS('=== PAYLOAD SIZE BREAKDOWN ===\n'))

        results = {
            'row_data': {
                'size_bytes': sys.getsizeof(context['row_data']),
                'size_mb': sys.getsizeof(context['row_data']) / 1024 / 1024,
                'num_models': len(row_data),
            },
            'column_defs': {
                'size_bytes': sys.getsizeof(context['column_defs']),
                'size_mb': sys.getsizeof(context['column_defs']) / 1024 / 1024,
                'num_columns': len(column_defs),
            },
            'metadata_maps': {},
            'total_size_mb': 0,
        }

        # Print row_data info
        self.stdout.write(f"row_data:")
        self.stdout.write(f"  Size: {results['row_data']['size_mb']:.2f} MB ({results['row_data']['size_bytes']:,} bytes)")
        self.stdout.write(f"  Models: {results['row_data']['num_models']}")

        # Analyze structure of a single model
        if row_data:
            sample_model = row_data[0]
            total_fields = len(sample_model.keys())
            score_fields = total_fields - 5  # subtract: id, rank, model, public, metadata, is_owner

            self.stdout.write(f"  Fields per model: {total_fields}")
            self.stdout.write(f"    - Score fields: ~{score_fields}")
            self.stdout.write(f"    - Base fields: 6 (id, rank, model, public, metadata, is_owner)")

            # Analyze a sample score object
            score_keys = [k for k in sample_model.keys() if k not in ['id', 'rank', 'model', 'public', 'metadata', 'is_owner']]
            if score_keys:
                sample_score = sample_model[score_keys[0]]
                if isinstance(sample_score, dict):
                    self.stdout.write(f"  Sample score object keys: {list(sample_score.keys())}")
                    score_size = sys.getsizeof(json.dumps(sample_score))
                    estimated_total = score_size * score_fields * results['row_data']['num_models']
                    self.stdout.write(f"  Estimated score data size: ~{estimated_total / 1024 / 1024:.2f} MB")

        self.stdout.write('')

        # Print column_defs info
        self.stdout.write(f"column_defs:")
        self.stdout.write(f"  Size: {results['column_defs']['size_mb']:.2f} MB ({results['column_defs']['size_bytes']:,} bytes)")
        self.stdout.write(f"  Columns: {results['column_defs']['num_columns']}")
        self.stdout.write('')

        # Analyze metadata maps
        self.stdout.write(f"metadata_maps:")
        metadata_keys = [
            'benchmarkStimuliMetaMap',
            'benchmarkDataMetaMap',
            'benchmarkMetricMetaMap',
            'model_metadata_map',
            'benchmark_bibtex_map'
        ]

        for key in metadata_keys:
            if key in context:
                size = sys.getsizeof(context[key])
                size_mb = size / 1024 / 1024
                results['metadata_maps'][key] = {
                    'size_bytes': size,
                    'size_mb': size_mb,
                }
                results['total_size_mb'] += size_mb
                self.stdout.write(f"  {key}: {size_mb:.2f} MB ({size:,} bytes)")

        self.stdout.write('')

        # Calculate total
        results['total_size_mb'] += results['row_data']['size_mb']
        results['total_size_mb'] += results['column_defs']['size_mb']

        self.stdout.write(f"TOTAL ESTIMATED PAYLOAD: {results['total_size_mb']:.2f} MB")
        self.stdout.write('')

        # Identify optimization opportunities
        self.stdout.write(self.style.WARNING('=== OPTIMIZATION OPPORTUNITIES ===\n'))

        # Check for redundant score fields
        if row_data:
            sample_model = row_data[0]
            score_keys = [k for k in sample_model.keys() if k not in ['id', 'rank', 'model', 'public', 'metadata', 'is_owner']]
            if score_keys:
                sample_score = sample_model[score_keys[0]]
                if isinstance(sample_score, dict):
                    self.stdout.write("Score object fields found:")
                    for field in sample_score.keys():
                        self.stdout.write(f"  - {field}: {type(sample_score[field]).__name__}")

                    self.stdout.write('')
                    self.stdout.write("Potential optimizations:")

                    # Check for pre-computed colors
                    if 'color' in sample_score:
                        self.stdout.write("  1. [HIGH IMPACT] Remove 'color' field - compute client-side from min/max")
                        self.stdout.write("     Estimated savings: ~50% of score data")

                    # Check for optional fields
                    optional_fields = ['raw', 'error', 'timestamp']
                    present_optional = [f for f in optional_fields if f in sample_score]
                    if present_optional:
                        self.stdout.write(f"  2. [HIGH IMPACT] Move optional fields to on-demand API: {', '.join(present_optional)}")
                        self.stdout.write("     Estimated savings: ~30% of score data")

                    # Check metadata maps
                    if results['metadata_maps']:
                        self.stdout.write("  3. [MEDIUM IMPACT] Lazy-load metadata maps on demand")
                        total_meta_mb = sum(m['size_mb'] for m in results['metadata_maps'].values())
                        self.stdout.write(f"     Estimated savings: {total_meta_mb:.2f} MB")

        self.stdout.write('')

        # Summary
        self.stdout.write(self.style.SUCCESS('=== SUMMARY ===\n'))
        self.stdout.write(f"Current payload: {results['total_size_mb']:.2f} MB")
        self.stdout.write(f"Target (Phase 1): < 10 MB")
        self.stdout.write(f"Reduction needed: {results['total_size_mb'] - 10:.2f} MB ({((results['total_size_mb'] - 10) / results['total_size_mb'] * 100):.1f}%)")
        self.stdout.write('')
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Profile with: python -m cProfile -o leaderboard.prof manage.py shell")
        self.stdout.write("  2. Implement payload reduction (remove color, move optional fields)")
        self.stdout.write("  3. Re-run this audit to measure improvements")
