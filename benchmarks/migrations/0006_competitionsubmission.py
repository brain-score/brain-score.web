# Generated by Django 3.2.3 on 2021-11-17 22:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0005_visual_degrees_benchmark_meta'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompetitionSubmission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('competition', models.CharField(max_length=100)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='benchmarks.submission')),
            ],
            options={
                'db_table': 'brainscore_competition_submission',
            },
        ),
    ]
