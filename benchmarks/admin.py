from django.contrib import admin

from .models import Score, ModelReference, Benchmark, User

admin.site.register(Score)
admin.site.register(ModelReference)
admin.site.register(Benchmark)
admin.site.register(User)