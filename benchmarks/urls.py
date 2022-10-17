from django.urls import path
import functools

from .views import index, user, model, competition

urlpatterns = [
    # index
    path('', functools.partial(index, domain='vision'), name='index'),
    path('/', functools.partial(index, domain='vision'), name='index'),
    # user
    path('logout/', user.Logout.as_view(domain="vision"), name='logout'),
    path('upload/', user.Profile.as_view(domain="vision"), name='upload'),
    path('public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),
    path('competition/', competition.view, name='competition'),

    # language changes
    path('vision/', functools.partial(index, domain='vision'), name='index'),
    path('language/', functools.partial(index, domain='language'), name='index'),
    path('password/vision/',  user.Password.as_view(domain="vision"), name='password-vision'),
    path('password/language/',  user.Password.as_view(domain="language"), name='password-language'),
    path('password-change/vision/<str:uidb64>/<str:token>', user.ChangePassword.as_view(domain="vision"), name='change-password-vision'),
    path('password-change/language/<str:uidb64>/<str:token>', user.ChangePassword.as_view(domain="language"), name='change-password-language'),
    path('signup/vision', user.Signup.as_view(domain="vision"), name='vision-signup'),
    path('signup/language', user.Signup.as_view(domain="language"), name='language-signup'),
    path('activate/vision/<str:uidb64>/<str:token>', user.Activate.as_view(domain="vision"), name='activate-vision'),
    path('activate/language/<str:uidb64>/<str:token>', user.Activate.as_view(domain="language"), name='activate-language'),
    path('display-name/vision', user.DisplayName.as_view(domain="vision"), name='display-name-vision'),
    path('display-name/language', user.DisplayName.as_view(domain="language"), name='display-name-language'),
    path('profile/vision/', user.Profile.as_view(domain="vision"), name='vision-information'),
    path('profile/language/', user.Profile.as_view(domain="language"), name='language-information'),
    path('profile/vision/submit/', user.Upload.as_view(domain="vision"), name='vision-submit'),
    path('profile/language/submit/', user.Upload.as_view(domain="language"), name='language-submit'),
    path('profile/vision/resubmit/', user.resubmit, name='vision_resubmit'),
    path('profile/language/resubmit/', user.resubmit, name='language_resubmit'),
    path('profile/vision/logout/',  user.Logout.as_view(domain="vision"), name='vision-logout'),
    path('profile/language/logout/', user.Logout.as_view(domain="language"), name='language-logout'),
    path('model/vision/<int:id>', model.view, name='model-vision'),
    path('model/language/<int:id>', model.view, name='model-language'),




]
