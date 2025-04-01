from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _
import json


class UserManager(BaseUserManager):
    """
    A custom user manager to deal with emails as unique identifiers for auth
    instead of usernames. The default that's used is "UserManager"
    """

    def _create_user(self, email, password, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)

    def get_by_natural_key(self, username):
        # __iexact is a filter that gives a case-insensitive representation of a field.
        # Permits mismatched casing for usernames.
        case_insensitive_username_field = '{}__iexact'.format(self.model.USERNAME_FIELD)
        return self.get(**{case_insensitive_username_field: username})


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, null=True)
    display_name = models.CharField(max_length=300, null=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user is a staff member.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            'Designates whether this user should be treated as active.'
            'Unselect this instead of deleting accounts.'
        ),
    )

    USERNAME_FIELD = 'email'
    objects = UserManager()

    def get_full_name(self):
        return self.display_name

    def get_short_name(self):
        return self.display_name

    def natural_key(self):
        return self.email,

    def __repr__(self):
        return generic_repr(self)

    class Meta:
        db_table = 'brainscore_user'


def generic_repr(obj):
    return obj.__class__.__name__ \
           + "[" + ",".join(f"{field}={value}" for field, value in vars(obj).items()) + "]"


class Reference(models.Model):
    author = models.CharField(max_length=300)
    year = models.IntegerField()
    url = models.CharField(max_length=1000, unique=True)
    bibtex = models.TextField()

    def __repr__(self):
        return generic_repr(self)

    class ReferenceManager(models.Manager):
        def get_by_natural_key(self, url):
            return self.get(url=url)

    objects = ReferenceManager()

    class Meta:
        db_table = 'brainscore_reference'


class BenchmarkType(models.Model):
    identifier = models.CharField(max_length=200, primary_key=True)
    domain = models.CharField(max_length=200, default="vision")
    reference = models.ForeignKey(Reference, on_delete=models.PROTECT, null=True)  # null for parents
    order = models.IntegerField(default=999)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)  # null: average benchmark has no parent
    visible = models.BooleanField(default=False, null=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, default=2)  # null for parents

    def __repr__(self):
        return generic_repr(self)

    class Meta:
        db_table = 'brainscore_benchmarktype'


class BenchmarkMeta(models.Model):
    number_of_stimuli = models.IntegerField(null=True)
    number_of_recording_sites = models.IntegerField(null=True)
    recording_sites = models.CharField(max_length=100, null=True)
    behavioral_task = models.CharField(max_length=100, null=True)

    class Meta:
        db_table = 'brainscore_benchmarkmeta'

class BenchmarkStimuliMeta(models.Model):
    num_stimuli = models.IntegerField(null=True, default=None)
    datatype = models.CharField(max_length=100, null=True, default="image")
    stimuli_subtype = models.CharField(max_length=100, null=True, default=None)
    total_size_mb = models.FloatField(null=True, default=None)
    brainscore_link = models.CharField(max_length=200, null=True, default=None)
    extra_notes = models.CharField(max_length=1000, null=True, default=None)

    class Meta:
        db_table = 'brainscore_benchmark_stimuli_meta'


class BenchmarkDataMeta(models.Model):
    benchmark_type = models.CharField(max_length=100, null=True, default=None)
    task = models.CharField(max_length=100, null=True, default=None)
    region = models.CharField(max_length=100, null=True, default=None)
    hemisphere = models.CharField(max_length=100, null=True, default=None)
    num_recording_sites = models.IntegerField(null=True, default=None)
    duration_ms = models.FloatField(null=True, default=None)
    species = models.CharField(max_length=100, null=True, default=None)
    datatype = models.CharField(max_length=100, null=True, default=None)
    num_subjects = models.IntegerField(null=True, default=None)
    pre_processing = models.CharField(max_length=100, null=True, default=None)
    brainscore_link = models.CharField(max_length=200, null=True, default=None)
    extra_notes = models.CharField(max_length=1000, null=True, default=None)

    class Meta:
        db_table = 'brainscore_benchmark_data_meta'


