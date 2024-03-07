from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0014_mailinglist'),
    ]

    operations = [
        migrations.AddField(
            model_name='benchmarktype',
            name='competition',
            field=models.CharField(default=None, max_length=200, null=True),
        ),
    ]
