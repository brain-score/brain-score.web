from django.urls import path
import functools

from .views import index, user, model, competition

# all currently supported Brain-Score domains:
supported_domains = ["vision", "language"]

non_domain_urls = [

        # landing page (preview mode)
        path('2023/', user.LandingPage.as_view(), name='landing_page'),

        path('', functools.partial(index, domain="vision"), name='index'),
        path('/', functools.partial(index, domain="vision"), name='index'),

        # user
        path('competition/', competition.view, name='competition'),
        path('signup/', user.Signup.as_view(), name='signup'),
        path('profile/logout/', user.Logout.as_view(), name='logout'),
        path('activate/<str:uidb64>/<str:token>', user.Activate.as_view(), name=f'activate'),
        path('display-name/', user.DisplayName.as_view(), name='display-name'),
        path('password/',  user.Password.as_view(), name='password'),
        path('password-change/<str:uidb64>/<str:token>', user.ChangePassword.as_view(), name=f'change-password'),

        # central profile page, constant across all Brain-Score domains
        path('profile/', user.ProfileAccount.as_view(), name='default-profile'),
        path('profile/public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),

        # central tutorial page, constant across all Brain-Score domains
        path('tutorial/', user.Tutorial.as_view(tutorial_type=""), name='tutorial'),
        path('tutorial/quickstart', user.Tutorial.as_view(tutorial_type="_quickstart"), name='tutorial-quickstart'),
        path('tutorial/deepdive_1', user.Tutorial.as_view(tutorial_type="_deepdive_1"), name='tutorial-deepdive-1'),
        path('tutorial/deepdive_2', user.Tutorial.as_view(tutorial_type="_deepdive_2"), name='tutorial-deepdive-2'),
        path('tutorial/deepdive_3', user.Tutorial.as_view(tutorial_type="_deepdive_3"), name='tutorial-deepdive-3'),
        path('tutorial/deepdive_3', user.Tutorial.as_view(tutorial_type="_deepdive_4"), name='tutorial-deepdive-4'),


        # need navbar links when on /profile. Default to vision.
        # this is a **temporary** fix until the new UI landing page is live.
        path('profile//', user.Profile.as_view(domain="vision"), name='default-profile-navbar'),
        path('profile//submit/', user.Upload.as_view(domain="vision"), name=f'vision-submit'),
        path('profile//resubmit/', functools.partial(user.resubmit, domain="vision"), name='vision-resubmit'),
        path('profile//logout/', user.Logout.as_view(domain="vision"), name='vision-logout'),
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
