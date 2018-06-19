from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('frontend.urls')),
    path('frontend/', include('frontend.urls')),
    path('admin/', admin.site.urls),
]
