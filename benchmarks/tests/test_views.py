import pytest
from django.test import TestCase

from benchmarks.views.index import _get_benchmark_shortname
from benchmarks.views.user import split_identifier_version

ALL_FIXTURES = ['fixture-benchmarkreferences.json', 'fixture-benchmarktypes.json',
                'fixture-benchmarkmeta.json', 'fixture-benchmarkinstances.json',
                'fixture-users.json', 'fixture-modelreferences.json', 'fixture-submissions.json', 'fixture-models.json',
                'fixture-scores.json', 'fixture-benchmarktypes-language.json', 'fixture-benchmarkmeta-language.json',
                'fixture-benchmarkinstances-language.json', 'fixture-users-language.json',
                'fixture-models-language.json', 'fixture-scores-language.json']


class TestTable(TestCase):
    fixtures = ALL_FIXTURES

    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/")
        self.assertEqual(resp.status_code, 200)

    # After UI update,  http://localhost:8000 has no leaderboard anymore.
    # vision is used here, language tested below.
    def test_num_rows(self):
        resp = self.client.get("http://localhost:8000/vision/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr")
        self.assertEqual(num_rows, 1 + 78)


@pytest.skip("2022 competition is over")
class TestCompetitionTable(TestCase):
    fixtures = ALL_FIXTURES

    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/competition2022/")
        self.assertEqual(resp.status_code, 200)

    def test_num_rows(self):
        resp = self.client.get("http://localhost:8000/competition2022/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr")
        self.assertEqual(num_rows, (1 + 9) * 3)  # header, 9 different models, 3 tracks

    def test_num_secondary_models(self):
        resp = self.client.get("http://localhost:8000/competition2022/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("is-secondary-model")
        num_total_models = 9 * 3  # 9 different models, 3 tracks
        num_primary_models = 4 * 3  # 4 different users, 3 tracks
        self.assertEqual(num_rows, num_total_models - num_primary_models)


class TestModel(TestCase):
    fixtures = ALL_FIXTURES

    def test_public_model(self):
        resp = self.client.get("http://localhost:8000/model/vision/1")
        self.assertEqual(resp.status_code, 200)

    def test_non_public_model(self):
        # test no returns 200 after competition update (model publicity schema is changed)
        resp = self.client.get("http://localhost:8000/model/vision/2")
        self.assertEqual(resp.status_code, 200)


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


class TestLanguage(TestCase):
    fixtures = ALL_FIXTURES

    def test_public_model_language(self):
        resp = self.client.get("http://localhost:8000/model/language/92")
        self.assertEqual(resp.status_code, 200)

    def test_non_public_model_language(self):
        # test no returns 200 after competition update (model publicity schema is changed)
        resp = self.client.get("http://localhost:8000/model/language/89")
        self.assertEqual(resp.status_code, 200)

    # ensures language homepage exists
    def test_language_leaderboard(self):
        resp = self.client.get("http://localhost:8000/language/")
        self.assertEqual(resp.status_code, 200)

    def test_num_lang_rows(self):
        resp = self.client.get("http://localhost:8000/language/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr")
        self.assertEqual(num_rows, 9)


class TestBenchmarkShortname:
    fixtures = ALL_FIXTURES

    def test_no_lab_id(self):
        benchmark_identifier = "Kar2019-ost"
        shortname = _get_benchmark_shortname(benchmark_identifier)
        expected_shortname = "Kar2019-ost"
        self.assertEqual(shortname, expected_shortname)

    def test_lab_id(self):
        benchmark_identifier = "fei-fei.Deng2009-top1"
        shortname = _get_benchmark_shortname(benchmark_identifier)
        expected_shortname = "Deng2009-top1"
        self.assertEqual(shortname, expected_shortname)

    def test_no_lab_id_with_version(self):
        benchmark_identifier = "MajajHong2015.V4-pls"
        shortname = _get_benchmark_shortname(benchmark_identifier)
        expected_shortname = "MajajHong2015.V4-pls"
        self.assertEqual(shortname, expected_shortname)

    def test_lab_id_with_version(self):
        benchmark_identifier = "dicarlo.MajajHong2015.V4-pls"
        shortname = _get_benchmark_shortname(benchmark_identifier)
        expected_shortname = "MajajHong2015.V4-pls"
        self.assertEqual(shortname, expected_shortname)