class BenchmarkMetricMeta(models.Model):
    type = models.CharField(max_length=100, null=True, default=None)
    reference = models.CharField(max_length=100, null=True, default=None)
    public = models.BooleanField(default=False, null=False)
    brainscore_link = models.CharField(max_length=200, null=True, default=None)
    extra_notes = models.CharField(max_length=1000, null=True, default=None)

    class Meta:
        db_table = 'brainscore_benchmark_metric_meta'

class BenchmarkInstance(models.Model):
    benchmark_type = models.ForeignKey(BenchmarkType, on_delete=models.PROTECT)
    version = models.IntegerField()
    ceiling = models.FloatField(default=0, null=True)
    ceiling_error = models.FloatField(null=True)
    meta = models.ForeignKey(BenchmarkMeta, null=True, on_delete=models.PROTECT)
    stimuli_meta = models.OneToOneField(BenchmarkStimuliMeta, null=True, on_delete=models.CASCADE)
    data_meta = models.OneToOneField(BenchmarkDataMeta, null=True, on_delete=models.CASCADE)
    metric_meta = models.OneToOneField(BenchmarkMetricMeta, null=True, on_delete=models.CASCADE)

    def __repr__(self):
        return generic_repr(self)

    def natural_key(self):
        return self.benchmark_type.identifier, self.version

    class BenchmarkInstanceManager(models.Manager):
        def get_by_natural_key(self, identifier, version):
            return self.get(benchmark_type__identifier=identifier, version=version)

    objects = BenchmarkInstanceManager()

    class Meta:
        unique_together = (('benchmark_type', 'version'),)
        db_table = 'brainscore_benchmarkinstance'


class Submission(models.Model):
    class Status:
        PENDING = 'running'
        SUCCESS = 'successful'
        FAILURE = 'failure'

    submitter = models.ForeignKey(User, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True, blank=True)
    model_type = models.CharField(max_length=30, default='BaseModel')
    status = models.CharField(max_length=25, default='unknown')

    # equivalent to ID until language changes were added: (ID 6756)
    jenkins_id = models.IntegerField()

    def __repr__(self):
        return generic_repr(self)

    class Meta:
        db_table = 'brainscore_submission'


class Model(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    reference = models.ForeignKey(Reference, on_delete=models.PROTECT, null=True)  # null for models without publication
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, null=True)  # null for self-run models
    visual_degrees = models.IntegerField(null=True)  # null during model creation before querying objec
    public = models.BooleanField(default=False)
    competition = models.CharField(max_length=200, default=None, null=True)
    domain = models.CharField(max_length=200, default="vision")

    def __repr__(self):
        return generic_repr(self)

    def natural_key(self):
        return self.name, self.owner.natural_key()

    class ModelManager(models.Manager):
        def get_by_natural_key(self, name, owner=None):
            kwargs = dict(name=name)
            if owner is not None:  # if owner is passed, explicitly use it to link, otherwise try without
                kwargs['owner__email'] = owner
            return self.get(**kwargs)

    objects = ModelManager()

    class Meta:
        db_table = 'brainscore_model'


class ModelMeta(models.Model):
    model = models.OneToOneField(Model, on_delete=models.CASCADE, primary_key=True)
    architecture = models.CharField(max_length=100, null=True, default=None)
    model_family = models.CharField(max_length=100, null=True, default=None)
    total_parameter_count = models.IntegerField(null=True, default=None)
    trainable_parameter_count = models.IntegerField(null=True, default=None)
    total_layers = models.IntegerField(null=True, default=None)
    trainable_layers = models.IntegerField(null=True, default=None)
    model_size_mb = models.FloatField(null=True, default=None)
    training_dataset = models.CharField(max_length=100, null=True, default=None)
    task_specialization = models.CharField(max_length=100, null=True, default=None)
    brainscore_link = models.CharField(max_length=256, null=True, default=None)
    hugging_face_link = models.CharField(max_length=256, null=True, default=None)
    extra_notes = models.CharField(max_length=1000, null=True, default=None)

    class Meta:
        db_table = 'brainscore_modelmeta'

