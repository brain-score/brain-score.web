from unittest import skip
from django.test import TestCase
from django.db import connection
import logging

# Set up logger at the top of the file
logger = logging.getLogger(__name__)

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
        Refreshes materialized views for all test classes that inherit from this base class.
        """
        super().setUpTestData()

        logger.info("Starting materialized view refresh")
        try:
            # Execute the refresh function to update materialized views
            with connection.cursor() as cursor:
                logger.debug("Executing refresh_all_materialized_views()")
                cursor.execute("SELECT refresh_all_materialized_views();")
                logger.info("Successfully refreshed materialized views") 
        # Some error handling
        except connection.OperationalError as e:
            logger.error(f"Database connection error while refreshing views: {str(e)}")
            raise RuntimeError("Database connection failed during materialized view refresh")
        except connection.ProgrammingError as e:
            logger.error(f"SQL error while refreshing views: {str(e)}")
            raise RuntimeError("SQL error during materialized view refresh")
        except Exception as e:
            logger.error(f"Unexpected error while refreshing views: {str(e)}")
            raise RuntimeError(f"Unexpected error during materialized view refresh: {str(e)}")


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
        self.assertEqual(num_rows, 1 + 78)

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

    def test_correct_ranking(self):
        """Test that the ranking is incrementing correctly with identical scores"""
        resp = self.client.get("http://localhost:8000/vision/")
        self.assertEqual(resp.status_code, 200)
        
        # Find the models with identical scores
        content = resp.content.decode('utf-8')
        
        # Find the ranks for these models
        densenet_rank = None
        resnet_rank = None
        prev_rank = None
        next_rank = None
        
        # Parse the HTML to find the ranks
        lines = content.split('\n')
        
        # First pass: find the ranks for our target models
        for i, line in enumerate(lines):
            if 'densenet-169' in line:
                # Look for the rank in the same tr element
                for j in range(max(0, i-5), i+1):  # Look back a few lines to find the rank
                    if 'class="rank">' in lines[j]:
                        densenet_rank = int(lines[j].split('class="rank">')[1].split('</td>')[0])
                        break
            elif 'resnet-101_v2' in line:
                # Look for the rank in the same tr element
                for j in range(max(0, i-5), i+1):  # Look back a few lines to find the rank
                    if 'class="rank">' in lines[j]:
                        resnet_rank = int(lines[j].split('class="rank">')[1].split('</td>')[0])
                        break
        
        print(f"densenet_rank: {densenet_rank}, resnet_rank: {resnet_rank}")
    
        # Verify the ranks
        self.assertIsNotNone(densenet_rank, "Could not find densenet-169 rank")
        self.assertIsNotNone(resnet_rank, "Could not find resnet-101_v2 rank")
        self.assertEqual(densenet_rank, resnet_rank, "Models with identical scores should have the same rank")
        self.assertIsNotNone(prev_rank, "Could not find previous rank")
        self.assertIsNotNone(next_rank, "Could not find next rank")
        self.assertEqual(prev_rank, densenet_rank - 1, "Previous rank should be one less")
        self.assertEqual(next_rank, densenet_rank + 2, "Next rank should be one more")


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


"""
The below are no longer used as they are now handled by the materialized views
"""

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