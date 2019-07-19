from django.db import models


def generic_repr(obj):
    return obj.__class__.__name__ \
           + "[" + ",".join("{}={}".format(field, value) for field, value in vars(obj).items()) + "]"


class Benchmark(models.Model):
    name = models.CharField(max_length=200, primary_key=True)
    ceiling = models.FloatField(default=0, null=True)  # null for average "benchmark"
    ceiling_error = models.FloatField(default=0, null=True)
    parent = models.CharField(max_length=200, null=True)
    link = models.CharField(max_length=1000, null=True)

    def __repr__(self):
        return generic_repr(self)


class ModelReference(models.Model):
    model = models.CharField(max_length=200, primary_key=True)
    short_reference = models.CharField(max_length=200)
    link = models.CharField(max_length=200)
    bibtex = models.CharField(max_length=2000)

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
