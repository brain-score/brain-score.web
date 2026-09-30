"""Routes exercised by the isolated metadata and comparison test suite."""
from django.urls import path
from benchmarks.views import compare, model, metadata_edit

urlpatterns = [
    path('model/<str:domain>/<int:id>/metadata/edit/', metadata_edit.edit, name='metadata-edit'),
    path('model/<str:domain>/<int:id>/metadata/preview/<int:number>/', metadata_edit.preview, name='metadata-preview'),
    path('metadata/proposals/<str:key>/', metadata_edit.review, name='metadata-review'),
    path('metadata/github/callback/', metadata_edit.callback, name='metadata-github-callback'),
    path('model/<str:domain>/<int:id>', model.view),
    path('vision/compare/', compare.view, {'domain': 'vision'}, name='vision-compare'),
    path('vision/compare/data/', compare.dashboard_data, {'domain': 'vision'}, name='vision-compare-data'),
    path('vision/compare/trend_pair/', compare.trend_pair, {'domain': 'vision'}, name='vision-compare-trend-pair'),
]
