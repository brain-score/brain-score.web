# Generated by Django 3.0.3 on 2020-09-10 23:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('benchmarks', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='benchmarktype',
            name='visible',
            field=models.BooleanField(default=False),
        ),
    ]
