# Generated by Django 3.2.3 on 2021-11-19 17:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0006_competitionsubmission'),
    ]

    operations = [
        migrations.AddField(
            model_name='model',
            name='competition',
            field=models.CharField(default='', max_length=200),
        ),
    ]