class Score(models.Model):
    benchmark = models.ForeignKey(BenchmarkInstance, on_delete=models.PROTECT)
    model = models.ForeignKey(Model, on_delete=models.PROTECT)

    score_raw = models.FloatField(default=0, null=True)
    score_ceiled = models.FloatField(default=0, null=True)
    error = models.FloatField(default=0, null=True)
    start_timestamp = models.DateTimeField(blank=True)
    end_timestamp = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    comment = models.CharField(max_length=1000, null=True)

    def __repr__(self):
        return generic_repr(self)

    def natural_key(self):
        return self.benchmark.natural_key(), self.model.natural_key()

    natural_key.dependencies = ['benchmarks.BenchmarkInstance', 'benchmarks.model']

    class Meta:
        db_table = 'brainscore_score'


class MailingList(models.Model):
    email = models.EmailField(max_length=254)

    indexes = [
        models.Index(fields=['email']),
    ]

class JSONBField(models.JSONField):
    """
    Django's standard JSONField tries to decode JSON "strings" into dicts/lists.
    However, in the materialized view creation, JSONB instead of JSON is used.
    Psycopg2 automatically converts JSONB to python dicts/lists.

    JSONField led to a TypeError because it would receive a string instead of
    an already decoded Python object.

    JSONB is also more performant for large datasets (like FinalModelContext)
    """
    def from_db_value(self, value, expression, connection):
        # 1) If DB returned None, just pass it
        if value is None:
            return None

        # 2) If DB gave us dict/list, return as is
        if isinstance(value, (dict, list)):
            return value

        # 3) Otherwise assume it's a JSON string, parse with json.loads
        return json.loads(value)

class FinalBenchmarkContext(models.Model):
    benchmark_type_id = models.CharField(max_length=255, primary_key=True)
    version = models.IntegerField()
    ceiling = models.CharField(max_length=32)
    ceiling_error = models.FloatField(null=True, blank=True)
    meta_id = models.IntegerField(null=True, blank=True)
    children = JSONBField(null=True, blank=True)
    parent = JSONBField(null=True, blank=True)
    visible = models.BooleanField(default=True)
    owner_id = models.IntegerField(null=True, blank=True)
    root_parent = models.CharField(max_length=64)
    domain = models.CharField(max_length=64)
    benchmark_url = models.CharField(max_length=255)
    benchmark_reference_identifier = models.CharField(max_length=255)
    benchmark_bibtex = models.TextField()
    depth = models.IntegerField()
    sort_path = models.TextField()
    is_leaf = models.BooleanField()
    number_of_all_children = models.IntegerField()
    overall_order = models.IntegerField()
    identifier = models.CharField(max_length=255)
    short_name = models.CharField(max_length=255)
    benchmark_id = models.IntegerField(null=True, blank=True)
    benchmark_data_meta = JSONBField(null=True, blank=True)
    benchmark_metric_meta = JSONBField(null=True, blank=True)
    benchmark_stimuli_meta = JSONBField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'mv_final_benchmark_context'

    @property
    def id(self):
        """Provide an 'id' so that templates using {{ benchmark.id}} still work. Can make chage in db too"""
        return self.benchmark_id

