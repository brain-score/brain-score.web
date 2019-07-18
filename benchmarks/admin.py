from django.contrib import admin

from .models import Score, ModelReference, Benchmark

admin.site.register(Score)
admin.site.register(ModelReference)
admin.site.register(Benchmark)
