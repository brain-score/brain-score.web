from django.contrib import admin

from .models import User, Reference, BenchmarkType, BenchmarkInstance, Submission, Model, Score

admin.site.register(User)
admin.site.register(Reference)
admin.site.register(BenchmarkType)
admin.site.register(BenchmarkInstance)
admin.site.register(Submission)
admin.site.register(Model)
admin.site.register(Score)
