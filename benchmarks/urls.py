from django.urls import path
import functools

from .views import index, user, model, competition

# all currently supported Brain-Score domains:
supported_domains = ["vision", "language"]

non_domain_urls = [

        # landing (main) page
        path('', user.LandingPage.as_view(), name='landing_page'),
        path('', user.LandingPage.as_view(), name='landing_page'),

        # user
        path('public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),
        path('competition/', competition.view, name='competition'),
        path('signup/', user.Signup.as_view(), name='signup'),
        path('profile/logout/', user.Logout.as_view(), name='logout'),
        path('activate/<str:uidb64>/<str:token>', user.Activate.as_view(), name=f'activate'),
        path('display-name/', user.DisplayName.as_view(), name='display-name'),
        path('password/',  user.Password.as_view(), name='password'),
        path('password-change/<str:uidb64>/<str:token>', user.ChangePassword.as_view(), name=f'change-password'),

        # central profile page, constant across all Brain-Score domains
        path('profile/', user.ProfileAccount.as_view(), name='default-profile'),
]

all_domain_urls = [non_domain_urls]

for domain in supported_domains:
    domain_urls = [
        path(f'{domain}/', functools.partial(index, domain=domain), name='index'),
        path(f'profile/{domain}/', user.Profile.as_view(domain=domain), name=f'{domain}-information'),
        path(f'profile/{domain}/submit/', user.Upload.as_view(domain=domain), name=f'{domain}-submit'),
        path(f'profile/<str:domain>/resubmit/', functools.partial(user.resubmit, domain=domain), name=f'resubmit'),
        path(f'profile/{domain}/logout/', user.Logout.as_view(domain=domain), name=f'{domain}-logout'),
        path(f'model/<str:domain>/<int:id>', functools.partial(model.view, domain=domain), name='model-view'),
    ]
    all_domain_urls.append(domain_urls)

# collapse all domains into 1D list (from 2D)
urlpatterns = sum(all_domain_urls, [])

