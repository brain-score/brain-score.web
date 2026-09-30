"""Routes exercised by the isolated metadata and comparison test suite."""
from django.urls import path
from benchmarks.views import compare, model

urlpatterns = [
    path('model/<str:domain>/<int:id>', model.view),
    path('vision/compare/', compare.view, {'domain': 'vision'}, name='vision-compare'),
    path('vision/compare/data/', compare.dashboard_data, {'domain': 'vision'}, name='vision-compare-data'),
    path('vision/compare/trend_pair/', compare.trend_pair, {'domain': 'vision'}, name='vision-compare-trend-pair'),
]
