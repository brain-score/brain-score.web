from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CandidateModel',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('brain_score', models.FloatField(default=0)),
                ('behavior', models.FloatField(default=0)),
                ('imagenet_top1', models.FloatField(default=0)),
                ('it', models.FloatField(default=0)),
                ('v4', models.FloatField(default=0)),
                ('paper_link', models.CharField(max_length=200)),
                ('paper_identifier', models.CharField(max_length=200)),
            ],
        ),
    ]
