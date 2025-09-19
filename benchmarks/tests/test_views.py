from django.test import TestCase
from django.db import connection
import logging
from bs4 import BeautifulSoup

# Set up logger at the top of the file
logger = logging.getLogger(__name__)


class BaseTestCase(TestCase):
    # Completely disable Django's test database creation. We do this to force django to use the web_test DB
    # Uses TestCase instead of TransactionTestCase to avoid flushing web_tests DB after each test
    @classmethod
    def setUpClass(cls):
        # Skip all Django test setup
        return

    @classmethod
    def tearDownClass(cls):
        # Skip all Django test teardown
        return

    def setUp(self):
        # Skip Django's setUp
        pass

    def tearDown(self):
        # Skip Django's tearDown
        pass


class TestMaterializedViewQuery(BaseTestCase):
    def test_query_mv_final_model_context(self):
        """Test querying the mv_final_model_context materialized view"""
        with connection.cursor() as cursor:
            # Query the materialized view and limit to 10 rows
            cursor.execute("""
                SELECT * FROM mv_final_model_context 
                LIMIT 10
            """)

            # Fetch all results
            rows = cursor.fetchall()

            # Get column names
            columns = [desc[0] for desc in cursor.description]

            # Assert that we got some results
            self.assertGreater(len(rows), 0, "Should return at least one row")
            self.assertLessEqual(len(rows), 10, "Should return at most 10 rows")


class TestWebsitePages(BaseTestCase):
    def test_home_page(self):
        """Test the home page loads correctly"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_vision_leaderboard(self):
        """Test the vision leaderboard page"""
        response = self.client.get('/vision/', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Leaderboard', response.content)

    def test_language_leaderboard(self):
        """Test the language leaderboard page"""
        response = self.client.get('/language/', follow=True)
        self.assertEqual(response.status_code, 200)

    def test_profile_page(self):
        """Test the profile page loads"""
        response = self.client.get('/profile/')
        self.assertEqual(response.status_code, 200)

    def test_explore_page(self):
        """Test the explore page loads"""
        response = self.client.get('/vision/explore/')
        self.assertEqual(response.status_code, 200)

    def test_compare_page(self):
        """Test the compare page loads"""
        response = self.client.get('/vision/compare/')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_home(self):
        """Test the tutorials home page loads"""
        response = self.client.get('/tutorials/')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_models(self):
        """Test the tutorials/models page loads"""
        response = self.client.get('/tutorials/models')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_benchmarks(self):
        """Test the tutorials/benchmarks page loads"""
        response = self.client.get('/tutorials/benchmarks')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_troubleshooting(self):
        """Test the tutorials/troubleshooting page loads"""
        response = self.client.get('/tutorials/troubleshooting')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_models_quickstart(self):
        """Test the tutorials/models/quickstart page loads"""
        response = self.client.get('/tutorials/models/quickstart')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_models_deepdive_1(self):
        """Test the tutorials/models/deepdive_1 page loads"""
        response = self.client.get('/tutorials/models/deepdive_1')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_models_deepdive_2(self):
        """Test the tutorials/models/deepdive_2 page loads"""
        response = self.client.get('/tutorials/models/deepdive_2')
        self.assertEqual(response.status_code, 200)

    def test_tutorials_models_deepdive_3(self):
        """Test the tutorials/models/deepdive_3 page loads"""
        response = self.client.get('/tutorials/models/deepdive_3')
        self.assertEqual(response.status_code, 200)

    def test_community_page(self):
        """Test the community page loads"""
        response = self.client.get('/community')
        self.assertEqual(response.status_code, 200)

    def test_faq_page(self):
        """Test the FAQ page loads"""
        response = self.client.get('/faq/')
        self.assertEqual(response.status_code, 200)

    def test_model_page(self):
        """Ensure the model detail page contains expected sections"""
        # Adjust the model slug to match one you know exists in your test DB
        response = self.client.get('/model/vision/2330')
        self.assertEqual(response.status_code, 200)

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check h3 title
        h3 = soup.find('h3', {'id': 'scores', 'class': 'title is-3'})
        self.assertIsNotNone(h3, "Missing h3#scores title")
        self.assertIn('Scores on benchmarks', h3.text)

        # Check subtitle h4
        h4 = soup.find('h4', class_='subtitle is-4')
        self.assertIsNotNone(h4, "Missing h4 subtitle")
        self.assertIn('How to use', h4.text)

        # Check for <p> with 'Layer Commitment'
        layer_commitments = soup.find_all('p', class_='subtitle is-5')
        layer_commitment_found = any('Layer Commitment' in p.get_text(strip=True) for p in layer_commitments)
        self.assertTrue(layer_commitment_found, "Missing 'Layer Commitment' paragraph")

        # Check for 3 identical 'Visual Angle' sections
        visual_angle = soup.find_all('p', class_='subtitle is-5')
        visual_angle_found = any('Visual Angle' in p.get_text(strip=True) for p in visual_angle)
        self.assertTrue(visual_angle_found, "Missing 'Visual Angle' paragraph")


class TestVision(BaseTestCase):

    def test_public_vision_model(self):
        resp = self.client.get("/model/vision/2330") # convnext top model
        self.assertEqual(resp.status_code, 200)

    def test_private_vision_model_anonymous_title(self):
        """Test that private vision models show anonymous title"""
        resp = self.client.get("/model/vision/912")  # alexnet2 is private
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '<h1 class="title">Anonymous Model #912</h1>')


    def test_aggrid_three_buttons(self):
        """Ensure the CSV export button is present on the vision leaderboard content"""
        response = self.client.get("/vision/leaderboard/content/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Export')
        self.assertContains(response, 'Advanced Filters')
        self.assertContains(response, 'id="modelSearchInput"')


class TestLanguage(BaseTestCase):

    def test_public_language_model(self):
        resp = self.client.get("/model/language/2074") # all language models are public
        self.assertEqual(resp.status_code, 200)
