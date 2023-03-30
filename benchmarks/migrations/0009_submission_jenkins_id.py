from django.db import migrations, models


def copy_id_to_jenkins_id(apps, schema_editor):
    submission_model = apps.get_model('benchmarks', 'Submission')
    for submission in submission_model.objects.all().iterator():
        submission.jenkins_id = submission.id
        submission.save()


class Migration(migrations.Migration):
    dependencies = [
        ('benchmarks', '0008_model_domain'),
    ]

    # 1. add new null jenkins_id field, 2. copy id -> jenkins_id, 3. set jenkins_id non-null,
    # 4. set id to be auto-created
    operations = [
        migrations.AddField(
            model_name='submission',
            name='jenkins_id',
            field=models.IntegerField(null=True),
        ),
        migrations.RunPython(copy_id_to_jenkins_id),
        migrations.AlterField(
            model_name='submission',
            name='jenkins_id',
            field=models.IntegerField(null=False),
        ),

        migrations.AlterField(
            model_name='submission',
            name='id',
            field=models.AutoField(primary_key=True, auto_created=True),
        ),
    ]
