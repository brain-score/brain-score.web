from pathlib import Path

from django.db import migrations


MIGRATION_SQL = (
    Path(__file__).resolve().parent / 'sql' / '0027_materialized_views.sql'
).read_text(encoding='utf-8')


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0026_modelmonthlyaggregate_coverage_leaves_added_vs_prev'),
    ]

    operations = [
        migrations.RunSQL(
            sql=MIGRATION_SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
