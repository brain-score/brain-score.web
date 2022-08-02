from django.urls import path
import functools

from .views import index, user, model, competition

urlpatterns = [
    # index
    path('', functools.partial(index, domain='vision'), name='index'),
    # user
    path('signup/', user.Signup.as_view(), name='signup'),
    path('activate/<str:uidb64>/<str:token>', user.Activate.as_view(), name='activate'),
    path('profile/', user.Profile.as_view(), name='login'),
    path('logout/', user.Logout.as_view(), name='logout'),
    path('upload/', user.Profile.as_view(), name='upload'),
    path('display-name/', user.DisplayName.as_view(), name='display-name'),
    path('password/', user.Password.as_view(), name='password'),
    path('password-change/<str:uidb64>/<str:token>', user.ChangePassword.as_view(), name='change-password'),
    path('public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),
    # model
    path('model/<int:id>', model.view, name='model'),
    path('competition/', competition.view, name='competition'),
    # language changes
    path('vision/', functools.partial(index, domain='vision'), name='index'),
    path('language/', functools.partial(index, domain='language'), name='index'),
    path('vision/my-submissions/', user.Domain.as_view(), name='vision-information'),
    path('language/my-submissions/', user.Domain.as_view(), name='language-information'),
    path('vision/submit/', user.Upload.as_view(), name='vision-submissions'),
    path('language/submit/', user.Upload.as_view(), name='language-submissions'),
    path('language/resubmit/', user.language_resubmit, name='language_resubmit'),
    path('vision/resubmit/', user.vision_resubmit, name='vision_resubmit'),
]
