from django.test import TestCase
from django.db import connection
from .test_views import ALL_FIXTURES, BaseTestCase

class TestMaterializedViews(BaseTestCase):
    def test_refresh_materialized_views(self):
        """Test that the refresh_all_materialized_views() function executes successfully"""
        with connection.cursor() as cursor:
            # Execute the refresh function
            cursor.execute("SELECT refresh_all_materialized_views()")

            # Verify that key materialized views exist and have data
            cursor.execute("""
                SELECT COUNT(*) 
                FROM mv_final_model_context
            """)
            model_count = cursor.fetchone()[0]
            self.assertGreater(model_count, 0, "mv_final_model_context should contain data")

            cursor.execute("""
                SELECT COUNT(*) 
                FROM mv_final_benchmark_context
            """)
            benchmark_count = cursor.fetchone()[0]
            self.assertGreater(benchmark_count, 0, "mv_final_benchmark_context should contain data")

    def test_refresh_after_data_change(self):
        """Test that materialized views update after data changes"""
        with connection.cursor() as cursor:
            # Get initial count
            cursor.execute("SELECT COUNT(*) FROM mv_final_model_context")
            initial_count = cursor.fetchone()[0]

            # Add a test model directly to the test database, not fixture (so non-permanent)
            cursor.execute("""
                INSERT INTO brainscore_model (name, domain, public, owner_id, submission_id, visual_degrees)
                VALUES ('test_model', 'vision', true, 
                    (SELECT id FROM brainscore_user WHERE email='martin.schrimpf@outlook.com'), 
                    33, 8)
            """)

            # Refresh views
            cursor.execute("SELECT refresh_all_materialized_views()")

            # Verify count increased
            cursor.execute("SELECT COUNT(*) FROM mv_final_model_context")
            new_count = cursor.fetchone()[0]
            self.assertGreater(new_count, initial_count, 
                             "mv_model_scores should reflect new data after refresh")