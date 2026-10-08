from django.http import Http404
from django.test import RequestFactory, TestCase

from benchmarks.views import benchmark


class TestBenchmarkPage(TestCase):
    def setUp(self):
        self.request = RequestFactory().get('/')

    def test_missing_benchmark_is_404(self):
        with self.assertRaises(Http404):
            benchmark.view(self.request, id=999999, domain='vision')
