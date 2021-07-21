from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import ugettext_lazy as _


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
    reference = models.ForeignKey(Reference, on_delete=models.PROTECT, null=True)  # null for parents
    order = models.IntegerField(default=999)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)  # null: average benchmark has no parent
    visible = models.BooleanField(default=False, null=False)

    def __repr__(self):
        return generic_repr(self)

    class Meta:
        db_table = 'brainscore_benchmarktype'


class BenchmarkInstance(models.Model):
    class Meta:
        unique_together = (('benchmark_type', 'version'),)

    benchmark_type = models.ForeignKey(BenchmarkType, on_delete=models.PROTECT)
    version = models.IntegerField()
    ceiling = models.FloatField(default=0, null=True)
    ceiling_error = models.FloatField(null=True)

    def __repr__(self):
        return generic_repr(self)

    def natural_key(self):
        return self.benchmark_type.identifier, self.version

    class BenchmarkInstanceManager(models.Manager):
        def get_by_natural_key(self, identifier, version):
            return self.get(benchmark_type__identifier=identifier, version=version)

    objects = BenchmarkInstanceManager()

    class Meta:
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
    public = models.BooleanField(default=False)

    def __repr__(self):
        return generic_repr(self)

    def natural_key(self):
        return self.name, self.owner

    class ModelManager(models.Manager):
        def get_by_natural_key(self, name, owner=None):
            kwargs = dict(name=name)
            if owner is not None:  # if owner is passed, explicitly use it to link, otherwise try without
                kwargs['owner'] = owner
            return self.get(**kwargs)

    objects = ModelManager()

    class Meta:
        db_table = 'brainscore_model'


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