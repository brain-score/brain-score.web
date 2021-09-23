from django.test import TestCase

from benchmarks.views.user import split_identifier_version


class TestTable(TestCase):
    fixtures = ['fixture-benchmarkreferences.json', 'fixture-benchmarktypes.json', 'fixture-benchmarkinstances.json',
                'fixture-users.json', 'fixture-modelreferences.json', 'fixture-models.json',
                'fixture-scores.json']

    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/")
        self.assertEqual(resp.status_code, 200)

    def test_num_rows(self):
        resp = self.client.get("http://localhost:8000/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr>")
        self.assertEqual(num_rows, 1 + 79)


class TestIdentifierVersionSplit(TestCase):
    def test_MajajHong(self):
        benchmark_specifier = 'dicarlo.MajajHong2015.V4-pls_v3'
        identifier, version = split_identifier_version(benchmark_specifier)
        self.assertEqual(identifier, 'dicarlo.MajajHong2015.V4-pls')
        self.assertEqual(version, '3')

    def test_RingachVariance(self):
        benchmark_specifier = 'dicarlo.Marques2020_Ringach2002-circular_variance_v1'
        identifier, version = split_identifier_version(benchmark_specifier)
        self.assertEqual(identifier, 'dicarlo.Marques2020_Ringach2002-circular_variance')
        self.assertEqual(version, '1')
