# Created manually by mschrimpf to address a change that happened at some point before
# https://github.com/brain-score/brain-score.web/pull/15 where the database model field `identifier` was renamed
# (or originally named) to `name`.
# Also address changed help text for `user.is_staff` in https://github.com/brain-score/brain-score.web/pull/69.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('benchmarks', '0003_user_display_name'),
    ]

    operations = [
        migrations.RenameField(
            model_name='model',
            old_name='identifier',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='model',
            name='name',
            field=models.CharField(max_length=200),
        ),
        migrations.AlterField(
            model_name='user',
            name='is_staff',
            field=models.BooleanField(default=False, help_text='Designates whether the user is a staff member.',
                                      verbose_name='staff status'),
        ),
    ]
