# Generated by Django 3.2.10 on 2023-04-01 16:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('benchmarks', '0009_submission_jenkins_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='benchmarktype',
            name='domain',
            field=models.CharField(default='vision', max_length=200),
        ),
        migrations.AlterField(
            model_name='model',
            name='domain',
            field=models.CharField(default='vision', max_length=200),
        ),
    ]
