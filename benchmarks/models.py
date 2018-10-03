from django.db import models


class CandidateModel(models.Model):
    name = models.CharField(max_length=200)
    brain_score = models.FloatField()
    imagenet_top1 = models.FloatField()
    V4 = models.FloatField()
    IT = models.FloatField()
    behavior = models.FloatField()
    V4_layer = models.CharField(max_length=500, default=None)
    IT_layer = models.CharField(max_length=500, default=None)
    behavior_layer = models.CharField(max_length=500, default=None)
    paper_link = models.CharField(max_length=200)
    paper_identifier = models.CharField(max_length=200)

    def __str__(self):
        return self.__class__.__name__ \
               + "[" + ",".join("{}={}".format(field, value) for field, value in vars(self).items()) + "]"
