# Generated by Django 2.2.1 on 2020-03-28 16:27

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0011_update_proxy_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='Benchmark',
            fields=[
                ('name', models.CharField(max_length=200, primary_key=True, serialize=False)),
                ('ceiling', models.FloatField(default=0, null=True)),
                ('ceiling_error', models.FloatField(default=0, null=True)),
                ('parent', models.CharField(max_length=200, null=True)),
                ('link', models.CharField(max_length=1000, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ModelReference',
            fields=[
                ('model', models.CharField(max_length=200, primary_key=True, serialize=False)),
                ('short_reference', models.CharField(max_length=200)),
                ('link', models.CharField(max_length=200)),
                ('bibtex', models.CharField(max_length=2000)),
                ('user', models.CharField(max_length=200)),
                ('public', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Score',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(db_index=True, max_length=200)),
                ('benchmark', models.CharField(db_index=True, max_length=200)),
                ('score_raw', models.FloatField(default=0, null=True)),
                ('score_ceiled', models.FloatField(default=0, null=True)),
                ('error', models.FloatField(default=0, null=True)),
                ('layer', models.CharField(default=None, max_length=200, null=True)),
            ],
            options={
                'unique_together': {('model', 'benchmark')},
            },
        ),
        migrations.CreateModel(
            name='ModelMeta',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.CharField(max_length=200)),
                ('key', models.CharField(max_length=200)),
                ('value', models.CharField(max_length=200)),
            ],
            options={
                'unique_together': {('model', 'key')},
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('email', models.EmailField(max_length=254, null=True, unique=True)),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=False, help_text='Designates whether this user should be treated as active.Unselect this instead of deleting accounts.', verbose_name='active')),
                ('datefield1', models.DateField(default=datetime.datetime(2019, 1, 1, 0, 0), verbose_name='Date')),
                ('datefield2', models.DateField(default=datetime.datetime(2019, 1, 1, 0, 0), verbose_name='Date')),
                ('datefield3', models.DateField(default=datetime.datetime(2019, 1, 1, 0, 0), verbose_name='Date')),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.Group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.Permission', verbose_name='user permissions')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
