from django.urls import path

from .views import index
from .views import user

urlpatterns = [
    path('', index, name='index'),
    path('signup/', user.Signup.as_view(), name='signup'),
    path('activate/<str:uidb64>/<str:token>', user.Activate.as_view(), name='activate'),
    path('profile/', user.Profile.as_view(), name='login'),
    path('logout/', user.Logout.as_view(), name='logout'),
    path('upload/', user.Upload.as_view(), name='upload'),
    path('password/', user.Password.as_view(), name='password'),
    path('password-change/<str:uidb64>/<str:token>', user.ChangePassword.as_view(), name='change-password'),
    path('public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),
    path('resubmit/', user.resubmit, name='resubmit'),
]
