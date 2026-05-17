# Generated for nt/historical-models-2: per-model coverage delta column.
#
# Adds `coverage_leaves_added_vs_prev` (JSON list of leaf benchmark identifiers
# the model newly got scored on this month, restricted to leaves already in the
# global aggregate the prior month). Populated by `recompute_score_trends`.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0023_monthbenchmarkedge_modelmonthlyaggregate_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='modelmonthlyaggregate',
            name='coverage_leaves_added_vs_prev',
            field=models.JSONField(default=list),
        ),
    ]