class FinalModelContext(models.Model):
    model_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    reference_identifier = models.CharField(max_length=255, null=True, blank=True)
    url = models.CharField(max_length=512, null=True, blank=True)
    user = JSONBField(null=True, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    owner = JSONBField(null=True, blank=True)
    public = models.BooleanField()
    competition = models.CharField(max_length=255, null=True, blank=True)
    domain = models.CharField(max_length=64)
    visual_degrees = models.IntegerField(null=True, blank=True)
    layers = JSONBField(null=True, blank=True)
    rank = models.IntegerField()
    scores = JSONBField(null=True, blank=True)
    build_status = models.CharField(max_length=64)
    submitter = JSONBField(null=True, blank=True)
    submission_id = models.IntegerField(null=True, blank=True)
    jenkins_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    primary_model_id = models.IntegerField(null=True, blank=True)
    num_secondary_models = models.IntegerField(null=True, blank=True)
    model_meta = JSONBField(null=True, blank=True)
    class Meta:
        managed = False
        db_table = 'mv_final_model_context'

    @property
    def id(self):
        """Provide an 'id' so that templates using {{ model.id}} still work. Can make chage in db too"""
        return self.model_id

# Not currently used but will be needed for leaderboard views to recompute color scales
class BenchmarkMinMax(models.Model):
    benchmark_identifier = models.CharField(max_length=255, primary_key=True)
    bench_id = models.CharField(max_length=255)
    min_score = models.FloatField()
    max_score = models.FloatField()

    class Meta:
        managed = False
        db_table = 'mv_benchmark_minmax'

class FlattenedModelContext(models.Model):
    """
    Django model for the 'mv_flattened_model_context' materialized view,
    which holds one row per (model × benchmark).
    Used for leaderboard views
    """
    id = models.BigIntegerField(primary_key=True)
    model_id = models.IntegerField(blank=True, null=True)
    model_name = models.TextField(blank=True, null=True)
    model_domain = models.CharField(max_length=255, blank=True, null=True)
    model_public = models.BooleanField(default=False)
    submission_id = models.IntegerField(blank=True, null=True)
    build_status = models.CharField(max_length=255, blank=True, null=True)
    submission_timestamp = models.DateTimeField(blank=True, null=True)
    jenkins_id = models.CharField(max_length=255, blank=True, null=True)
    model_reference_identifier = models.IntegerField(blank=True, null=True)
    model_author = models.TextField(blank=True, null=True)
    model_year = models.TextField(blank=True, null=True)
    model_url = models.TextField(blank=True, null=True)
    model_bibtex = models.TextField(blank=True, null=True)
    visual_degrees = models.FloatField(blank=True, null=True)
    overall_rank = models.IntegerField(blank=True, null=True)
    model_owner_info = JSONBField(blank=True, null=True)
    submitter_info = JSONBField(blank=True, null=True)
    competition = models.BooleanField(default=False)
    model_meta = JSONBField(blank=True, null=True)
    layers = JSONBField(blank=True, null=True)

    benchmark_type_id = models.CharField(max_length=255, blank=True, null=True)
    benchmark_identifier = models.CharField(max_length=255, blank=True, null=True)
    benchmark_short_name = models.CharField(max_length=255, blank=True, null=True)
    benchmark_parent = JSONBField(blank=True, null=True)
    benchmark_version = models.IntegerField(blank=True, null=True)

    score_raw = models.CharField(max_length=255, blank=True, null=True)
    score_ceiled_raw = models.CharField(max_length=255, blank=True, null=True)
    score_ceiled_label = models.CharField(max_length=255, blank=True, null=True)
    error = models.CharField(max_length=255, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    score_visual_degrees = models.CharField(max_length=255, blank=True, null=True)
    color = models.CharField(max_length=255, blank=True, null=True)
    median_score = models.CharField(max_length=255, blank=True, null=True)
    best_score = models.CharField(max_length=255, blank=True, null=True)
    benchmark_rank = models.CharField(max_length=255, blank=True, null=True)
    is_complete = models.CharField(max_length=255, blank=True, null=True)

    benchmark_data_meta = JSONBField(blank=True, null=True)
    benchmark_metric_meta = JSONBField(blank=True, null=True)
    benchmark_stimuli_meta = JSONBField(blank=True, null=True)

    is_leaf = models.BooleanField(default=False)
    depth = models.IntegerField(blank=True, null=True)
    sort_path = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'mv_flattened_model_context'

