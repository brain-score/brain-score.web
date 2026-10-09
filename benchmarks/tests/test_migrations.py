from importlib import import_module
from pathlib import Path
from unittest import TestCase


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / 'migrations'


class MaterializedViewMigrationTests(TestCase):
    def test_0017_does_not_use_columns_added_by_later_migrations(self):
        migration = import_module(
            'benchmarks.migrations.0017_adds_materialized_view_contexts'
        )

        self.assertNotIn(
            'data_publicly_available',
            migration.Migration.operations[0].sql,
        )

    def test_latest_snapshot_matches_current_definition(self):
        snapshot = import_module(
            'benchmarks.migrations.0027_refresh_materialized_view_definitions'
        ).Migration.operations[0].sql
        final_context = import_module(
            'benchmarks.migrations.0034_final_model_context_reads_v2_metadata'
        )
        current_sql = (
            MIGRATIONS_DIR.parent / 'sql' / 'mv.sql'
        ).read_text(encoding='utf-8')

        self.assertIn(final_context.REVERSE_SQL, snapshot)
        self.assertEqual(
            snapshot.replace(final_context.REVERSE_SQL, final_context.FORWARD_SQL).splitlines(),
            current_sql.splitlines(),
        )
