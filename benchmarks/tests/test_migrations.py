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
        migration = import_module(
            'benchmarks.migrations.0027_refresh_materialized_view_definitions'
        )
        current_sql = (
            MIGRATIONS_DIR.parent / 'sql' / 'mv.sql'
        ).read_text(encoding='utf-8')

        self.assertEqual(
            migration.Migration.operations[0].sql.splitlines(),
            current_sql.splitlines(),
        )
