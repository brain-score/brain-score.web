from django.test.runner import DiscoverRunner


class ExistingDatabaseTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        return None

    def teardown_databases(self, old_config, **kwargs):
        pass
