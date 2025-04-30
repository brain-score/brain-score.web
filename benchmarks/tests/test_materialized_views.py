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
            
    def test_aggregation_with_new_benchmark(self):
        """Tests if average_vision score updates correctly when a new benchmark score is added"""
        
        print("\n\nUsing  mobilenet_v1_0.25_128 on FreemanZiemba2013.V1-pls for aggregation test")
        
        with connection.cursor() as cursor:
            # 1. First get mobilenet's current average_vision
            cursor.execute("""
                SELECT model_id, score_ceiled
                FROM mv_model_scores_enriched 
                WHERE benchmark_identifier = 'average_vision' 
                AND model_id = (
                    SELECT id FROM brainscore_model 
                    WHERE name = 'mobilenet_v1_0.25_128'
                )
            """)
            model_id, initial_average = cursor.fetchone()

            # Print all existing scores for this model and benchmark before modification
            cursor.execute("""
                SELECT s.*, b.benchmark_type_id, b.version
                FROM brainscore_score s
                JOIN brainscore_benchmarkinstance b ON s.benchmark_id = b.id
                WHERE s.model_id = %s
                AND b.benchmark_type_id = 'movshon.FreemanZiemba2013.V1-pls'
            """, [model_id])
            print("\n\nExisting entry for FreemanZiemba2013.V1-pls:")
            for row in cursor.fetchall():
                print(row)

            print(f"\nAverage vision with the above score for FreemanZiemba2013.V1-pls: {initial_average}")

            # 2. Update the existing score instead of inserting a new one
            cursor.execute("""
                UPDATE brainscore_score 
                SET score_ceiled = 0.04,
                    score_raw = 0.02,
                    end_timestamp = NOW()
                WHERE model_id = %s
                AND benchmark_id = (
                    SELECT id FROM brainscore_benchmarkinstance 
                    WHERE benchmark_type_id = 'movshon.FreemanZiemba2013.V1-pls' 
                    AND version = 2
                )
            """, [model_id])

            # Print all scores after modification
            cursor.execute("""
                SELECT s.*, b.benchmark_type_id, b.version
                FROM brainscore_score s
                JOIN brainscore_benchmarkinstance b ON s.benchmark_id = b.id
                WHERE s.model_id = %s
                AND b.benchmark_type_id = 'movshon.FreemanZiemba2013.V1-pls'
            """, [model_id])
            print("\nUpdated entry for FreemanZiemba2013.V1-pls:")
            for row in cursor.fetchall():
                print(row)

            # 3. Refresh the materialized views
            cursor.execute("SELECT refresh_all_materialized_views()")

            # 4. Get the new average_vision
            cursor.execute("""
                SELECT score_ceiled 
                FROM mv_model_scores_enriched 
                WHERE model_id = %s
                AND benchmark_identifier = 'average_vision'
            """, [model_id])
            new_average = cursor.fetchone()[0]

            print(f"\nAverage vision after modification of score for FreemanZiemba2013.V1-pls: {new_average}")

            # 5. Verify the average changed
            self.assertNotEqual(initial_average, new_average, 
                              "average_vision should change after adding new benchmark score")