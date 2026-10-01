from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("benchmarks", "0031_widen_legacy_parameter_counts")]
    operations = [
        migrations.AddField(
            model_name="modelmetadatarevision",
            name="reviewer",
            field=models.CharField(max_length=100, blank=True),
        ),
    ]
