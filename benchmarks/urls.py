from django.urls import path
from . import views
from . import view

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', view.Signup.as_view(), name='signup'),
    path('activate/<str:uidb64>/<str:token>', view.Activate.as_view(), name='activate'),
    path('profile/', view.Profile.as_view(), name='login'),
    path('logout/', view.Logout.as_view(), name='logout'),
    path('upload/', view.Upload.as_view(), name='upload'),
    path('password/', view.Password.as_view(), name='password'),
    path('password-change/<str:uidb64>/<str:token>', view.ChangePassword.as_view(), name='change-password'),
    path('public-ajax/', view.PublicAjax.as_view(), name='PublicAjax'),
]