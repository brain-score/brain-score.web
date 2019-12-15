from django.urls import path
from . import views
from . import view

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', view.Signup.as_view(), name='signup'),
    path('activate/<str:uidb64>/<str:token>', view.Activate.as_view(), name='activate'),
    path('profile/', view.Profile.as_view(), name='login'),
    path('login/', view.Login.as_view(), name='login'),
    path('logout/', view.Logout.as_view(), name='logout'),
    path('upload/', view.Upload.as_view(), name='upload')
]
