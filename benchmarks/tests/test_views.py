from django.test import TestCase

ALL_FIXTURES = ['fixture-benchmarkreferences.json', 'fixture-benchmarktypes.json', 'fixture-benchmarkinstances.json',
                'fixture-users.json', 'fixture-modelreferences.json', 'fixture-models.json',
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
        self.assertEqual(num_rows, 1 + 79)


class TestModel(TestCase):
    fixtures = ALL_FIXTURES

    def test_public_model(self):
        resp = self.client.get("http://localhost:8000/model/1")
        self.assertEqual(resp.status_code, 200)

    def test_non_public_model(self):
        resp = self.client.get("http://localhost:8000/model/2")
        self.assertEqual(resp.status_code, 404)
