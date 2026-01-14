"""
Management command to generate pre-computed wayback snapshots.

These snapshots are static JSON files that can be served via CDN for
instant wayback machine loading without any server round-trips.

Usage:
    # Generate monthly snapshots for vision domain (last 3 years)
    python manage.py generate_wayback_snapshots vision

    # Generate weekly snapshots for a specific date range
    python manage.py generate_wayback_snapshots vision --start-date 2023-01-01 --end-date 2024-01-01 --interval weekly

    # Generate a single snapshot for a specific date
    python manage.py generate_wayback_snapshots vision --date 2023-06-15

    # List available snapshots
    python manage.py generate_wayback_snapshots vision --list

    # Clean old snapshots
    python manage.py generate_wayback_snapshots vision --clean --keep-count 36
"""

import json
import gzip
import os
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = 'Generate pre-computed wayback snapshots for fast historical leaderboard loading'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            type=str,
            choices=['vision', 'language'],
            help='Domain to generate snapshots for (vision or language)'
        )
        parser.add_argument(
            '--date',
            type=str,
            help='Generate snapshot for a specific date (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for range generation (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for range generation (YYYY-MM-DD)'
        )
        parser.add_argument(
            '--interval',
            type=str,
            choices=['daily', 'weekly', 'monthly'],
            default='monthly',
            help='Interval for snapshot generation (default: monthly)'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List available snapshots'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean old snapshots'
        )
        parser.add_argument(
            '--keep-count',
            type=int,
            default=36,
            help='Number of recent snapshots to keep when cleaning (default: 36)'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            help='Custom output directory for snapshots'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            default=True,
            help='Compress snapshots with gzip (default: True)'
        )
        parser.add_argument(
            '--no-compress',
            action='store_false',
            dest='compress',
            help='Disable gzip compression'
        )

    def handle(self, *args, **options):
        domain = options['domain']

        # Determine output directory
        if options['output_dir']:
            output_dir = Path(options['output_dir'])
        else:
            output_dir = Path(settings.BASE_DIR) / 'static' / 'benchmarks' / 'snapshots' / domain

        output_dir.mkdir(parents=True, exist_ok=True)

        if options['list']:
            self.list_snapshots(output_dir)
            return

        if options['clean']:
            self.clean_snapshots(output_dir, options['keep_count'])
            return

        if options['date']:
            # Single date snapshot
            target_date = datetime.strptime(options['date'], '%Y-%m-%d')
            self.generate_snapshot(domain, target_date, output_dir, options['compress'])
        else:
            # Range of snapshots
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d') if options['end_date'] else datetime.now()

            if options['start_date']:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
            else:
                # Default: 3 years back
                start_date = end_date - timedelta(days=3*365)

            self.generate_range_snapshots(
                domain, start_date, end_date,
                options['interval'], output_dir, options['compress']
            )

        # Generate manifest
        self.generate_manifest(domain, output_dir)

    def get_snapshot_data(self, domain, target_date):
        """
        Generate snapshot data for a specific date using version-aware SQL functions.

        This uses the mv_version_timeline materialized view to determine which
        benchmark version was active at the target date, ensuring scores from
        the historically-correct version are shown (not the current version).

        For example, if MajajHong2015.V4-pls was on version 3 in 2024-01-01,
        we show _v3 scores, not _v4 scores.
        """
        from benchmarks.views.leaderboard import json_serializable
        from benchmarks.views.index import get_context
        from benchmarks.models import FinalBenchmarkContext
        from colour import Color
        import numpy as np

        # Color scale for score visualization
        colors_redgreen = list(Color('red').range_to(Color('#1BA74D'), 101))
        a, b = 0.2270617, 1.321928
        colors_redgreen = [colors_redgreen[int(a * np.power(i, b))] for i in range(len(colors_redgreen))]

        def get_score_color(score_val):
            """Generate color for a score value (0-1 range)."""
            if score_val is None or score_val == 'X':
                return '#E0E1E2'
            try:
                score_float = float(score_val)
                idx = min(100, max(0, int(score_float * 100)))
                color = colors_redgreen[idx]
                return f"background-color: {color.hex}; background-color: rgba({int(color.red*255)}, {int(color.green*255)}, {int(color.blue*255)}, {0.5 + score_float * 0.5});"
            except (ValueError, TypeError):
                return '#E0E1E2'

        # Step 1: Get active benchmark versions at target date using SQL function
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT benchmark_type_id, active_version, instance_id
                FROM get_benchmark_version_at_timestamp(%s)
            """, [target_date])
            columns = [col[0] for col in cursor.description]
            active_versions = {
                row[0]: {'version': row[1], 'instance_id': row[2]}
                for row in cursor.fetchall()
            }

        self.stdout.write(f"  Found {len(active_versions)} active benchmark versions at {target_date.strftime('%Y-%m-%d')}")

        # Step 2: Get leaf scores for wayback using SQL function
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    score_id, model_id, benchmark_type_id, benchmark_id,
                    version, score_raw, score_ceiled, error, comment, end_timestamp
                FROM get_leaf_scores_for_wayback(%s)
            """, [target_date])
            columns = [col[0] for col in cursor.description]
            leaf_scores_raw = [dict(zip(columns, row)) for row in cursor.fetchall()]

        self.stdout.write(f"  Retrieved {len(leaf_scores_raw)} leaf scores from database")

        # Organize leaf scores by model_id
        scores_by_model = {}
        for score in leaf_scores_raw:
            model_id = score['model_id']
            if model_id not in scores_by_model:
                scores_by_model[model_id] = {}
            benchmark_type_id = score['benchmark_type_id']
            scores_by_model[model_id][benchmark_type_id] = score

        # Step 3: Get benchmark hierarchy for parent aggregation
        # Note: FinalBenchmarkContext has the CURRENT version (what the grid columns use)
        benchmarks = FinalBenchmarkContext.objects.filter(domain=domain)
        benchmark_info = {}
        parent_benchmarks_by_depth = {}  # depth -> list of benchmark info

        for b in benchmarks:
            # current_version = what the grid columns use (latest version)
            # historical_version = what was active at target date (from active_versions)
            historical_version = active_versions.get(b.benchmark_type_id, {}).get('version')
            benchmark_info[b.benchmark_type_id] = {
                'children': b.children or [],
                'depth': b.depth,
                'current_version': b.version,  # Grid column version
                'historical_version': historical_version  # Version active at wayback date
            }
            if b.children:
                depth = b.depth
                if depth not in parent_benchmarks_by_depth:
                    parent_benchmarks_by_depth[depth] = []
                parent_benchmarks_by_depth[depth].append(b.benchmark_type_id)

        # Step 4: Get model metadata from current context (metadata doesn't change over time)
        context = get_context(user=None, domain=domain, show_public=True)
        model_metadata = {}
        model_info = {}
        for model in context['models']:
            model_metadata[model.model_id] = {
                'architecture': model.model_meta.get('architecture', '') if model.model_meta else '',
                'model_family': model.model_meta.get('model_family', '') if model.model_meta else '',
                'total_parameter_count': model.model_meta.get('total_parameter_count', 0) if model.model_meta else 0,
                'total_layers': model.model_meta.get('total_layers', 0) if model.model_meta else 0,
                'model_size_mb': model.model_meta.get('model_size_mb', 0) if model.model_meta else 0,
                'runnable': model.model_meta.get('runnable', False) if model.model_meta else False,
                'training_dataset': model.model_meta.get('training_dataset', '') if model.model_meta else '',
                'task_specialization': model.model_meta.get('task_specialization', '') if model.model_meta else ''
            }
            model_info[model.model_id] = {
                'name': model.name,
                'submitter': model.submitter.get('display_name') if model.submitter else None,
                'public': model.public,
                'rank': model.rank
            }

        # Step 5: Build row_data for each model with scores
        row_data = []
        models_with_scores = set(scores_by_model.keys())

        for model_id in models_with_scores:
            model_scores = scores_by_model[model_id]
            info = model_info.get(model_id, {})

            rd = {
                'id': model_id,
                'rank': info.get('rank', 0),
                'model': {
                    'id': model_id,
                    'name': info.get('name', f'Model {model_id}'),
                    'submitter': info.get('submitter')
                },
                'public': info.get('public', True),
                'metadata': model_metadata.get(model_id, {})
            }

            # Track aggregated scores for this model (used for parent aggregation)
            aggregated_scores = {}

            # Add leaf benchmark scores
            # Key insight: We use the CURRENT version identifier as the key (what the grid expects)
            # but include the historical version number in the data for transparency
            for benchmark_type_id, score_data in model_scores.items():
                historical_version = score_data['version']
                # Use current version for the column key (so data appears in correct grid column)
                binfo = benchmark_info.get(benchmark_type_id, {})
                current_version = binfo.get('current_version', historical_version)
                vid = f"{benchmark_type_id}_v{current_version}"

                score_ceiled = score_data['score_ceiled']
                score_raw = score_data['score_raw']

                # Format score value
                if score_ceiled is not None:
                    if isinstance(score_ceiled, (int, float)):
                        formatted_score = f".{int(float(score_ceiled) * 1000):03d}" if float(score_ceiled) < 1 else f"{float(score_ceiled):.1f}"
                    else:
                        formatted_score = str(score_ceiled)
                else:
                    formatted_score = 'X'

                rd[vid] = {
                    'value': formatted_score,
                    'raw': score_raw,
                    'error': score_data['error'],
                    'color': get_score_color(score_raw),
                    'complete': 1,
                    'timestamp': score_data['end_timestamp'].isoformat() if score_data['end_timestamp'] else None,
                    'version': historical_version,  # Store historical version for reference
                    'current_version': current_version  # Store current version for debugging
                }

                # Check if score is valid (not None and not NaN)
                is_valid_score = score_raw is not None and not (isinstance(score_raw, float) and np.isnan(score_raw))
                aggregated_scores[benchmark_type_id] = {
                    'score_raw': score_raw,
                    'valid': is_valid_score
                }

            # Aggregate parent benchmarks (bottom-up by depth)
            for depth in sorted(parent_benchmarks_by_depth.keys(), reverse=True):
                for benchmark_type_id in parent_benchmarks_by_depth[depth]:
                    binfo = benchmark_info.get(benchmark_type_id, {})
                    children = binfo.get('children', [])
                    current_version = binfo.get('current_version', 0)
                    historical_version = binfo.get('historical_version', current_version)
                    vid = f"{benchmark_type_id}_v{current_version}"

                    # Compute average of valid children (exclude None and NaN)
                    valid_scores = []
                    for child_id in children:
                        child_score = aggregated_scores.get(child_id)
                        if child_score and child_score.get('valid'):
                            raw = child_score.get('score_raw')
                            if raw is not None and not (isinstance(raw, float) and np.isnan(raw)):
                                valid_scores.append(float(raw))

                    if valid_scores:
                        avg_score = sum(valid_scores) / len(valid_scores)
                        formatted_score = f".{int(avg_score * 1000):03d}" if avg_score < 1 else f"{avg_score:.1f}"

                        rd[vid] = {
                            'value': formatted_score,
                            'raw': avg_score,
                            'error': None,
                            'color': get_score_color(avg_score),
                            'complete': 1,
                            'timestamp': None,
                            'version': historical_version,
                            'current_version': current_version
                        }
                        aggregated_scores[benchmark_type_id] = {
                            'score_raw': avg_score,
                            'valid': True
                        }
                    else:
                        rd[vid] = {
                            'value': 'X',
                            'color': '#E0E1E2'
                        }
                        aggregated_scores[benchmark_type_id] = {'valid': False}

            row_data.append(rd)

        self.stdout.write(f"  Generated data for {len(row_data)} models")

        # Sort by rank
        row_data.sort(key=lambda x: x.get('rank', 999999))

        return json_serializable(row_data)

    def generate_snapshot(self, domain, target_date, output_dir, compress=True):
        """Generate a single snapshot for the given date."""
        self.stdout.write(f"Generating snapshot for {domain} at {target_date.strftime('%Y-%m-%d')}...")

        try:
            row_data = self.get_snapshot_data(domain, target_date)

            # Create filename
            date_str = target_date.strftime('%Y-%m-%d')
            if compress:
                filename = f"{date_str}.json.gz"
                filepath = output_dir / filename

                # Write compressed
                json_data = json.dumps(row_data, separators=(',', ':'))
                with gzip.open(filepath, 'wt', encoding='utf-8', compresslevel=6) as f:
                    f.write(json_data)
            else:
                filename = f"{date_str}.json"
                filepath = output_dir / filename

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(row_data, f, separators=(',', ':'))

            file_size = filepath.stat().st_size
            self.stdout.write(
                self.style.SUCCESS(f"  Created {filename} ({file_size / 1024:.1f} KB)")
            )

            return filepath

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  Failed to generate snapshot: {e}")
            )
            return None

    def generate_range_snapshots(self, domain, start_date, end_date, interval, output_dir, compress=True):
        """Generate snapshots for a range of dates."""
        self.stdout.write(
            f"Generating {interval} snapshots from {start_date.strftime('%Y-%m-%d')} "
            f"to {end_date.strftime('%Y-%m-%d')}..."
        )

        # Calculate interval delta
        if interval == 'daily':
            delta = timedelta(days=1)
        elif interval == 'weekly':
            delta = timedelta(weeks=1)
        else:  # monthly
            delta = timedelta(days=30)  # Approximate

        current_date = start_date
        generated_count = 0

        while current_date <= end_date:
            result = self.generate_snapshot(domain, current_date, output_dir, compress)
            if result:
                generated_count += 1

            if interval == 'monthly':
                # For monthly, advance to the same day next month
                if current_date.month == 12:
                    current_date = current_date.replace(year=current_date.year + 1, month=1)
                else:
                    current_date = current_date.replace(month=current_date.month + 1)
            else:
                current_date += delta

        self.stdout.write(
            self.style.SUCCESS(f"\nGenerated {generated_count} snapshots")
        )

    def generate_manifest(self, domain, output_dir):
        """Generate a manifest file listing all available snapshots."""
        snapshots = []

        for filepath in sorted(output_dir.glob('*.json*')):
            if filepath.name == 'manifest.json':
                continue

            # Parse date from filename
            date_str = filepath.name.split('.')[0]
            try:
                snapshot_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                continue

            snapshots.append({
                'date': date_str,
                'filename': filepath.name,
                'size': filepath.stat().st_size,
                'compressed': filepath.name.endswith('.gz')
            })

        manifest = {
            'domain': domain,
            'generated_at': datetime.now().isoformat(),
            'snapshot_count': len(snapshots),
            'snapshots': snapshots
        }

        manifest_path = output_dir / 'manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(f"Generated manifest with {len(snapshots)} snapshots")
        )

    def list_snapshots(self, output_dir):
        """List available snapshots."""
        manifest_path = output_dir / 'manifest.json'

        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)

            self.stdout.write(f"\nAvailable snapshots for {manifest['domain']}:")
            self.stdout.write(f"Generated: {manifest['generated_at']}")
            self.stdout.write(f"Count: {manifest['snapshot_count']}\n")

            for snapshot in manifest['snapshots']:
                size_kb = snapshot['size'] / 1024
                compressed = ' (gzipped)' if snapshot['compressed'] else ''
                self.stdout.write(f"  {snapshot['date']}: {size_kb:.1f} KB{compressed}")
        else:
            self.stdout.write("No manifest found. Scanning directory...")

            for filepath in sorted(output_dir.glob('*.json*')):
                if filepath.name == 'manifest.json':
                    continue
                size_kb = filepath.stat().st_size / 1024
                self.stdout.write(f"  {filepath.name}: {size_kb:.1f} KB")

    def clean_snapshots(self, output_dir, keep_count):
        """Remove old snapshots, keeping only the most recent ones."""
        snapshots = sorted(output_dir.glob('*.json*'), reverse=True)
        snapshots = [s for s in snapshots if s.name != 'manifest.json']

        if len(snapshots) <= keep_count:
            self.stdout.write(f"Only {len(snapshots)} snapshots exist, nothing to clean")
            return

        to_remove = snapshots[keep_count:]

        for filepath in to_remove:
            filepath.unlink()
            self.stdout.write(f"  Removed {filepath.name}")

        self.stdout.write(
            self.style.SUCCESS(f"Cleaned {len(to_remove)} old snapshots")
        )
