"""Legacy proposals retain approved metadata, evidence, and shared-file siblings."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from unittest import skipIf, skipUnless
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase, override_settings
from benchmarks.models import Model, ModelMetadataRecord, ModelMetadataPublication, ModelMetadataRevision, User
from benchmarks.model_metadata.bootstrap import proposal_baseline, document_revision, read_bootstrap_entries
from benchmarks.model_metadata.github import GitHub, ProposalError, metadata_available
from benchmarks.model_metadata.writer import write_tables
from benchmarks.model_metadata.publishing import publish_pull_request
from benchmarks.tests.test_metadata_edit import REGISTRY, PATH, FakeGitHub


LEGACY = """models:
  example:
    total_parameter_count: 55
    architecture: DCNN
    extra_notes: Preserve submission notes
  sibling:
    total_parameter_count: 66
    extra_notes: Preserve sibling notes
"""


def approved_document():
    models = {}
    for identifier, count in [('example', 100), ('sibling', 200)]:
        models[identifier] = {
            'model': {'parameter_count': count, 'display_name': identifier.title()},
            'training': {'process': 'Pretraining, then supervised fine-tuning'},
            'data': {'summary': 'Pretrain + ImageNet', 'training_datasets': [
                {'name': 'Pretrain', 'role': 'pretraining'},
                {'name': 'ImageNet', 'role': 'fine_tuning'},
            ]},
            'use': {'applications': ['Classification'], 'limitations': ['Counting']},
            'sources': {'workbook': {'kind': 'unreviewed', 'citation': 'curation_workbook'}},
            'assertions': [{'path': path, 'status': 'verified', 'sources': ['workbook']}
                           for path in ['/model/parameter_count', '/model/display_name',
                                        '/training/process', '/data/summary',
                                        '/data/training_datasets', '/use/applications', '/use/limitations']],
        }
    return {'schema_version': '2.0', 'domain': 'vision', 'models': models}


def form_values(response):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(response.content, 'html.parser')
    values = {}
    for field in soup.select('form input, form textarea, form select'):
        name = field.get('name')
        if not name or field.has_attr('disabled'):
            continue
        if field.get('type') == 'checkbox':
            if field.has_attr('checked'):
                values[name] = field.get('value', 'on')
        elif field.name == 'select':
            option = field.select_one('option[selected]') or field.select_one('option')
            values[name] = option.get('value', '')
        elif field.name == 'textarea':
            value = field.get_text()
            values[name] = value[1:] if value.startswith('\n') else value
        else:
            values[name] = field.get('value', '')
    return soup.select_one('form')['action'], values


@skipUnless(metadata_available(), 'Install core with metadata support')
@skipIf(settings.TEST_RUNNER.endswith('ExistingDatabaseTestRunner'),
        'Run bootstrap database tests with web.metadata_test_settings on disposable PostgreSQL')
@override_settings(
    MODEL_METADATA_REPOSITORIES=REGISTRY, MODEL_METADATA_EDIT_ENABLED=True,
    METADATA_GITHUB_CLIENT_ID='client', METADATA_GITHUB_CLIENT_SECRET='secret',
    METADATA_GITHUB_APP_ID='1', METADATA_GITHUB_APP_PRIVATE_KEY='test-key',
    METADATA_GITHUB_CALLBACK_URL='http://testserver/metadata/github/callback/',
)
class BootstrapProposalTests(TestCase):
    def setUp(self):
        from brainscore_core.metadata.storage import to_tables

        cache.clear()
        self.user = User.objects._create_user('bootstrap@example.org', 'password', is_active=True)
        self.client.force_login(self.user)
        for name in ['example', 'sibling']:
            Model.objects.create(name=name, domain='vision', owner=self.user)
        write_tables(to_tables(approved_document()))
        self.model = SimpleNamespace(name='example', model_id=1)
        for patcher in [
            patch('benchmarks.views.metadata_edit.lookup', return_value=(self.model, None, REGISTRY['vision'])),
            patch('benchmarks.views.metadata_edit.GitHub.reader', side_effect=lambda config: GitHub('token', read_only=True)),
            patch('benchmarks.views.metadata_edit.GitHub.file', side_effect=self.file),
            patch('benchmarks.model_metadata.proposal_source.discover_model_folder', return_value=('example', '')),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def file(repository, path, ref):
        if path.endswith('/__init__.py'):
            return "model_registry['example'] = build\nmodel_registry['sibling'] = build", 'registry'
        if path == PATH:
            return LEGACY, 'blob'
        raise ProposalError('Not found', 404)

    def baseline(self):
        from benchmarks.model_metadata.proposal_source import proposal_document

        api = GitHub('token')
        repository, content, blob = proposal_document(api, REGISTRY['vision'], 'vision', PATH, 'example')
        return proposal_baseline(repository, content)

    def snapshot(self):
        from benchmarks.model_metadata.catalog import TABLES

        return {name: list(model.objects.order_by('pk').values())
                for name, (model, _) in TABLES.items()}

    def test_modal_populates_training_data_and_use_and_locks_verified_values(self):
        before = self.snapshot()
        response = self.client.get('/model/vision/1/metadata/edit/', HTTP_X_METADATA_MODAL='1')
        self.assertContains(response, 'Pretraining, then supervised fine-tuning')
        self.assertContains(response, 'Classification')
        self.assertContains(response, 'Counting')
        self.assertContains(response, 'ImageNet')
        self.assertContains(response, 'View verified metadata')
        form = response.context['form']
        count = next(field for field in form.fields.values()
                     if getattr(field, 'metadata_path', None) == '/model/parameter_count')
        self.assertEqual(count.initial, 100)
        self.assertTrue(count.disabled)
        self.assertIn('Verified', count.help_text)
        datasets = next(group for group in response.context['groups'] if group['path'] == '/data/training_datasets')
        self.assertFalse(datasets['editable'])
        self.assertEqual(len(datasets['formset'].initial), 2)
        self.assertEqual(self.snapshot(), before)

    def test_full_diff_preserves_all_sections_and_siblings_and_ignores_tampered_locked_fields(self):
        from brainscore_core.metadata import load

        before = self.snapshot()
        baseline = self.baseline()
        response = self.client.get('/model/vision/1/metadata/edit/', HTTP_X_METADATA_MODAL='1')
        action, values = form_values(response)
        fields = response.context['form'].fields
        rate = next(name for name, field in fields.items()
                    if getattr(field, 'metadata_path', None) == '/training/learning_rate')
        count = next(name for name, field in fields.items()
                     if getattr(field, 'metadata_path', None) == '/model/parameter_count')
        values.update({rate: '1e-4', count: '999', 'reason': 'Document the learning rate',
                       'source_url': 'https://example.org/config', 'source_kind': 'other'})
        response = self.client.post(action, values, HTTP_X_METADATA_MODAL='1')
        self.assertEqual(response.status_code, 302, response.content.decode())
        key = response.url.rstrip('/').rsplit('/', 1)[-1]
        draft = cache.get('metadata-draft:' + key)
        proposed = load(draft['after'])
        self.assertEqual(proposed['models']['example']['model']['parameter_count'], 100)
        self.assertEqual(proposed['models']['example']['training']['learning_rate'], '1e-4')
        for section in ['data', 'use']:
            self.assertEqual(proposed['models']['example'][section], baseline['models']['example'][section])
        self.assertEqual(proposed['models']['sibling'], baseline['models']['sibling'])
        self.assertEqual(proposed['models']['sibling']['legacy']['extra_notes'], 'Preserve sibling notes')
        self.assertEqual(draft['base_document_hash'], document_revision(baseline))
        review = self.client.get(response.url, HTTP_X_METADATA_MODAL='1')
        self.assertContains(review, 'converts a file containing 2 models to Schema v2.0')
        for section in ['training:', 'data:', 'use:', 'applications:', 'limitations:']:
            self.assertContains(review, section)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(ModelMetadataPublication.objects.exists())
        self.assertFalse(ModelMetadataRevision.objects.exists())

    def test_database_change_in_shared_sibling_rejects_a_stale_form(self):
        response = self.client.get('/model/vision/1/metadata/edit/', HTTP_X_METADATA_MODAL='1')
        action, values = form_values(response)
        ModelMetadataRecord.objects.filter(identifier='sibling').update(parameter_count=201)
        response = self.client.post(action, values, HTTP_X_METADATA_MODAL='1')
        self.assertContains(response, 'Metadata changed while you were editing', status_code=409)

    def test_submission_rechecks_database_baseline_before_any_github_write(self):
        from brainscore_core.metadata import dump

        baseline = self.baseline()
        after = deepcopy(baseline)
        after['models']['example']['training']['learning_rate'] = '1e-4'
        api = GitHub('token')
        ModelMetadataRecord.objects.filter(identifier='sibling').update(parameter_count=201)
        with patch.object(api, 'request') as request, patch.object(api, 'create_branch') as branch:
            with self.assertRaisesRegex(ProposalError, 'metadata changed'):
                api.create_proposal(REGISTRY['vision'], PATH, 'blob', dump(after), 'example',
                                    'Update rate', 'nonce', user_id=self.user.pk, github_login='contributor',
                                    initial=True, base_document_hash=document_revision(baseline))
            request.assert_not_called()
            branch.assert_not_called()

    def test_old_draft_and_sibling_changes_cannot_bypass_bootstrap_validation(self):
        from brainscore_core.metadata import dump

        baseline = self.baseline()
        api = GitHub('token')
        with patch.object(api, 'request') as request:
            with self.assertRaisesRegex(ProposalError, 'predates the current editor'):
                api.create_proposal(REGISTRY['vision'], PATH, 'blob', dump(baseline), 'example',
                                    'Old draft', 'nonce', user_id=self.user.pk, github_login='contributor', initial=True)
            changed = deepcopy(baseline)
            changed['models']['sibling']['use']['limitations'] = []
            with self.assertRaisesRegex(ProposalError, 'only change the selected model'):
                api.create_proposal(REGISTRY['vision'], PATH, 'blob', dump(changed), 'example',
                                    'Tampered sibling', 'nonce', user_id=self.user.pk, github_login='contributor',
                                    initial=True, base_document_hash=document_revision(baseline))
            request.assert_not_called()

    def test_app_payload_contains_complete_bootstrap_file_and_changes_only_selected_model(self):
        import base64
        from brainscore_core.metadata import dump, load

        baseline = self.baseline()
        after = deepcopy(baseline)
        after['models']['example']['training']['learning_rate'] = '1e-4'
        api = GitHub('token')
        calls = []

        def request(method, path, **kwargs):
            calls.append((method, path, kwargs))
            if method == 'GET' and path.endswith('/pulls'):
                return []
            return {'html_url': 'https://github.com/brain-score/vision/pull/10'}

        before = self.snapshot()
        with patch.object(api, 'request', side_effect=request), patch.object(api, 'create_branch'):
            result = api.create_proposal(REGISTRY['vision'], PATH, 'blob', dump(after), 'example',
                                         'Update rate', 'nonce', user_id=self.user.pk, github_login='contributor',
                                         initial=True, base_document_hash=document_revision(baseline))
        self.assertEqual(result, 'https://github.com/brain-score/vision/pull/10')
        payload = next(kwargs['json'] for method, path, kwargs in calls if method == 'PUT')
        self.assertEqual(load(base64.b64decode(payload['content']).decode()), after)
        body = next(kwargs['json']['body'] for method, path, kwargs in calls
                    if method == 'POST' and path.endswith('/pulls'))
        self.assertIn('converts a file containing 2 models to Schema v2.0', body)
        self.assertEqual(after['models']['sibling'], baseline['models']['sibling'])
        self.assertEqual(self.snapshot(), before)

    def test_first_publication_rejects_missing_bootstrap_data_without_writing_any_model(self):
        before = self.snapshot()
        incomplete = deepcopy(approved_document())
        del incomplete['models']['sibling']['use']
        with self.assertRaisesRegex(ProposalError, 'Initial publication omits existing metadata for sibling'):
            publish_pull_request('vision', 10, FakeGitHub(incomplete))
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(ModelMetadataPublication.objects.exists())
        self.assertFalse(ModelMetadataRevision.objects.exists())

    def test_complete_shared_first_publication_preserves_approved_fields(self):
        baseline = self.baseline()
        after = deepcopy(baseline)
        after['models']['example']['training']['learning_rate'] = '1e-4'
        publish_pull_request('vision', 10, FakeGitHub(after))
        self.assertEqual(ModelMetadataPublication.objects.count(), 2)
        self.assertEqual(ModelMetadataRecord.objects.get(identifier='sibling').parameter_count, 200)
        sibling = ModelMetadataPublication.objects.get(identifier='sibling').document
        self.assertEqual(sibling, baseline['models']['sibling'])
        self.assertEqual(ModelMetadataRecord.objects.get(identifier='example').learning_rate, '1e-4')

    def test_bootstrap_values_are_not_guessed_into_primary_source_types(self):
        entries = read_bootstrap_entries('vision', ['EXAMPLE'])
        self.assertEqual(entries['example']['sources']['curation_workbook']['kind'], 'unreviewed')
        self.assertTrue(any(a['status'] == 'verified' for a in entries['example']['assertions']))

    def test_repository_legacy_values_fill_undocumented_gaps_without_overriding_verified_values(self):
        from brainscore_core.metadata.storage import from_legacy

        ModelMetadataRecord.objects.filter(identifier='example').update(trainable_layers=None)
        doc = {'schema_version': '2.0', 'domain': 'vision', 'models': {
            'EXAMPLE': from_legacy({'total_parameter_count': 55, 'trainable_layers': 12}, 'vision'),
        }}
        baseline = proposal_baseline(doc, LEGACY)
        self.assertEqual(baseline['models']['EXAMPLE']['model']['parameter_count'], 100)
        self.assertEqual(baseline['models']['EXAMPLE']['model']['trainable_layers'], '12')
        self.assertEqual(baseline['models']['EXAMPLE']['legacy']['total_parameter_count'], 55)

    def test_bootstrap_lookup_keeps_domains_separate_and_excludes_published_models(self):
        ModelMetadataRecord.objects.create(domain='language', identifier='example', parameter_count=700)
        self.assertEqual(read_bootstrap_entries('language', ['example'])['example']['model']['parameter_count'], 700)
        self.assertEqual(read_bootstrap_entries('vision', ['example'])['example']['model']['parameter_count'], 100)
        ModelMetadataPublication.objects.create(
            domain='vision', identifier='example', repository='brain-score/vision', path=PATH,
            commit_sha='a' * 40, blob_sha='b' * 40, pull_request=10, document={},
        )
        self.assertEqual(read_bootstrap_entries('vision', ['example']), {})


@skipUnless(metadata_available(), 'Install core with metadata support')
class VerifiedPolicyTests(SimpleTestCase):
    def test_only_verified_status_locks_metadata_regardless_of_source_or_value(self):
        from benchmarks.model_metadata.policy import editability, protected_changes
        from brainscore_core.metadata.contract import put_path

        for kind in ['other', 'paper', 'huggingface', 'unreviewed']:
            for status in ['verified', 'probable', 'uncertain', 'undocumented', None]:
                for path, value in [('/model/parameter_count', 100),
                                    ('/model/visual_degrees', 8),
                                    ('/use/applications', ['Classification'])]:
                    for populated in [True, False]:
                        with self.subTest(kind=kind, status=status, path=path, populated=populated):
                            entry = {'sources': {'source': {'kind': kind, 'url': 'https://example.org/source'}},
                                     'assertions': []}
                            if status is not None:
                                entry['assertions'] = [{'path': path, 'status': status, 'sources': ['source']}]
                            put_path(entry, path, value if populated else None)
                            self.assertEqual(editability(entry, path)[0], status != 'verified')
                            changed = deepcopy(entry)
                            put_path(changed, path, None if populated else value)
                            self.assertEqual(path in protected_changes(entry, changed), status == 'verified')

    def test_specific_unverified_assertion_overrides_inherited_verified_status(self):
        from benchmarks.model_metadata.policy import editability, protected_changes

        entry = approved_document()['models']['example']
        entry['assertions'] = [
            {'path': '/model', 'status': 'verified', 'sources': ['workbook']},
            {'path': '/model/parameter_count', 'status': 'probable', 'sources': ['workbook']},
        ]
        self.assertTrue(editability(entry, '/model/parameter_count')[0])
        self.assertFalse(editability(entry, '/model/display_name')[0])
        changed = deepcopy(entry)
        changed['model']['parameter_count'] = 999
        self.assertEqual(protected_changes(entry, changed), [])

    def test_app_allows_unverified_primary_and_unreviewed_metadata_edits(self):
        from brainscore_core.metadata import dump
        from benchmarks.tests.test_metadata_edit import document

        for kind in ['paper', 'huggingface', 'unreviewed']:
            with self.subTest(kind=kind):
                before = document(kind=kind)
                after = deepcopy(before)
                after['models']['example']['model']['parameter_count'] = 999
                api = GitHub('token')
                def request(method, path, **kwargs):
                    if method == 'GET' and path.endswith('/pulls'):
                        return []
                    return {'html_url': 'https://github.com/brain-score/vision/pull/10'}
                with patch.object(api, 'file', return_value=(dump(before), 'blob')), \
                        patch.object(api, 'create_branch') as branch, \
                        patch.object(api, 'request', side_effect=request) as calls:
                    result = api.create_proposal(REGISTRY['vision'], PATH, 'blob', dump(after), 'example',
                                                 'Correct unverified metadata', 'nonce', user_id=1,
                                                 github_login='contributor')
                self.assertEqual(result, 'https://github.com/brain-score/vision/pull/10')
                branch.assert_called_once()
                self.assertTrue(any(call.args[0] == 'PUT' for call in calls.call_args_list))

    def test_inherited_verified_assertion_locks_child_fields(self):
        from benchmarks.model_metadata.policy import editability, protected_changes

        entry = approved_document()['models']['example']
        entry['sources']['workbook']['kind'] = 'other'
        entry['assertions'] = [{'path': '/model', 'status': 'verified', 'sources': ['workbook']}]
        self.assertFalse(editability(entry, '/model/parameter_count')[0])
        changed = deepcopy(entry)
        changed['assertions'][0]['status'] = 'probable'
        self.assertIn('/model/parameter_count', protected_changes(entry, changed))

    def test_verified_other_source_value_or_evidence_cannot_be_changed_or_downgraded(self):
        from brainscore_core.metadata import dump
        from benchmarks.model_metadata.policy import editability, protected_changes
        from benchmarks.tests.test_metadata_edit import document

        before = document()['models']['example']
        before['assertions'][0]['status'] = 'verified'
        self.assertFalse(editability(before, '/model/parameter_count')[0])
        for change in ['value', 'status', 'source']:
            after = deepcopy(before)
            if change == 'value':
                after['model']['parameter_count'] = 999
            elif change == 'status':
                after['assertions'][0]['status'] = 'probable'
            else:
                after['sources']['source']['url'] = 'https://example.org/replaced'
            self.assertIn('/model/parameter_count', protected_changes(before, after))
            original = {'schema_version': '2.0', 'domain': 'vision', 'models': {'example': before}}
            proposed = dict(original, models={'example': after})
            api = GitHub('token')
            with patch.object(api, 'file', return_value=(dump(original), 'blob')), patch.object(api, 'request') as request:
                with self.assertRaisesRegex(ProposalError, 'protected field'):
                    api.create_proposal(REGISTRY['vision'], PATH, 'blob', dump(proposed), 'example',
                                        'Tampered verified field', 'nonce', user_id=1, github_login='contributor')
                request.assert_not_called()

    def test_existing_v2_repository_metadata_remains_authoritative(self):
        from brainscore_core.metadata import dump

        doc = approved_document()
        with patch('benchmarks.model_metadata.bootstrap.read_bootstrap_entries') as reader:
            self.assertEqual(proposal_baseline(doc, dump(doc)), doc)
            reader.assert_not_called()
