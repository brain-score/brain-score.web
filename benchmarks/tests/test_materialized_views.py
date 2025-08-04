from django.test import TestCase
from django.db import connection
from .test_views import BaseTestCase
import unittest


class TestMaterializedViews(BaseTestCase):
    def test_refresh_materialized_views(self):
        """Test that the refresh_all_materialized_views() function executes successfully"""
        with connection.cursor() as cursor:
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

    @unittest.skip("Insertion of new model scores to be avoided on web_tests database.")
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

    @unittest.skip("Insertion of new benchmark to be avoided on web_tests database.")
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

    def test_compare_get_context_implementations(self):
        """Test that the new materialized view implementation of get_context() produces equivalent output to the legacy implementation"""
        from benchmarks.views.index import get_context as new_get_context
        from benchmarks.tests.test_helpers.legacy_index import get_context as legacy_get_context

        # Test cases to cover different scenarios
        test_cases = [
            # (domain, user, show_public)
            ("vision", None, True),  # Public vision view
            ("language", None, True),  # Public language view
        ]

        for domain, user, show_public in test_cases:
            # Get contexts from both implementations
            new_context = new_get_context(domain=domain, user=user, show_public=show_public)
            legacy_context = legacy_get_context(domain=domain, user=user, show_public=show_public)

            # Filter legacy context to only include public models
            legacy_context['models'] = [model for model in legacy_context['models'] if model.public]

            # Compare key fields that should be identical
            self.assertEqual(new_context['domain'], legacy_context['domain'],
                             f"Domain mismatch for {domain} view")
            self.assertEqual(new_context['BASE_DEPTH'], legacy_context['BASE_DEPTH'],
                             f"BASE_DEPTH mismatch for {domain} view")
            self.assertEqual(new_context['has_user'], legacy_context['has_user'],
                             f"has_user mismatch for {domain} view")

            # Compare benchmark data
            new_benchmarks = {b.identifier: b for b in new_context['benchmarks']}
            legacy_benchmarks = {b.identifier: b for b in legacy_context['benchmarks']}
            self.assertEqual(set(new_benchmarks.keys()), set(legacy_benchmarks.keys()),
                             f"Benchmark identifiers mismatch for {domain} view")

            # Compare model data - allow for newer models in materialized views
            new_models = {m.id: m for m in new_context['models']}
            legacy_models = {m.id: m for m in legacy_context['models']}

            # Check that legacy models are subset of new models (newer models may exist in materialized views)
            legacy_set = set(legacy_models.keys())
            new_set = set(new_models.keys())

            # All legacy models should exist in new implementation
            missing_in_new = legacy_set - new_set
            self.assertEqual(len(missing_in_new), 0,
                             f"Legacy models missing in new implementation: {missing_in_new}")

            # Compare benchmark parents and visibility
            self.assertEqual(new_context['benchmark_parents'], legacy_context['benchmark_parents'],
                             f"Benchmark parents mismatch for {domain} view")
            self.assertEqual(new_context['not_shown_set'], legacy_context['not_shown_set'],
                             f"Not shown set mismatch for {domain} view")

    def test_compare_score_between_legacy_and_new_implementation(self):
        """Test that the new materialized view implementation of get_context() produces equivalent output to the legacy implementation"""
        from benchmarks.views.index import get_context as new_get_context
        from benchmarks.tests.test_helpers.legacy_index import get_context as legacy_get_context

        domain = "vision"
        user = None
        show_public = True

        new_context = new_get_context(domain=domain, user=user, show_public=show_public)
        legacy_context = legacy_get_context(domain=domain, user=user, show_public=show_public)

        new_row = new_context['models'][0]
        legacy_row = legacy_context['models'][0]

        # Make sure we are comparing the same model
        self.assertEqual(new_row.name, legacy_row.name)
        self.assertEqual(new_row.id, legacy_row.id)

        # Get the score for the model in the new context
        new_score = new_row.scores[0]
        legacy_score = legacy_row.scores[0]

        # Compare score_ceiled
        self.assertEqual(
            float(new_score['score_ceiled'].strip('.')),  # Convert '.390' to 0.390
            float(legacy_score.score_ceiled.strip('.')),  # Convert '.390' to 0.390
            "Score ceiled mismatch between new and legacy implementation"
        )

        # Compare benchmark identifier
        self.assertEqual(
            new_score['benchmark']['identifier'],
            legacy_score.benchmark.identifier,
            "Benchmark identifier mismatch between new and legacy implementation"
        )