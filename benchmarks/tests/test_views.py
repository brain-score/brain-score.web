from django.test import TestCase


class TestTable(TestCase):
    def test_no_errors(self):
        resp = self.client.get("http://localhost:8000/")
        self.assertEqual(resp.status_code, 200)

    def test_no_data(self):
        resp = self.client.get("http://localhost:8000/")
        content = resp.content.decode('utf-8')
        self.assertIn("No data.", content)
