from django.contrib import admin

from .models import Score, Model, Benchmark, User, Submission

admin.site.register(Score)
admin.site.register(Model)
admin.site.register(Benchmark)
admin.site.register(User)
admin.site.register(Submission)
