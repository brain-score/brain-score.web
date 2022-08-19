from django.urls import path
import functools

from .views import index, user, model, competition

urlpatterns = [
    # index
    path('', functools.partial(index, domain='vision'), name='index'),
    # user
    path('signup/', user.Signup.as_view(), name='signup'),
    path('activate/<str:uidb64>/<str:token>', user.Activate.as_view(), name='activate'),
    path('logout/', user.Logout.as_view(domain="vision"), name='logout'),
    path('upload/', user.Profile.as_view(domain="vision"), name='upload'),
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
    path('profile/vision/', user.Profile.as_view(domain="vision"), name='vision-information'),
    path('profile/language/', user.Profile.as_view(domain="language"), name='language-information'),
    path('profile/vision/submit/', user.Upload.as_view(domain="vision"), name='vision-submit'),
    path('profile/language/submit/', user.Upload.as_view(domain="language"), name='language-submit'),
    path('profile/vision/resubmit/', user.resubmit, name='vision_resubmit'),
    path('profile/language/resubmit/', user.resubmit, name='language_resubmit'),
    path('profile/vision/logout/',  user.Logout.as_view(domain="vision"), name='vision-logout'),
    path('profile/language/logout/', user.Logout.as_view(domain="language"), name='language-logout'),




]
