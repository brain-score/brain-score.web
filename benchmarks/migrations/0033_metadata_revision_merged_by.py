from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("benchmarks", "0032_metadata_revision_reviewer")]
    operations = [
        migrations.AddField(
            model_name="modelmetadatarevision",
            name="merged_by",
            field=models.CharField(max_length=100, blank=True),
        ),
    ]
