# Generated by Django 4.0 on 2025-03-27 14:58

import benchmarks.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0016_adds_benchmark_metadata'),
    ]

    operations = [
        migrations.RunSQL(
            sql=open('benchmarks/sql/mv.sql').read(),
            # No reverse SQL needed as these are mostly materialized views. 
            # There are two tables (final_agg_scores and intermediate_parent_stats) that are used as
            # intermediate tables to create the materialized views to allow functions to be used.
            # May need to add a reverse SQL to drop these intermediate tables.
            reverse_sql=''
        ),
        migrations.CreateModel(
            name='BenchmarkMinMax',
            fields=[
                ('benchmark_identifier', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('bench_id', models.CharField(max_length=255)),
                ('min_score', models.FloatField()),
                ('max_score', models.FloatField()),
            ],
            options={
                'db_table': 'mv_benchmark_minmax',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='FinalBenchmarkContext',
            fields=[
                ('benchmark_type_id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('version', models.IntegerField()),
                ('ceiling', models.CharField(max_length=32)),
                ('ceiling_error', models.FloatField(blank=True, null=True)),
                ('meta_id', models.IntegerField(blank=True, null=True)),
                ('children', benchmarks.models.JSONBField(blank=True, null=True)),
                ('parent', benchmarks.models.JSONBField(blank=True, null=True)),
                ('visible', models.BooleanField(default=True)),
                ('owner_id', models.IntegerField(blank=True, null=True)),
                ('root_parent', models.CharField(max_length=64)),
                ('domain', models.CharField(max_length=64)),
                ('benchmark_url', models.CharField(max_length=255)),
                ('benchmark_reference_identifier', models.CharField(max_length=255)),
                ('benchmark_bibtex', models.TextField()),
                ('depth', models.IntegerField()),
                ('number_of_all_children', models.IntegerField()),
                ('overall_order', models.IntegerField()),
                ('identifier', models.CharField(max_length=255)),
                ('short_name', models.CharField(max_length=255)),
                ('benchmark_id', models.IntegerField(blank=True, null=True)),
                ('benchmark_data_meta', benchmarks.models.JSONBField(blank=True, null=True)),
                ('benchmark_metric_meta', benchmarks.models.JSONBField(blank=True, null=True)),
                ('benchmark_stimuli_meta', benchmarks.models.JSONBField(blank=True, null=True)),
            ],
            options={
                'db_table': 'mv_final_benchmark_context',
                'managed': False,
            },
        ),
        migrations.CreateModel(
            name='FinalModelContext',
            fields=[
                ('model_id', models.IntegerField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('reference_identifier', models.CharField(blank=True, max_length=255, null=True)),
                ('url', models.CharField(blank=True, max_length=512, null=True)),
                ('user', benchmarks.models.JSONBField(blank=True, null=True)),
                ('user_id', models.IntegerField(blank=True, null=True)),
                ('owner', benchmarks.models.JSONBField(blank=True, null=True)),
                ('public', models.BooleanField()),
                ('competition', models.CharField(blank=True, max_length=255, null=True)),
                ('domain', models.CharField(max_length=64)),
                ('visual_degrees', models.IntegerField(blank=True, null=True)),
                ('layers', benchmarks.models.JSONBField(blank=True, null=True)),
                ('rank', models.IntegerField()),
                ('scores', benchmarks.models.JSONBField(blank=True, null=True)),
                ('build_status', models.CharField(max_length=64)),
                ('submitter', benchmarks.models.JSONBField(blank=True, null=True)),
                ('submission_id', models.IntegerField(blank=True, null=True)),
                ('jenkins_id', models.IntegerField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(blank=True, null=True)),
                ('primary_model_id', models.IntegerField(blank=True, null=True)),
                ('num_secondary_models', models.IntegerField(blank=True, null=True)),
                ('model_meta', benchmarks.models.JSONBField(blank=True, null=True)),
            ],
            options={
                'db_table': 'mv_final_model_context',
                'managed': False,
            },
        ),
    ]
