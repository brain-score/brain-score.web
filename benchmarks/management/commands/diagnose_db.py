"""
Management command to diagnose database performance for leaderboard queries.

Usage:
    python manage.py diagnose_db [domain]
    python manage.py diagnose_db vision
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = 'Diagnose database performance for leaderboard queries'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            nargs='?',
            type=str,
            default='vision',
            help='Domain to diagnose (vision or language, default: vision)'
        )

    def handle(self, *args, **options):
        domain = options['domain']

        # Safety check
        db_host = settings.DATABASES['default']['HOST']
        self.stdout.write(self.style.WARNING('=== ENVIRONMENT CHECK ==='))
        self.stdout.write(f"Database Host: {db_host}")

        if 'prod' in db_host.lower() or 'production' in db_host.lower():
            self.stderr.write(self.style.ERROR('ERROR: Cannot run diagnostics against production database'))
            return

        self.stdout.write(self.style.SUCCESS('✓ Connected to dev/test database'))
        self.stdout.write('')

        with connection.cursor() as cursor:
            # 1. Check indexes on mv_final_model_context
            self.stdout.write(self.style.SUCCESS('=== INDEXES ON mv_final_model_context ===\n'))
            cursor.execute("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'mv_final_model_context'
                ORDER BY indexname;
            """)

            indexes = cursor.fetchall()
            if indexes:
                for index_name, index_def in indexes:
                    self.stdout.write(f"{index_name}:")
                    self.stdout.write(f"  {index_def}")
                    self.stdout.write('')
            else:
                self.stdout.write(self.style.WARNING("⚠ No indexes found on mv_final_model_context!"))
                self.stdout.write('')

            # Check for specific needed indexes
            has_domain_public_index = any('domain' in idx[1] and 'public' in idx[1] for idx in indexes)
            if not has_domain_public_index:
                self.stdout.write(self.style.ERROR('❌ Missing index on (domain, public) columns'))
                self.stdout.write('   This is likely causing the 19-second query time!')
                self.stdout.write('')
                self.stdout.write('   Recommendation:')
                self.stdout.write('   CREATE INDEX CONCURRENTLY idx_fmc_domain_public')
                self.stdout.write('   ON mv_final_model_context(domain, public)')
                self.stdout.write('   WHERE public = true;')
                self.stdout.write('')
            else:
                self.stdout.write(self.style.SUCCESS('✓ Index on (domain, public) exists'))
                self.stdout.write('')

            # 2. Check table size and stats
            self.stdout.write(self.style.SUCCESS('=== TABLE SIZE AND STATISTICS ===\n'))
            cursor.execute("""
                SELECT
                    pg_size_pretty(pg_total_relation_size('mv_final_model_context')) as total_size,
                    pg_size_pretty(pg_relation_size('mv_final_model_context')) as table_size,
                    pg_size_pretty(pg_indexes_size('mv_final_model_context')) as indexes_size,
                    (SELECT COUNT(*) FROM mv_final_model_context) as total_rows,
                    (SELECT COUNT(*) FROM mv_final_model_context WHERE domain = %s) as domain_rows,
                    (SELECT COUNT(*) FROM mv_final_model_context WHERE domain = %s AND public = true) as public_rows;
            """, [domain, domain])

            stats = cursor.fetchone()
            self.stdout.write(f"Total size (table + indexes): {stats[0]}")
            self.stdout.write(f"Table size: {stats[1]}")
            self.stdout.write(f"Indexes size: {stats[2]}")
            self.stdout.write(f"Total rows: {stats[3]:,}")
            self.stdout.write(f"Rows in {domain} domain: {stats[4]:,}")
            self.stdout.write(f"Public rows in {domain} domain: {stats[5]:,}")
            self.stdout.write('')

            # 3. Check JSONB column sizes
            self.stdout.write(self.style.SUCCESS('=== JSONB COLUMN SIZES ===\n'))
            cursor.execute("""
                SELECT
                    model_id,
                    name,
                    pg_size_pretty(pg_column_size(scores)::bigint) as scores_size,
                    jsonb_array_length(scores) as num_scores,
                    pg_size_pretty(pg_column_size(model_meta)::bigint) as model_meta_size
                FROM mv_final_model_context
                WHERE domain = %s AND public = true
                ORDER BY pg_column_size(scores) DESC
                LIMIT 10;
            """, [domain])

            self.stdout.write("Top 10 models by scores field size:")
            self.stdout.write(f"{'Model ID':<10} {'Name':<30} {'Scores Size':<15} {'# Scores':<10} {'Metadata Size':<15}")
            self.stdout.write("-" * 90)
            for row in cursor.fetchall():
                self.stdout.write(f"{row[0]:<10} {row[1][:28]:<30} {row[2]:<15} {row[3]:<10} {row[4]:<15}")
            self.stdout.write('')

            # 4. EXPLAIN ANALYZE the actual query
            self.stdout.write(self.style.SUCCESS('=== QUERY EXECUTION PLAN ===\n'))
            self.stdout.write(f"Analyzing query: SELECT * FROM mv_final_model_context WHERE domain = '{domain}' AND public = true")
            self.stdout.write('')

            try:
                cursor.execute("""
                    EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                    SELECT * FROM mv_final_model_context
                    WHERE domain = %s AND public = true;
                """, [domain])
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ Could not run EXPLAIN ANALYZE: {e}"))

            plan = cursor.fetchall()
            for line in plan:
                self.stdout.write(line[0])
            self.stdout.write('')

            # 5. Check for slow queries in pg_stat_statements (if available)
            self.stdout.write(self.style.SUCCESS('=== RECENT SLOW QUERIES (pg_stat_statements) ===\n'))
            try:
                cursor.execute("""
                    SELECT
                        LEFT(query, 100) as query_snippet,
                        calls,
                        ROUND(mean_exec_time::numeric, 2) as mean_ms,
                        ROUND(max_exec_time::numeric, 2) as max_ms,
                        ROUND(total_exec_time::numeric, 2) as total_ms
                    FROM pg_stat_statements
                    WHERE query LIKE '%mv_final_model_context%'
                        AND mean_exec_time > 100
                    ORDER BY mean_exec_time DESC
                    LIMIT 10;
                """)

                slow_queries = cursor.fetchall()
                if slow_queries:
                    self.stdout.write(f"{'Query (first 100 chars)':<102} {'Calls':<8} {'Mean (ms)':<12} {'Max (ms)':<12} {'Total (ms)':<12}")
                    self.stdout.write("-" * 150)
                    for row in slow_queries:
                        self.stdout.write(f"{row[0]:<102} {row[1]:<8} {row[2]:<12} {row[3]:<12} {row[4]:<12}")
                else:
                    self.stdout.write("No slow queries found in pg_stat_statements")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠ pg_stat_statements not available: {e}"))

            self.stdout.write('')

        # 6. Summary and recommendations
        self.stdout.write(self.style.SUCCESS('=== SUMMARY AND RECOMMENDATIONS ===\n'))

        if not has_domain_public_index:
            self.stdout.write(self.style.ERROR('CRITICAL: Missing index on (domain, public)'))
            self.stdout.write('')
            self.stdout.write('This is the #1 cause of the 19-second query time.')
            self.stdout.write('')
            self.stdout.write('To fix (run on dev database):')
            self.stdout.write('  CREATE INDEX CONCURRENTLY idx_fmc_domain_public')
            self.stdout.write('  ON mv_final_model_context(domain, public)')
            self.stdout.write('  WHERE public = true;')
            self.stdout.write('')
            self.stdout.write('Expected improvement: 19s → 1-2s')
            self.stdout.write('')

        self.stdout.write('Additional optimizations to consider:')
        self.stdout.write('  1. The scores JSONB field is large (~1-2MB per row)')
        self.stdout.write('     Consider using .defer() or .only() to avoid loading it until needed')
        self.stdout.write('')
        self.stdout.write('  2. Check the query plan above for:')
        self.stdout.write('     - "Seq Scan" (bad) vs "Index Scan" (good)')
        self.stdout.write('     - "Buffers: shared hit=" vs "shared read=" (cache hits vs disk reads)')
        self.stdout.write('')
        self.stdout.write('Next steps:')
        self.stdout.write('  1. If missing index: Add the index on dev, re-run audit_payload')
        self.stdout.write('  2. Review the EXPLAIN ANALYZE output above')
        self.stdout.write('  3. Consider Django ORM optimizations (.defer(), .only())')
