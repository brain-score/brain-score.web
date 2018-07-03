from django.db import models


class CandidateModel(models.Model):
    name = models.CharField(max_length=200)
    brain_score = models.FloatField()
    imagenet_top1 = models.FloatField()
    v4 = models.FloatField()
    it = models.FloatField()
    behavior = models.FloatField()

    def __str__(self):
        return self.__class__.__name__ \
               + "[" + ",".join("{}={}".format(field, value) for field, value in vars(self).items()) + "]"
