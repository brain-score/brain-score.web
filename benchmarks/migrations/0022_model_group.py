from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0021_change_meta_fields_to_foreignkey'),
    ]

    operations = [
        migrations.AddField(
            model_name='model',
            name='group',
            field=models.CharField(max_length=50, default=None, null=True),
        ),
    ]
