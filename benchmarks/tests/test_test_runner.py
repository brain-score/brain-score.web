from unittest import TestCase

from benchmarks.test_runner import ExistingDatabaseTestRunner


class ExistingDatabaseTestRunnerTests(TestCase):
    def test_database_setup_is_skipped(self):
        runner = ExistingDatabaseTestRunner()

        self.assertIsNone(runner.setup_databases())

    def test_database_teardown_is_skipped(self):
        runner = ExistingDatabaseTestRunner()

        self.assertIsNone(runner.teardown_databases(None))
