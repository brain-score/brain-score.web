from django.urls import path
import functools

from .views import index, user, model, competition2022, competition2024, compare, community, release2_0

# all currently supported Brain-Score domains:
supported_domains = ["vision", "language"]

non_domain_urls = [
    # landing
    path('', user.LandingPage.as_view(), name='landing_page'),
    path('/', user.LandingPage.as_view(), name='landing_page'),

    # global pages
    path('compare', functools.partial(compare.view, domain="vision"), name='compare'),
    path('sponsors/', user.Sponsors.as_view(), name='sponsors'),
    path('faq/', user.Faq.as_view(), name='faq'),
    path('community', functools.partial(community.view), name='community'),
    path('community/join/slack', community.JoinSlack.as_view(), name="join_slack"),
    path('community/join/mailing-list', community.JoinMailingList.as_view(), name="join_mailing_list"),
    path('unsubscribe', functools.partial(community.Unsubscribe.as_view()), name='unsubscribe'),

    # user
    path('signup/', user.Signup.as_view(), name='signup'),
    path('profile/logout/', user.Logout.as_view(), name='logout'),
    path('activate/<str:uidb64>/<str:token>', user.Activate.as_view(), name=f'activate'),
    path('display-name/', user.DisplayName.as_view(), name='display-name'),
    path('password/', user.Password.as_view(), name='password'),
    path('password-change/<str:uidb64>/<str:token>', user.ChangePassword.as_view(), name=f'change-password'),

    # central profile page, constant across all Brain-Score domains
    path('profile/', user.ProfileAccount.as_view(), name='default-profile'),
    path('profile/public-ajax/', user.PublicAjax.as_view(), name='PublicAjax'),

    # need navbar links when on /profile. Default to vision.
    # this is a **temporary** fix until the new UI landing page is live.
    path('profile/', user.Profile.as_view(domain="vision"), name='default-profile-navbar'),
    path('profile/submit/', user.Upload.as_view(domain="vision"), name=f'vision-submit'),
    path('profile/resubmit/', functools.partial(user.resubmit, domain="vision"), name='vision-resubmit'),
    path('profile/logout/', user.Logout.as_view(domain="vision"), name='vision-logout'),

    # central tutorial page, constant across all Brain-Score domains
    path('tutorials/', user.Tutorials.as_view(tutorial_type="tutorial"), name='tutorial'),
    path('tutorials/troubleshooting', user.Tutorials.as_view(tutorial_type="troubleshooting"),
         name='tutorial-troubleshooting'),

    path('tutorials/models', user.Tutorials.as_view(plugin="models", tutorial_type="models"), name='model-tutorial'),
    path('tutorials/models/quickstart', user.Tutorials.as_view(plugin="models", tutorial_type="quickstart"),
         name='model-tutorial-quickstart'),
    path('tutorials/models/deepdive_1', user.Tutorials.as_view(plugin="models", tutorial_type="deepdive_1"),
         name='model-tutorial-deepdive-1'),
    path('tutorials/models/deepdive_2', user.Tutorials.as_view(plugin="models", tutorial_type="deepdive_2"),
         name='model-tutorial-deepdive-2'),
    path('tutorials/models/deepdive_3', user.Tutorials.as_view(plugin="models", tutorial_type="deepdive_3"),
         name='model-tutorial-deepdive-3'),

    # benchmark tutorials:
    path('tutorials/benchmarks', user.Tutorials.as_view(plugin="benchmarks", tutorial_type="benchmarks"),
         name='benchmark-tutorial'),
    path('tutorials/benchmarks/package_data', user.Tutorials.as_view(plugin="benchmarks", tutorial_type="package_data"),
         name='benchmark-package-data'),
    path('tutorials/benchmarks/create_benchmark',
         user.Tutorials.as_view(plugin="benchmarks", tutorial_type="create_benchmark"),
         name='benchmark-create-benchmark'),

    # competitions and releases
    path('competition/', competition2024.view, name='competition'),
    path('competition2024/', competition2024.view, name='competition2024'),
    path('competition2022/', competition2022.view, name='competition2022'),
    path('release2.0/', release2_0.view, name='release2.0'),
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
        path(f'{domain}/compare/', functools.partial(compare.view, domain=domain), name='compare'),
    ]
    all_domain_urls.append(domain_urls)

# collapse all domains into 1D list (from 2D)
urlpatterns = sum(all_domain_urls, [])
