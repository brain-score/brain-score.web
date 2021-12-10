from django.test import TestCase

from benchmarks.views.user import split_identifier_version

ALL_FIXTURES = ['fixture-benchmarkreferences.json', 'fixture-benchmarktypes.json', 'fixture-benchmarkinstances.json',
                'fixture-users.json', 'fixture-modelreferences.json', 'fixture-submissions.json', 'fixture-models.json',
                'fixture-scores.json']


class TestTable(TestCase):
    fixtures = ALL_FIXTURES

    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/")
        self.assertEqual(resp.status_code, 200)

    def test_num_rows(self):
        resp = self.client.get("http://localhost:8000/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr>")
        self.assertEqual(num_rows, 1 + 78)


class TestCompetitionTable(TestCase):
    fixtures = ALL_FIXTURES

    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/competition/")
        self.assertEqual(resp.status_code, 200)

    def test_num_rows(self):
        resp = self.client.get("http://localhost:8000/competition/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr>")
        self.assertEqual(num_rows, 1 + 7)


class TestModel(TestCase):
    fixtures = ALL_FIXTURES

    def test_public_model(self):
        resp = self.client.get("http://localhost:8000/model/1")
        self.assertEqual(resp.status_code, 200)

    def test_non_public_model(self):
        resp = self.client.get("http://localhost:8000/model/2")
        self.assertEqual(resp.status_code, 404)


class TestIdentifierVersionSplit(TestCase):
    def test_MajajHong(self):
        versioned_benchmark_identifier = 'dicarlo.MajajHong2015.V4-pls_v3'
        identifier, version = split_identifier_version(versioned_benchmark_identifier)
        self.assertEqual(identifier, 'dicarlo.MajajHong2015.V4-pls')
        self.assertEqual(version, '3')

    def test_RingachVariance(self):
        versioned_benchmark_identifier = 'dicarlo.Marques2020_Ringach2002-circular_variance_v1'
        identifier, version = split_identifier_version(versioned_benchmark_identifier)
        self.assertEqual(identifier, 'dicarlo.Marques2020_Ringach2002-circular_variance')
        self.assertEqual(version, '1')
