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
    is_quota_exempt = models.BooleanField(default=False)  # file upload quota exemption

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
    data_publicly_available = models.BooleanField(default=True, null=False)

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
    runnable = models.BooleanField(default=True, null=True)
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

    JSONField will lead to a TypeError because it would receive a string instead of
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
    """
    Materialized view for benchmark context.

    This view aggregates benchmark information including hierarchy, metadata, and relationships.
    It replaces the previous _collect_benchmarks() functionality from views/index.py.

    Attributes:
        benchmark_type_id (str): Primary key, unique identifier for the benchmark type (e.g., MajajHong2015.IT-pls, Ferguson2024)
        version (int): Version number of the benchmark
        ceiling (str): Ceiling score for the benchmark
        ceiling_error (float, optional): Error margin for the ceiling score
        children (dict, optional): JSON object containing direct child benchmark identifiers (e.g., ["Ferguson2024llh-value_delta", "Ferguson2024round_f-value_delta", ...])
        parent (dict, optional): JSON object with parent benchmark info including:
            - identifier: Parent benchmark identifier (e.g., "behavior_vision")
            - domain: Domain of parent benchmark (e.g., "vision")
            - reference_id: Reference ID (e.g., "null" for parents)
            - order: Display order (e.g., 2)
            - parent_id: Parent's parent ID (e.g., "average_vision")
            - visible: Visibility status (e.g., True)
            - owner_id: Owner's user ID (e.g., 2)
        visible (bool): Whether the benchmark is visible in the UI
        domain (str): Domain of the benchmark (e.g. 'vision')
        benchmark_url (str): Benchmark reference URL
        benchmark_reference_identifier (str): Reference identifier for the benchmark (e.g., "Ferguson et al., 2024")
        benchmark_bibtex (str): BibTeX citation for the benchmark
        depth (int): Depth in the benchmark hierarchy (e.g., 2)
        number_of_all_children (int): Total number of child benchmarks (e.g., 14)
        overall_order (int): Global ordering of the benchmark
        identifier (str): Unique identifier for the benchmark (e.g., identifier + version; "Ferguson2024_v0")
        short_name (str): Display name for the benchmark (e.g., Ferguson2024)
        benchmark_data_meta (dict, optional): JSON object containing benchmark data metadata
        benchmark_metric_meta (dict, optional): JSON object containing benchmark metric metadata
        benchmark_stimuli_meta (dict, optional): JSON object containing benchmark stimuli metadata
    """

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
    number_of_all_children = models.IntegerField()
    overall_order = models.IntegerField()
    identifier = models.CharField(max_length=255)
    short_name = models.CharField(max_length=255)
    benchmark_id = models.IntegerField(null=True, blank=True)

    # Metadata related fields that returns a JSON object of the above metadata objects. 
    # Columns become keys in the JSON object.
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
    """
    Materialized view for model context.

    This view aggregations all model-related information including scores, layers, and metadata.
    It replaces the previously used `_collect_models()` method in /views/index.py.

    Attributes:
        model_id (int): Primary key, unique identifier for the model
        name (str): Name of the model
        reference_identifier (str, optional): Reference identifier for the model's publication
        url (str, optional): URL to model details or repository
        domain (str): Domain of the model (e.g. 'vision')
        visual_degrees (int, optional): Visual degrees used in model evaluation
        rank (int): Model's ranking
        user (dict, optional): JSON object containing user info with keys:
            - id: User ID
            - email: User email
            - is_staff: Staff status
            - is_active: Active status
            - last_login: Last login timestamp
            - display_name: User's display name
            - is_superuser: Superuser status
        owner (dict, optional): JSON object with owner information (same structure as user)
        submitter (dict, optional): JSON object with submitter information (same structure as user)
        build_status (str): Current build status of the model
        layers (dict, optional): JSON object containing layer information for IT, V1, V2, V4
        scores (dict, optional): Nested JSON object containing benchmark scores and metadata with each dictionary containingkeys:
            - best
            - rank
            - color
            - error
            - median
            - comment
            - benchmark (dict): JSON object of appropriate FinalBenchmarkContext
                - id 
                - url
                - meta
                - year
                - depth
                - author
                - bibtex
                - parent
                - ceiling
                - meta_id
                - version
                - children
                - identifier
                - short_name
                - root_parent
                - ceiling_error
                - overall_order
                - benchmark_type_id
                - reference_identifier
                - number_of_all_children
            - score_raw (float)
            - is_complete
            - start_timestamp (timestamp)
            - end_timestamp (timestamp)
            - score_ceiled_raw (float)
            - score_ceiled (string of score_ceiled_raw with three decimal places)
            - visual_degrees
            - versioned_benchmark_identifier
        competition (str, optional): Competition the model is part of
        public (bool): Whether the model is publicly visible
        model_meta (dict, optional): JSON object containing model metadata including (see modelmeta table; attributes become keys)
    """

    model_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    reference_identifier = models.CharField(max_length=255, null=True, blank=True)
    url = models.CharField(max_length=512, null=True, blank=True)
    domain = models.CharField(max_length=64)
    visual_degrees = models.IntegerField(null=True, blank=True)
    rank = models.IntegerField()
    user = JSONBField(null=True, blank=True) 
    user_id = models.IntegerField(null=True, blank=True)
    owner = JSONBField(null=True, blank=True) 
    submitter = JSONBField(null=True, blank=True) 
    submission_id = models.IntegerField(null=True, blank=True)
    build_status = models.CharField(max_length=64)
    jenkins_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    primary_model_id = models.IntegerField(null=True, blank=True)
    num_secondary_models = models.IntegerField(null=True, blank=True)
    layers = JSONBField(null=True, blank=True)  # keys: IT, V1, V2, V4
    scores = JSONBField(null=True, blank=True)
    competition = models.CharField(max_length=255, null=True, blank=True)
    public = models.BooleanField()
    model_meta = JSONBField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'mv_final_model_context'

    @property
    def id(self):
        """
        Aliases `model_id` as `id` for compatibility with templates expecting `model.id`.
        """
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
        
class FileUploadTracker(models.Model):
    id = models.AutoField(primary_key=True, serialize=False)
    filename = models.CharField(max_length=1000)
    link = models.CharField(max_length=1000)
    upload_datetime =  models.DateTimeField(auto_now_add=True)
    owner = models.ForeignKey(on_delete=models.PROTECT, to='benchmarks.user')
    plugin_type = models.CharField(max_length=100)
    file_size_bytes = models.BigIntegerField(default=0)
    version_id = models.CharField(max_length=255, null=True)
    domain = models.CharField(max_length=100)

    class Meta:
        db_table = 'brainscore_fileuploadtracker'

