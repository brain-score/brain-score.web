from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from benchmarks.models import BenchmarkInstance, BenchmarkType, Model, Score, User
from benchmarks.views import benchmark
from benchmarks.views.index import representative_color


class TestRepresentativeColor(SimpleTestCase):
    def test_zero_range_matches_best_score(self):
        self.assertEqual(representative_color(0.3, min_value=0.3, max_value=0.3),
                         representative_color(0.9, min_value=0.1, max_value=0.9))


@override_settings(ROOT_URLCONF='benchmarks.urls')
class TestBenchmarkPage(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/')

    def test_missing_benchmark_is_404(self):
        with self.assertRaises(Http404):
            benchmark.view(self.request, id=999999, domain='vision')

    def test_single_public_score_renders(self):
        owner = User.objects.create(email='owner@example.com')
        benchmark_type = BenchmarkType.objects.create(identifier='Example2026.V1-cka', domain='vision', owner=owner)
        instance = BenchmarkInstance.objects.create(benchmark_type=benchmark_type, version=1)
        model = Model.objects.create(name='example-model', owner=owner, domain='vision', public=True)
        Score.objects.create(benchmark=instance, model=model, score_raw=0.34, score_ceiled=0.34,
                             start_timestamp=timezone.now())

        response = benchmark.view(self.request, id=instance.id, domain='vision')

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'example-model', response.content)
