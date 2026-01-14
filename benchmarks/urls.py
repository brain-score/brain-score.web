from functools import partial
from django.conf import settings
from django.urls import path
from django.views.generic import RedirectView
from .views import index, user, model, competition2022, competition2024, compare, community, release2_0, brain_model, \
    content_utils, benchmark, explore, leaderboard, report_issue, blog, tutorials
from .utils import show_token, refresh_cache


# all currently supported Brain-Score domains:
supported_domains = ["vision", "language"]

non_domain_urls = [
    # landing
    path('', user.LandingPage.as_view(), name='landing_page'),
    path('/', user.LandingPage.as_view(), name='landing_page'),

    # global pages - default to vision domain
    path('explore/', RedirectView.as_view(url='/vision/explore/', permanent=False), name='default-explore'),
    path('compare/', RedirectView.as_view(url='/vision/compare/', permanent=False), name='default-compare'),
    path('leaderboard/', RedirectView.as_view(url='/vision/leaderboard/', permanent=False), name='default-leaderboard'),
    path('sponsors/', user.Sponsors.as_view(), name='sponsors'),
    path('faq/', user.Faq.as_view(), name='faq'),
    path('community', partial(community.view), name='community'),
    path('community/join/slack', community.JoinSlack.as_view(), name="join_slack"),
    path('community/join/mailing-list', community.JoinMailingList.as_view(), name="join_mailing_list"),
    path('unsubscribe', partial(community.Unsubscribe.as_view()), name='unsubscribe'),

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
    path('profile/refresh-leaderboard/', user.RefreshLeaderboardAjax.as_view(), name='RefreshLeaderboardAjax'),
    path('profile/submit/', user.Upload.as_view(domain="vision"), name=f'vision-submit'),
    path('profile/resubmit/', partial(user.resubmit, domain="vision"), name='vision-resubmit'),
    path('profile/logout/', user.Logout.as_view(domain="vision"), name='vision-logout'),

    # Large File upload page:
    path('profile/large_file_upload/', user.LargeFileUpload.as_view(), name=f'large_file_upload'),
    path('profile/large_file_upload/finalize/', user.FinalizeUpload.as_view(), name='finalize_upload'),

    # central tutorial page, constant across all Brain-Score domains
    path('tutorials/', user.Tutorials.as_view(tutorial_type="tutorial"), name='tutorial'),
    path('tutorials/troubleshooting', user.Tutorials.as_view(tutorial_type="troubleshooting"),
         name='tutorial-troubleshooting'),
    # - model tutorials
    path('tutorials/models', user.Tutorials.as_view(plugin="models", tutorial_type="models"), name='model-tutorial'),
    path('tutorials/models/quickstart', user.Tutorials.as_view(plugin="models", tutorial_type="quickstart"),
         name='model-tutorial-quickstart'),
    path('tutorials/models/deepdive_1', user.Tutorials.as_view(plugin="models", tutorial_type="deepdive_1"),
         name='model-tutorial-deepdive-1'),
    path('tutorials/models/deepdive_2', user.Tutorials.as_view(plugin="models", tutorial_type="deepdive_2"),
         name='model-tutorial-deepdive-2'),
    path('tutorials/models/deepdive_3', user.Tutorials.as_view(plugin="models", tutorial_type="deepdive_3"),
         name='model-tutorial-deepdive-3'),
    # - benchmark tutorials
    path('tutorials/benchmarks', user.Tutorials.as_view(plugin="benchmarks", tutorial_type="benchmarks"),
         name='benchmark-tutorial'),
    path('tutorials/benchmarks/package_data', user.Tutorials.as_view(plugin="benchmarks", tutorial_type="package_data"),
         name='benchmark-package-data'),
    path('tutorials/benchmarks/create_benchmark',
         user.Tutorials.as_view(plugin="benchmarks", tutorial_type="create_benchmark"),
         name='benchmark-create-benchmark'),
    # - new markdown-based benchmark tutorials
    path('tutorials/benchmarks/<slug:slug>/', tutorials.benchmark_tutorial_detail,
         name='benchmark-tutorial-detail'),
    # - brain model explanation
    path('brain_model', brain_model.view, name='brain-model'),

    # competitions and releases
    path('competition/', competition2024.view, name='competition'),
    path('competition2024/', competition2024.view, name='competition2024'),
    path('competition2022/', competition2022.view, name='competition2022'),
    path('release2.0/', release2_0.view, name='release2.0'),

    # Add the refresh_cache URL and make domain specific

    # Triggers the refresh_cache function in utils.py when URL is visited
    path('refresh_cache/<str:domain>/', refresh_cache, name='refresh_cache'),
    
    # Report issue endpoint
    path('report-issue/', report_issue.report_issue_view, name='report_issue'),
    
    # Blog endpoints
    path('blog/', blog.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', blog.blog_detail, name='blog_detail'),
    path('blog/category/<slug:slug>/', blog.blog_category, name='blog_category'),
    path('blog/tag/<str:tag>/', blog.blog_tag, name='blog_tag'),
]

all_domain_urls = [non_domain_urls]

for domain in supported_domains:
    domain_urls = [
        path(f'{domain}/', RedirectView.as_view(url=f'/{domain}/leaderboard/', permanent=False), name='index'),
        path(f'{domain}/leaderboard/', partial(leaderboard.ag_grid_leaderboard_shell, domain=domain),
             name=f'{domain}-leaderboard'),
        path(f'{domain}/leaderboard/content/', partial(leaderboard.ag_grid_leaderboard_content, domain=domain),
             name=f'{domain}-leaderboard-content'),
        path(f'{domain}/leaderboard/snapshots/manifest.json', partial(leaderboard.wayback_snapshot_manifest, domain=domain),
             name=f'{domain}-snapshot-manifest'),
        path(f'profile/{domain}/', user.Profile.as_view(domain=domain), name=f'{domain}-information'),
        path(f'profile/{domain}/submit/', user.Upload.as_view(domain=domain), name=f'{domain}-submit'),
        path(f'profile/<str:domain>/resubmit/', partial(user.resubmit, domain=domain), name=f'resubmit'),
        path(f'profile/{domain}/logout/', user.Logout.as_view(domain=domain), name=f'{domain}-logout'),

        path(f'{domain}/explore/', partial(explore.view, domain=domain), name=f'{domain}-explore'),
        path(f'model/<str:domain>/<int:id>', partial(model.view, domain=domain), name='model-view'),
        path(f'benchmark/<str:domain>/<int:id>', partial(benchmark.view, domain=domain), name='benchmark-view'),
        path(f'{domain}/compare/', partial(compare.view, domain=domain), name='{domain}-compare'),
    ]
    all_domain_urls.append(domain_urls)

if settings.DEBUG:
    all_domain_urls.append([
        path('content_utils/sample_benchmark_images/', content_utils.sample_benchmark_images, name='sample_benchmark_images'),
        path('debug/show_token/', show_token, name='show_token'),  # Show token required to trigger cache refresh
    ])

# collapse all domains into 1D list (from 2D)
urlpatterns = sum(all_domain_urls, [])
