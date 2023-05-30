from django.urls import path
import functools

from .views import index, user, model, competition

# all currently supported Brain-Score domains:
supported_domains = ["vision", "language"]

non_domain_urls = [
        path('', functools.partial(index, domain='vision'), name='index'),
        path('/', functools.partial(index, domain='vision'), name='index'),
        # user
        path('logout/', user.Logout.as_view(domain="vision"), name='logout'),
        path('upload/', user.Profile.as_view(domain="vision"), name='upload'),
        path('public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),
        path('competition/', competition.view, name='competition'),

        # default profile is vision
        path('profile/', user.Profile.as_view(domain="vision"), name='default-profile'),
]

all_domain_urls = [non_domain_urls]

for domain in supported_domains:
    domain_urls = [
        path(f'{domain}/', functools.partial(index, domain=domain), name='index'),
        path(f'password/{domain}/',  user.Password.as_view(domain=domain), name=f'password-{domain}'),
        path(f'password-change/{domain}/<str:uidb64>/<str:token>', user.ChangePassword.as_view(domain=domain), name=f'change-password-{domain}'),
        path(f'signup/{domain}', user.Signup.as_view(domain=domain), name=f'{domain}-signup'),
        path(f'activate/{domain}/<str:uidb64>/<str:token>', user.Activate.as_view(domain=domain), name=f'activate-{domain}'),
        path(f'display-name/<str:domain>', user.DisplayName.as_view(domain=domain), name=f'display-name'),
        path(f'profile/{domain}/', user.Profile.as_view(domain=domain), name=f'{domain}-information'),
        path(f'profile/{domain}/submit/', user.Upload.as_view(domain=domain), name=f'{domain}-submit'),
        path(f'profile/<str:domain>/resubmit/', functools.partial(user.resubmit, domain=domain), name=f'resubmit'),
        path(f'profile/{domain}/logout/',  user.Logout.as_view(domain=domain), name=f'{domain}-logout'),
        path(f'model/<str:domain>/<int:id>', functools.partial(model.view, domain=domain), name='model-view'),
    ]
    all_domain_urls.append(domain_urls)

# collapse all domains into 1D list (from 2D)
urlpatterns = sum(all_domain_urls, [])

