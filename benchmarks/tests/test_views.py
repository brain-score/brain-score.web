from unittest import skip
from django.test import TestCase
from django.db import connection

ALL_FIXTURES = [
    'fixture-users.json',
    'fixture-benchmarkreferences.json',
    'fixture-benchmarktypes.json',
    'fixture-benchmarkmeta.json',
    'fixture-benchmarkinstances.json',
    'fixture-modelreferences.json',
    'fixture-submissions.json',
    'fixture-models.json',
    'fixture-scores.json',
    'fixture-benchmarktypes-language.json',
    'fixture-benchmarkmeta-language.json',
    'fixture-benchmarkinstances-language.json',
    'fixture-users-language.json',
    'fixture-models-language.json',
    'fixture-scores-language.json'
]

class BaseTestCase(TestCase):
    fixtures = ALL_FIXTURES

    @classmethod
    def setUpTestData(cls):
        """
        This runs once for the entire test class *after* the fixtures are loaded.
        Sets up materialized views for all test classes that inherit from this base class.
        """
        super().setUpTestData()

        # 1. Read your SQL file
        with open("benchmarks/sql/mv.sql", "r") as f:
            mv_script = f.read()

        # 2. Execute the SQL against the test database
        with connection.cursor() as cursor:
            cursor.execute(mv_script)


class TestTable(BaseTestCase):
    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/")
        self.assertEqual(resp.status_code, 200)

class TestVision(BaseTestCase):    
    def test_vision_leaderboard(self):
        resp = self.client.get("http://localhost:8000/vision/")
        self.assertEqual(resp.status_code, 200)

    def test_num_vision_rows(self):
        resp = self.client.get("http://localhost:8000/vision/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr")
        # Extra (1 +) because of a header with <tr>
        self.assertEqual(num_rows, 1 + 87)

    def test_public_vision_model(self):
        resp = self.client.get("http://localhost:8000/model/vision/1")
        self.assertEqual(resp.status_code, 200)

    def test_non_public_vision_model(self):
        resp = self.client.get("http://localhost:8000/model/vision/2")
        self.assertEqual(resp.status_code, 200)

    def test_private_vision_model_anonymous_title(self):
        """Test that private vision models show anonymous title"""
        resp = self.client.get("http://localhost:8000/model/vision/2")  # alexnet2 is private
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<h1 class="title">Anonymous Model #2</h1>')


class TestLanguage(BaseTestCase):
    def test_language_leaderboard(self):
        resp = self.client.get("http://localhost:8000/language/")
        self.assertEqual(resp.status_code, 200)
    
    def test_num_lang_rows(self):
        resp = self.client.get("http://localhost:8000/language/")
        content = resp.content.decode('utf-8')
        num_rows = content.count("<tr")
        # Extra (1 +) because of a header with <tr>
        self.assertEqual(num_rows, 8 + 1)

    def test_public_language_model(self):
        resp = self.client.get("http://localhost:8000/model/language/92")
        self.assertEqual(resp.status_code, 200)

    def test_non_public_language_model(self):
        resp = self.client.get("http://localhost:8000/model/language/89")
        self.assertEqual(resp.status_code, 200)

    def test_private_language_model_anonymous_title(self):
        """Test that private language models show anonymous title"""
        resp = self.client.get("http://localhost:8000/model/language/89")  # glove-840b is private
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<h1 class="title">Anonymous Model #89</h1>')

"""
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
"""

"""
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
"""

@skip("2022 competition is over")
class TestCompetitionTable2022(BaseTestCase):
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


class TestCompetition2024(BaseTestCase):
    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/competition2024/")
        self.assertEqual(resp.status_code, 200)
