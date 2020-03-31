from django.db import models
from django.contrib.auth.models import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.utils.translation import ugettext_lazy as _
import datetime


class MyUserManager(BaseUserManager):
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
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=False,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )

    USERNAME_FIELD = 'email'
    objects = MyUserManager()

    datefield1 = models.DateField(("Date"), default=datetime.datetime(2019, 1, 1))
    datefield2 = models.DateField(("Date"), default=datetime.datetime(2019, 1, 1))
    datefield3 = models.DateField(("Date"), default=datetime.datetime(2019, 1, 1))

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.email

    def get_short_name(self):
        return self.email

    def get_lowest_datefield(self):
        lowest_date = self.datefield1
        if lowest_date < self.datefield2:
            lowest_date = self.datefield2
        if lowest_date < self.datefield3:
            lowest_date = self.datefield3
        return lowest_date

    def set_lowest_datefield(self, date):
        lowest_date = self.get_lowest_datefield()
        if lowest_date == self.datefield1:
            self.datefield1 = models.DateField(("Date"), default=date)
        elif lowest_date == self.datefield2:
            self.datefield2 = models.DateField(("Date"), default=date)
        elif lowest_date < self.datefield3:
            self.datefield3 = models.DateField(("Date"), default=date)


def generic_repr(obj):
    return obj.__class__.__name__ \
           + "[" + ",".join(f"{field}={value}" for field, value in vars(obj).items()) + "]"


class Benchmark(models.Model):
    name = models.CharField(max_length=200, primary_key=True)
    ceiling = models.FloatField(default=0, null=True)  # null for average "benchmark"
    ceiling_error = models.FloatField(default=0, null=True)
    parent = models.CharField(max_length=200, null=True)
    link = models.CharField(max_length=1000, null=True)
    version = models.IntegerField(null=True)

    def __repr__(self):
        return generic_repr(self)


class ModelReference(models.Model):
    model = models.CharField(max_length=200, primary_key=True)
    short_reference = models.CharField(max_length=200)
    link = models.CharField(max_length=200)
    bibtex = models.CharField(max_length=2000)

    def __repr__(self):
        return generic_repr(self)


class ModelMeta(models.Model):
    class Meta:
        unique_together = (('model', 'key'),)

    model = models.CharField(max_length=200)
    key = models.CharField(max_length=200)
    value = models.CharField(max_length=200)

    def __repr__(self):
        return generic_repr(self)


class Score(models.Model):
    class Meta:
        unique_together = (('model', 'benchmark'),)

    model = models.CharField(max_length=200, db_index=True)
    benchmark = models.CharField(max_length=200, db_index=True)
    score_raw = models.FloatField(default=0, null=True)
    score_ceiled = models.FloatField(default=0, null=True)
    error = models.FloatField(default=0, null=True)
    layer = models.CharField(max_length=200, default=None, null=True)

    def __repr__(self):
        return generic_repr(self)
