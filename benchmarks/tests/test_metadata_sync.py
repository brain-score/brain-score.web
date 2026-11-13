"""Scheduled publication cannot skip failures or turn open PRs into writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from types import SimpleNamespace
from unittest import skipIf, skipUnless
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings

from benchmarks.model_metadata.github import ProposalError, metadata_available
from benchmarks.model_metadata.synchronization import merged_candidates, sync_domain, timestamp
from benchmarks.management.commands.sync_model_metadata import Command
from benchmarks.tests.test_metadata_edit import FakeGitHub, REGISTRY, PATH, document

NOW = datetime(2026, 10, 3, 16, 0, tzinfo=timezone.utc)
START = NOW - timedelta(hours=1)


def pull(number=10, **changes):
    value = {'number': number, 'merge_commit_sha': str(number),
             'merged_at': (NOW - timedelta(minutes=2)).isoformat(),
             'updated_at': (NOW - timedelta(minutes=1)).isoformat(),
             'base': {'ref': 'master', 'repo': {'full_name': 'brain-score/vision'}}}
    value.update(changes)
    return value


class State:
    def __init__(self):
        self.values = {}
        self.writes = 0

    def read(self, domain):
        return deepcopy(self.values.get(domain, {}))

    def save(self, domain, value):
        self.values[domain] = deepcopy(value)
        self.writes += 1


class SynchronizationTests(SimpleTestCase):
    def setUp(self):
        self.state = State()
        self.api = Mock()
        self.api.request.return_value = [pull()]
        self.api.pages.return_value = [{'filename': PATH, 'status': 'modified'}]
        self.publish = Mock(return_value=[])

    def sync(self, **kwargs):
        return sync_domain('vision', REGISTRY['vision'], self.api, self.state,
                           START, NOW, self.publish, **kwargs)

    def test_only_merged_postactivation_prs_on_the_configured_branch_are_candidates(self):
        self.api.request.return_value = [pull(1, merged_at=None),
            pull(2, merged_at=(START - timedelta(days=1)).isoformat()),
            pull(3, base={'ref': 'other', 'repo': {'full_name': 'brain-score/vision'}}),
            pull(4, base={'ref': 'master', 'repo': {'full_name': 'another/vision'}}), pull()]
        self.assertEqual(self.sync()['candidate_prs'], [10])
        self.publish.assert_called_once_with('vision', 10, self.api)

    def test_nonmetadata_changes_and_paths_outside_model_folders_are_skipped(self):
        self.api.pages.return_value = [{'filename': 'brainscore_vision/models/example/model.py'},
            {'filename': 'brainscore_vision/models/example/nested/metadata.yaml'}]
        self.assertEqual(self.sync()['candidate_prs'], [])
        self.publish.assert_not_called()

    def test_removals_and_renames_reach_the_existing_publication_validator(self):
        self.api.pages.return_value = [{'filename': 'other/file.yaml', 'previous_filename': PATH,
                                        'status': 'renamed'}]
        self.publish.side_effect = ProposalError('A separate migration is required')
        self.assertEqual(self.sync()['errors'], [{'pr': 10, 'error': 'ProposalError'}])
        self.assertEqual(self.state.writes, 0)

    def test_successful_prs_are_not_republished_during_the_overlap_window(self):
        self.sync()
        self.assertEqual(self.sync()['processed_prs'], [])
        self.publish.assert_called_once()

    def test_failed_publication_retries_without_repeating_successful_siblings(self):
        self.api.request.return_value = [pull(10), pull(11)]
        self.publish.side_effect = [[], RuntimeError("private token must not appear")]
        result = self.sync()
        self.assertEqual(result['processed_prs'], [10])
        self.assertNotIn('private token', str(result))
        self.assertEqual(self.state.read('vision')['cursor'], START.isoformat())
        self.publish.reset_mock(side_effect=True)
        self.assertEqual(self.sync()['processed_prs'], [11])
        self.publish.assert_called_once_with('vision', 11, self.api)
        self.assertEqual(self.state.read('vision')['cursor'], NOW.isoformat())

    def test_partial_publication_retains_models_and_advances_the_cursor(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "published", "deferred_models": ["later"]}
        ]
        result = self.sync()
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["processed_prs"], [10])
        files = [{"path": PATH, "deferred_models": ["later"]}]
        self.assertEqual(result["deferred_prs"], [{"pr": 10, "files": files}])
        saved = self.state.read("vision")
        self.assertEqual(saved["cursor"], NOW.isoformat())
        self.assertEqual(saved["deferred"], {"10": {"sha": "10", "files": files}})
        self.assertNotIn("10", saved["completed"])

    def test_deferred_files_retry_after_the_discovery_window_expires(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "deferred", "deferred_models": ["later"]}
        ]
        self.sync()
        self.api.request.side_effect = [[], pull()]
        self.publish.reset_mock()
        self.publish.return_value = [{"path": PATH, "status": "published"}]
        later = NOW + timedelta(days=2)
        result = sync_domain(
            "vision",
            REGISTRY["vision"],
            self.api,
            self.state,
            START,
            later,
            self.publish,
        )
        self.publish.assert_called_once_with("vision", 10, self.api, paths=[PATH])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["deferred_prs"], [])
        self.assertEqual(result["processed_prs"], [10])
        self.assertEqual(self.state.read("vision")["deferred"], {})
        self.assertEqual(self.state.read("vision")["cursor"], later.isoformat())

    def test_overlap_and_deferred_list_publish_a_pr_only_once(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "deferred", "deferred_models": ["later"]}
        ]
        self.sync()
        self.publish.reset_mock()
        self.sync()
        self.publish.assert_called_once_with("vision", 10, self.api, paths=[PATH])
        self.assertEqual(self.api.pages.call_count, 1)

    def test_deferred_retry_failure_preserves_pending_models(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "deferred", "deferred_models": ["later"]}
        ]
        self.sync()
        saved = self.state.read("vision")
        self.publish.side_effect = RuntimeError("private credential")
        result = self.sync()
        self.assertEqual(result["errors"], [{"pr": 10, "error": "RuntimeError"}])
        self.assertEqual(self.state.read("vision"), saved)
        self.assertNotIn("private credential", str(result))

    def test_deferred_lookup_failure_preserves_pending_models(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "deferred", "deferred_models": ["later"]}
        ]
        self.sync()
        saved = self.state.read("vision")
        self.api.request.side_effect = [[], RuntimeError("private credential")]
        self.publish.reset_mock()
        result = self.sync()
        self.assertEqual(result["errors"], [{"pr": 10, "error": "RuntimeError"}])
        self.assertEqual(self.state.read("vision"), saved)
        self.publish.assert_not_called()

    def test_partial_pr_does_not_repeat_successful_sibling_prs(self) -> None:
        self.api.request.return_value = [pull(10), pull(11)]
        self.publish.side_effect = [
            [{"path": PATH, "status": "published", "deferred_models": ["later"]}],
            [{"path": PATH, "status": "published"}],
        ]
        self.sync()
        self.publish.reset_mock(side_effect=True)
        self.publish.return_value = [{"path": PATH, "status": "published"}]
        self.assertEqual(self.sync()["processed_prs"], [10])
        self.publish.assert_called_once_with("vision", 10, self.api, paths=[PATH])

    def test_superseded_deferred_file_leaves_the_retry_list(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "deferred", "deferred_models": ["later"]}
        ]
        self.sync()
        self.publish.return_value = [{"path": PATH, "status": "superseded"}]
        self.assertEqual(self.sync()["deferred_prs"], [])
        self.assertEqual(self.state.read("vision")["deferred"], {})

    def test_dry_run_does_not_publish_or_remove_deferred_models(self) -> None:
        self.publish.return_value = [
            {"path": PATH, "status": "deferred", "deferred_models": ["later"]}
        ]
        self.sync()
        saved, writes = self.state.read("vision"), self.state.writes
        self.publish.reset_mock()
        result = self.sync(dry_run=True)
        self.assertEqual(result["deferred_prs"][0]["pr"], 10)
        self.assertEqual(self.state.read("vision"), saved)
        self.assertEqual(self.state.writes, writes)
        self.publish.assert_not_called()

    def test_publication_command_returns_structured_results_for_retry(self) -> None:
        import os

        api = SimpleNamespace(
            session=SimpleNamespace(
                headers={"Authorization": "Bearer temporary-test-token"}
            )
        )
        results = [{"path": PATH, "status": "deferred", "deferred_models": ["later"]}]

        def command(*args: object, **kwargs: object) -> None:
            self.assertEqual(kwargs["paths"], [PATH])
            self.assertEqual(kwargs["format"], "json")
            kwargs["stdout"].write(json.dumps(results))

        with patch.dict(
            os.environ, {"METADATA_PUBLISH_GITHUB_TOKEN": "existing-test-token"}
        ), patch(
            "benchmarks.management.commands.sync_model_metadata.call_command",
            side_effect=command,
        ):
            self.assertEqual(Command.publish("vision", 10, api, paths=[PATH]), results)
            self.assertEqual(
                os.environ["METADATA_PUBLISH_GITHUB_TOKEN"], "existing-test-token"
            )

    def test_dry_run_never_publishes_or_changes_checkpoints(self):
        self.assertEqual(self.sync(dry_run=True)['candidate_prs'], [10])
        self.publish.assert_not_called()
        self.assertEqual(self.state.writes, 0)

    def test_pagination_failure_does_not_advance_the_cursor(self):
        self.api.request.return_value = [pull(number) for number in range(100)]
        with self.assertRaisesRegex(ProposalError, '1,000'):
            self.sync()
        self.assertEqual(self.api.request.call_count, 10)
        self.assertEqual(self.state.writes, 0)
        self.publish.assert_not_called()

    def test_candidates_are_processed_by_merge_time_and_pagination_ends_at_watermark(self):
        values = [pull(number) for number in range(100)]
        values[0] = pull(0, updated_at=(START - timedelta(minutes=1)).isoformat())
        self.api.request.side_effect = [values, []]
        candidates = merged_candidates(self.api, REGISTRY['vision'], START, START, NOW)
        self.assertEqual([p['number'] for p in candidates], list(range(1, 100)))
        self.assertEqual(self.api.request.call_count, 2)

    def test_timezone_is_required_and_utc_normalization_is_stable(self):
        self.assertEqual(timestamp('2026-10-03T12:00:00-04:00'), NOW)
        for value in ['2026-10-03T12:00:00', '', None]:
            with self.assertRaises(ProposalError):
                timestamp(value)

    def test_future_checkpoint_cannot_skip_merged_prs(self):
        self.state.save('vision', {'start': START.isoformat(),
            'cursor': (NOW + timedelta(minutes=1)).isoformat()})
        with self.assertRaisesRegex(ProposalError, 'future'):
            self.sync()
        self.publish.assert_not_called()

    @override_settings(MODEL_METADATA_SYNC_ENABLED=False)
    def test_disabled_command_does_not_connect_to_publication_resources(self):
        with patch('benchmarks.management.commands.sync_model_metadata.RedisState') as state, \
                patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader') as reader, \
                patch('benchmarks.management.commands.sync_model_metadata.report_run') as metric:
            call_command('sync_model_metadata', stdout=StringIO())
        metric.assert_not_called()
        state.assert_not_called()
        reader.assert_not_called()

    def test_publication_token_is_restored_after_a_command_failure(self):
        import os
        api = SimpleNamespace(session=SimpleNamespace(headers={'Authorization': 'Bearer temporary-test-token'}))
        with patch.dict(os.environ, {'METADATA_PUBLISH_GITHUB_TOKEN': 'existing-test-token'}), \
                patch('benchmarks.management.commands.sync_model_metadata.call_command', side_effect=CommandError('retry')):
            with self.assertRaises(CommandError):
                Command.publish('vision', 10, api)
            self.assertEqual(os.environ['METADATA_PUBLISH_GITHUB_TOKEN'], 'existing-test-token')


@skipUnless(metadata_available(), 'Install core with metadata support')
@skipIf(settings.TEST_RUNNER.endswith('ExistingDatabaseTestRunner'),
        'Run synchronization database tests on disposable PostgreSQL')
@override_settings(MODEL_METADATA_REPOSITORIES=REGISTRY)
class SynchronizationPublicationTests(TestCase):
    def command_settings(self):
        return override_settings(MODEL_METADATA_SYNC_ENABLED=True,
            MODEL_METADATA_SYNC_START_AT='2026-10-01T00:00:00Z',
            MODEL_METADATA_SYNC_EXPECTED_DATABASE=connection.settings_dict['NAME'])

    def test_other_instance_lock_prevents_a_duplicate_worker(self):
        from benchmarks.management.commands.sync_model_metadata import LOCK_ID

        peer = connection.copy()
        try:
            with peer.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_lock(%s)', [LOCK_ID])
            output = StringIO()
            with self.command_settings(), patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader') as reader, \
                    patch('benchmarks.management.commands.sync_model_metadata.report_run') as metric:
                call_command('sync_model_metadata', stdout=output)
            metric.assert_not_called()
            self.assertIn('Another metadata synchronization', output.getvalue())
            reader.assert_not_called()
        finally:
            peer.close()

    def test_dry_run_reports_no_health_metric_and_cannot_publish(self):
        state = State()
        discovery = Mock()
        discovery.request.return_value = [pull()]
        discovery.pages.return_value = [{'filename': PATH, 'status': 'modified'}]
        with self.command_settings(), \
                patch('benchmarks.management.commands.sync_model_metadata.DryRunState', return_value=state), \
                patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader') as reader, \
                patch('benchmarks.management.commands.sync_model_metadata.report_run') as metric, \
                patch.object(Command, 'publish') as publish:
            reader.return_value.__enter__.return_value = discovery
            call_command('sync_model_metadata', dry_run=True, stdout=StringIO())
        metric.assert_not_called()
        publish.assert_not_called()
        self.assertEqual(state.writes, 0)

    def test_successful_worker_reports_health_after_checkpointing(self):
        state = State()
        discovery = Mock()
        discovery.request.return_value = []
        with self.command_settings(), \
                patch('benchmarks.management.commands.sync_model_metadata.caches', {'redis': Mock()}), \
                patch('benchmarks.management.commands.sync_model_metadata.RedisState', return_value=state), \
                patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader') as reader, \
                patch('benchmarks.management.commands.sync_model_metadata.report_run') as metric:
            reader.return_value.__enter__.return_value = discovery
            call_command('sync_model_metadata', stdout=StringIO())
        self.assertTrue(state.read('vision').get('cursor'))
        metric.assert_called_once_with(True)

    def test_deferred_registration_reports_success_and_keeps_retry_state(self) -> None:
        state, output = State(), StringIO()
        discovery = Mock()
        discovery.request.return_value = [pull()]
        discovery.pages.return_value = [{"filename": PATH, "status": "modified"}]
        with self.command_settings(), patch(
            "benchmarks.management.commands.sync_model_metadata.caches",
            {"redis": Mock()},
        ), patch(
            "benchmarks.management.commands.sync_model_metadata.RedisState",
            return_value=state,
        ), patch(
            "benchmarks.management.commands.sync_model_metadata.GitHub.reader"
        ) as reader, patch.object(
            Command,
            "publish",
            return_value=[
                {"path": PATH, "status": "published", "deferred_models": ["later"]}
            ],
        ), patch(
            "benchmarks.management.commands.sync_model_metadata.report_run"
        ) as metric:
            reader.return_value.__enter__.return_value = discovery
            call_command("sync_model_metadata", stdout=output)
        metric.assert_called_once_with(True)
        self.assertEqual(
            state.read("vision")["deferred"]["10"]["files"][0]["deferred_models"],
            ["later"],
        )
        report = json.loads(output.getvalue())[0]
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["deferred_prs"][0]["pr"], 10)

    def test_domain_failure_does_not_skip_another_domain_or_emit_success(self):
        registry = dict(REGISTRY, language={'repository': 'brain-score/language',
                        'branch': 'main', 'model_root': 'brainscore_language/models'})
        state, output = State(), StringIO()
        discovery = Mock()
        discovery.request.return_value = []
        context = Mock()
        context.__enter__ = Mock(return_value=discovery)
        context.__exit__ = Mock(return_value=False)
        with self.command_settings(), override_settings(MODEL_METADATA_REPOSITORIES=registry), \
                patch('benchmarks.management.commands.sync_model_metadata.caches', {'redis': Mock()}), \
                patch('benchmarks.management.commands.sync_model_metadata.RedisState', return_value=state), \
                patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader',
                      side_effect=[ProposalError('private credential'), context]) as reader, \
                patch('benchmarks.management.commands.sync_model_metadata.report_run') as metric:
            with self.assertRaises(CommandError):
                call_command('sync_model_metadata', stdout=output)
        self.assertEqual(reader.call_count, 2)
        self.assertFalse(state.read('vision'))
        self.assertTrue(state.read('language').get('cursor'))
        self.assertNotIn('private credential', output.getvalue())
        metric.assert_called_once_with(False)

    def test_redis_failure_cannot_publish_and_releases_the_worker_lock(self):
        from benchmarks.management.commands.sync_model_metadata import LOCK_ID

        with self.command_settings(), \
                patch('benchmarks.management.commands.sync_model_metadata.caches', {'redis': Mock()}), \
                patch('benchmarks.management.commands.sync_model_metadata.RedisState', side_effect=RuntimeError('private credential')), \
                patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader') as reader, \
                patch('benchmarks.management.commands.sync_model_metadata.report_run') as metric:
            with self.assertRaises(CommandError) as error:
                call_command('sync_model_metadata', stdout=StringIO())
            metric.assert_called_once_with(False)
            self.assertNotIn('private credential', str(error.exception))
            reader.assert_not_called()
        peer = connection.copy()
        try:
            with peer.cursor() as cursor:
                cursor.execute('SELECT pg_try_advisory_lock(%s)', [LOCK_ID])
                self.assertTrue(cursor.fetchone()[0])
        finally:
            peer.close()

    def test_publication_and_cache_retry_do_not_duplicate_database_revisions(self):
        from benchmarks.models import Model, User, ModelMetadataRecord, ModelMetadataRevision

        user = User.objects.create(email='sync@example.org')
        Model.objects.create(name='example', domain='vision', owner=user)
        api = FakeGitHub()
        api.session = SimpleNamespace(headers={'Authorization': 'Bearer temporary-test-token'})
        discovery = Mock()
        discovery.request.return_value = [pull()]
        discovery.pages.return_value = [{'filename': PATH, 'status': 'modified'}]
        state = State()
        def publish(domain, number, github):
            return Command.publish(domain, number, api)
        with patch('benchmarks.management.commands.publish_model_metadata_pr.GitHub', return_value=api), \
                patch('benchmarks.utils.invalidate_domain_cache', side_effect=[{'status': 'warning'}, {'status': 'success'}]):
            first = sync_domain('vision', REGISTRY['vision'], discovery, state, START, NOW, publish)
            self.assertEqual(first['errors'], [{'pr': 10, 'error': 'CommandError'}])
            self.assertEqual(state.writes, 0)
            self.assertEqual(ModelMetadataRecord.objects.get().parameter_count, 100)
            self.assertEqual(ModelMetadataRevision.objects.count(), 1)
            second = sync_domain('vision', REGISTRY['vision'], discovery, state, START, NOW, publish)
            self.assertEqual(second['processed_prs'], [10])
            self.assertEqual(ModelMetadataRevision.objects.count(), 1)

    def test_worker_publishes_registered_metadata_and_reports_healthy_deferral(
        self,
    ) -> None:
        from benchmarks.models import Model, User, ModelMetadataRecord

        owner = User.objects.create(email="partial-worker@example.org")
        Model.objects.create(name="example", domain="vision", owner=owner)
        metadata = document()
        metadata["models"]["later"] = deepcopy(metadata["models"]["example"])
        api = FakeGitHub(metadata)
        state, output, discovery = State(), StringIO(), Mock()
        discovery.session = SimpleNamespace(
            headers={"Authorization": "Bearer temporary-test-token"}
        )
        discovery.request.return_value = [pull()]
        discovery.pages.return_value = [{"filename": PATH, "status": "modified"}]
        with self.command_settings(), patch(
            "benchmarks.management.commands.sync_model_metadata.caches",
            {"redis": Mock()},
        ), patch(
            "benchmarks.management.commands.sync_model_metadata.RedisState",
            return_value=state,
        ), patch(
            "benchmarks.management.commands.sync_model_metadata.GitHub.reader"
        ) as reader, patch(
            "benchmarks.management.commands.publish_model_metadata_pr.GitHub",
            return_value=api,
        ), patch(
            "benchmarks.utils.invalidate_domain_cache",
            return_value={"status": "success"},
        ) as refresh, patch(
            "benchmarks.management.commands.sync_model_metadata.report_run"
        ) as metric:
            reader.return_value.__enter__.return_value = discovery
            call_command("sync_model_metadata", stdout=output)
        metric.assert_called_once_with(True)
        refresh.assert_called_once_with("vision")
        self.assertEqual(
            list(ModelMetadataRecord.objects.values_list("identifier", flat=True)),
            ["example"],
        )
        self.assertEqual(
            state.read("vision")["deferred"]["10"]["files"][0]["deferred_models"],
            ["later"],
        )
        report = json.loads(output.getvalue())[0]
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["deferred_prs"][0]["pr"], 10)

    def test_partial_import_retries_after_registration_without_duplicate_revisions(
        self,
    ) -> None:
        from benchmarks.models import (
            Model,
            User,
            ModelMetadataRecord,
            ModelMetadataRevision,
        )

        owner = User.objects.create(email="deferred@example.org")
        Model.objects.create(name="example", domain="vision", owner=owner)
        metadata = document()
        metadata["models"]["later"] = deepcopy(metadata["models"]["example"])
        api = FakeGitHub(metadata)
        api.session = SimpleNamespace(
            headers={"Authorization": "Bearer temporary-test-token"}
        )
        discovery = Mock()
        discovery.request.return_value = [pull()]
        discovery.pages.return_value = [{"filename": PATH, "status": "modified"}]
        state = State()

        def publish(
            domain: str, number: int, github: object, paths: list[str] | None = None
        ) -> list[dict]:
            return Command.publish(domain, number, api, paths=paths)

        with patch(
            "benchmarks.management.commands.publish_model_metadata_pr.GitHub",
            return_value=api,
        ), patch(
            "benchmarks.utils.invalidate_domain_cache",
            return_value={"status": "success"},
        ):
            first = sync_domain(
                "vision", REGISTRY["vision"], discovery, state, START, NOW, publish
            )
            self.assertEqual(first["errors"], [])
            self.assertEqual(
                first["deferred_prs"][0]["files"][0]["deferred_models"], ["later"]
            )
            self.assertEqual(ModelMetadataRecord.objects.count(), 1)
            self.assertEqual(ModelMetadataRevision.objects.count(), 1)
            unchanged = sync_domain(
                "vision", REGISTRY["vision"], discovery, state, START, NOW, publish
            )
            self.assertEqual(unchanged["errors"], [])
            self.assertEqual(ModelMetadataRevision.objects.count(), 1)
            Model.objects.create(name="later", domain="vision", owner=owner)
            final = sync_domain(
                "vision", REGISTRY["vision"], discovery, state, START, NOW, publish
            )
            self.assertEqual(final["deferred_prs"], [])
            self.assertEqual(final["errors"], [])
            self.assertEqual(ModelMetadataRecord.objects.count(), 2)
            self.assertEqual(ModelMetadataRevision.objects.count(), 2)
            self.assertEqual(state.read("vision")["deferred"], {})
            self.assertEqual(
                sync_domain(
                    "vision", REGISTRY["vision"], discovery, state, START, NOW, publish
                )["processed_prs"],
                [],
            )

    @override_settings(MODEL_METADATA_SYNC_ENABLED=True,
                       MODEL_METADATA_SYNC_START_AT='2026-10-03T12:00:00Z',
                       MODEL_METADATA_SYNC_EXPECTED_DATABASE='not-the-test-database')
    def test_wrong_database_cannot_publish(self):
        with patch('benchmarks.management.commands.sync_model_metadata.GitHub.reader') as reader:
            with self.assertRaises(CommandError):
                call_command('sync_model_metadata', stdout=StringIO())
        reader.assert_not_called()


@override_settings(MODEL_METADATA_SYNC_METRICS_ENABLED=True,
                   MODEL_METADATA_SYNC_METRICS_ENVIRONMENT='test-environment',
                   MODEL_METADATA_SYNC_METRICS_REGION='us-east-2')
class MonitoringTests(SimpleTestCase):
    def test_success_and_failure_use_one_environment_scoped_metric(self):
        from benchmarks.model_metadata.monitoring import report_run
        with patch('benchmarks.model_metadata.monitoring.boto3.client') as client:
            report_run(True)
            report_run(False)
        calls = client.return_value.put_metric_data.call_args_list
        self.assertEqual([call.kwargs['MetricData'][0]['Value'] for call in calls], [1, 0])
        self.assertEqual(calls[0].kwargs['Namespace'], 'BrainScore/MetadataSynchronization')
        self.assertEqual(calls[0].kwargs['MetricData'][0]['Dimensions'],
                         [{'Name': 'Environment', 'Value': 'test-environment'}])
        config = client.call_args.kwargs['config']
        self.assertEqual(config.connect_timeout, 3)
        self.assertEqual(config.retries['max_attempts'], 0)

    def test_reporting_failure_is_redacted_and_does_not_raise(self):
        from benchmarks.model_metadata.monitoring import report_run
        with patch('benchmarks.model_metadata.monitoring.boto3.client',
                   side_effect=RuntimeError('private credential')), \
                self.assertLogs('benchmarks.model_metadata.monitoring', level='WARNING') as logs:
            report_run(True)
        self.assertIn('RuntimeError', str(logs.output))
        self.assertNotIn('private credential', str(logs.output))

    @override_settings(MODEL_METADATA_SYNC_METRICS_ENVIRONMENT='')
    def test_missing_environment_cannot_mix_development_and_production_metrics(self):
        from benchmarks.model_metadata.monitoring import report_run
        with patch('benchmarks.model_metadata.monitoring.boto3.client') as client, \
                self.assertLogs('benchmarks.model_metadata.monitoring', level='WARNING'):
            report_run(True)
        client.assert_not_called()

    @override_settings(MODEL_METADATA_SYNC_METRICS_ENABLED=False)
    def test_disabled_monitoring_uses_no_aws_client(self):
        from benchmarks.model_metadata.monitoring import report_run
        with patch('benchmarks.model_metadata.monitoring.boto3.client') as client:
            report_run(True)
        client.assert_not_called()
