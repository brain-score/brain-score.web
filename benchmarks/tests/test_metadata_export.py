"""Bootstrap resolution must preserve siblings without executing plugins."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.conf import settings
from django.db import connection
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from io import StringIO

from benchmarks.model_metadata.github import metadata_available
from unittest import skipIf, skipUnless


@skipUnless(metadata_available(), 'Install core with metadata support')
class MetadataExportTests(SimpleTestCase):
    def test_workbook_derivation_survives_yaml_export(self):
        from scripts.export_model_metadata_yaml import export
        from brainscore_core.metadata import load
        from brainscore_core.metadata.storage import to_tables
        document = {'schema_version': '2.0', 'domain': 'vision', 'models': {'exact-id': {
            'training': {'objective': 'Classification', 'batch_size': '256'},
            'sources': {'curation_workbook': {'kind': 'unreviewed', 'citation': 'Workbook'}},
            'assertions': [
                {'path': '/training/objective', 'status': 'probable', 'sources': ['curation_workbook']},
                {'path': '/training/batch_size', 'status': 'uncertain', 'sources': ['curation_workbook']},
            ],
        }}}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / 'checkout/brainscore_vision/models/example'
            plugin.mkdir(parents=True)
            (plugin / '__init__.py').write_text("model_registry['exact-id'] = lambda: None\n")
            claims = {'source': {'filename': 'workbook.csv',
                                 'color_workbook': {'filename': 'workbook.xlsx'}}, 'models': [{
                'identifier': 'exact-id', 'cell_annotations': {
                    'training_objective': {'sheet': 'Sheet1', 'address': 'E15',
                                           'derivation': 'Inferred by Claude from source material'},
                    'batch_size': {'sheet': 'Sheet1', 'address': 'E20',
                                   'derivation': 'Inferred by Claude without source material'},
                },
            }]}
            (root / 'workbook-claims.json').write_text(json.dumps(claims))
            tables = to_tables(document)
            for assertion in tables['assertions']:
                assertion['source'] = 'curation_workbook'
            with patch('scripts.export_model_metadata_yaml.read_catalog', return_value=tables):
                export(root, 'vision', root / 'checkout', root / 'out', include_registered=True)
            entry = load((root / 'out/brainscore_vision/models/example/metadata.yaml').read_text())['models']['exact-id']
            for assertion, field, status, cell, derivation in zip(
                    entry['assertions'], ['training_objective', 'batch_size'],
                    ['probable', 'uncertain'], ['E15', 'E20'], ['from source material', 'without source material']):
                self.assertEqual(assertion['status'], status)
                evidence = entry['sources'][assertion['sources'][0]]
                self.assertEqual(evidence['kind'], 'unreviewed')
                self.assertIn('Sheet1!' + cell, evidence['citation'])
                self.assertIn(derivation, evidence['citation'])

    def test_new_file_resolves_literal_identifier_without_execution(self):
        from scripts.export_model_metadata_yaml import export
        from brainscore_core.metadata import load
        from brainscore_core.metadata.storage import to_tables
        document = {'schema_version': '2.0', 'domain': 'vision', 'models': {'exact-id': {}}}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / 'checkout/brainscore_vision/models/example'
            plugin.mkdir(parents=True)
            (plugin / '__init__.py').write_text(
                "raise RuntimeError('must not execute')\nmodel_registry['exact-id'] = lambda: None\n")
            claims = b'{"models": [{"identifier": "exact-id", "raw": {"dataset_size": "Unconfirmed"}}]}\n'
            (root / 'workbook-claims.json').write_bytes(claims)
            with patch('scripts.export_model_metadata_yaml.read_catalog', return_value=to_tables(document)):
                report = export(root, 'vision', root / 'checkout', root / 'out', include_registered=True)
            self.assertEqual(report, {'files': 1, 'unmatched': []})
            result = load((root / 'out/brainscore_vision/models/example/metadata.yaml').read_text())
            self.assertIn('exact-id', result['models'])
            self.assertEqual((root / 'out/evidence/workbook-claims.json').read_bytes(), claims)

    def test_missing_entry_preserves_existing_yaml_extension_and_sibling(self):
        from scripts.export_model_metadata_yaml import export
        from brainscore_core.metadata import load
        from brainscore_core.metadata.storage import to_tables
        document = {'schema_version': '2.0', 'domain': 'vision', 'models': {'exact-id': {}}}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            plugin = root / 'checkout/brainscore_vision/models/example'
            plugin.mkdir(parents=True)
            (plugin / '__init__.py').write_text("model_registry['exact-id'] = lambda: None\n")
            (plugin / 'metadata.yml').write_text('models:\n  sibling:\n    architecture: DCNN\n')
            with patch('scripts.export_model_metadata_yaml.read_catalog', return_value=to_tables(document)):
                export(root, 'vision', root / 'checkout', root / 'out', include_registered=True)
            result = load((root / 'out/brainscore_vision/models/example/metadata.yml').read_text())
            self.assertEqual(result['models']['sibling']['legacy'], {'architecture': 'DCNN'})
            self.assertIn('exact-id', result['models'])

    def test_ambiguous_registration_fails_instead_of_picking_a_plugin(self):
        from scripts.export_model_metadata_yaml import export
        from brainscore_core.metadata.storage import to_tables
        document = {'schema_version': '2.0', 'domain': 'vision', 'models': {'exact-id': {}}}
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('one', 'two'):
                plugin = root / 'checkout/brainscore_vision/models' / name
                plugin.mkdir(parents=True)
                (plugin / '__init__.py').write_text("model_registry['exact-id'] = lambda: None\n")
            with patch('scripts.export_model_metadata_yaml.read_catalog', return_value=to_tables(document)):
                with self.assertRaisesMessage(ValueError, 'Ambiguous registered model'):
                    export(root, 'vision', root / 'checkout', root / 'out', include_registered=True)


@skipUnless(metadata_available(), 'Install core with metadata support')
@skipIf(settings.TEST_RUNNER.endswith('ExistingDatabaseTestRunner'),
        'Run bootstrap export tests on disposable PostgreSQL')
class DatabaseBootstrapExportTests(TestCase):
    def setUp(self):
        from benchmarks.models import Model, User
        from benchmarks.model_metadata.writer import write_tables
        from brainscore_core.metadata.storage import to_tables
        from benchmarks.tests.test_metadata_bootstrap import approved_document
        user = User.objects.create(email='export@example.org')
        for identifier in ('example', 'sibling'):
            Model.objects.create(name=identifier, domain='vision', owner=user)
        document = approved_document()
        document['models']['sibling']['model'].update(parameter_count=0, recurrent=False)
        document['models']['sibling']['assertions'].append({
            'path': '/model/recurrent', 'status': 'verified', 'sources': ['workbook']})
        write_tables(to_tables(document))
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / 'checkout'
        self.folder = self.checkout / 'brainscore_vision/models/example'
        self.folder.mkdir(parents=True)
        (self.folder / '__init__.py').write_text(
            "raise RuntimeError('never execute plugins')\n"
            "model_registry['example'] = build\nmodel_registry['sibling'] = build\n")
        (self.folder / 'metadata.yml').write_text(
            'models:\n  example:\n    architecture: DCNN\n  sibling:\n    extra_notes: Preserve sibling notes\n')

    def export(self):
        from benchmarks.model_metadata.bootstrap_export import export_bootstrap
        return export_bootstrap('vision', self.checkout, self.root / 'output')

    def test_preserves_values_evidence_siblings_and_extension_without_database_writes(self):
        from brainscore_core.metadata import load
        from brainscore_core.metadata.policy import evidence
        from benchmarks.model_metadata.bootstrap import read_bootstrap_entries
        from benchmarks.model_metadata.catalog import TABLES
        before = {name: list(model.objects.order_by('pk').values()) for name, (model, _) in TABLES.items()}
        baseline = read_bootstrap_entries('vision', ['example', 'sibling'])
        report = self.export()
        self.assertEqual(report['covered_models'], 2)
        self.assertEqual(report['blocked'], [])
        document = load((self.root / 'output/brainscore_vision/models/example/metadata.yml').read_text())
        self.assertEqual(set(document['models']), {'example', 'sibling'})
        self.assertEqual(document['models']['sibling']['legacy']['extra_notes'], 'Preserve sibling notes')
        for identifier in ('example', 'sibling'):
            self.assertEqual(document['models'][identifier]['model']['parameter_count'],
                             baseline[identifier]['model']['parameter_count'])
            self.assertEqual(evidence(document['models'][identifier], '/model/parameter_count'),
                             evidence(baseline[identifier], '/model/parameter_count'))
        self.assertIs(document['models']['sibling']['model']['recurrent'], False)
        self.assertEqual(document['models']['sibling']['model']['parameter_count'], 0)
        self.assertEqual(before, {name: list(model.objects.order_by('pk').values())
                                 for name, (model, _) in TABLES.items()})
        self.assertFalse((self.root / 'output/brainscore_vision/models/example/metadata.yaml').exists())

    def test_authoritative_v2_file_requires_separate_reconciliation(self):
        from brainscore_core.metadata import dump
        from benchmarks.tests.test_metadata_bootstrap import approved_document
        (self.folder / 'metadata.yml').write_text(dump(approved_document()))
        report = self.export()
        self.assertEqual(report['covered_models'], 0)
        self.assertEqual(len(report['blocked']), 2)
        self.assertFalse(report['files'])

    def test_unknown_sibling_blocks_the_complete_file(self):
        with (self.folder / 'metadata.yml').open('a') as stream:
            stream.write('  unregistered:\n    architecture: DCNN\n')
        report = self.export()
        self.assertEqual(report['covered_models'], 0)
        self.assertIn('not registered', report['blocked'][0]['reason'])

    def test_ambiguous_identity_is_not_guessed(self):
        (self.folder / 'metadata.yml').unlink()
        other = self.folder.parent / 'other'
        other.mkdir()
        (other / '__init__.py').write_text("model_registry['example'] = build\n")
        report = self.export()
        self.assertEqual(report['identifiers'], ['sibling'])
        self.assertEqual(report['blocked'][0]['identifier'], 'example')

    def test_output_cannot_overwrite_a_checkout_or_existing_proposal(self):
        from benchmarks.model_metadata.bootstrap_export import export_bootstrap
        with self.assertRaises(ValueError):
            export_bootstrap('vision', self.checkout, self.checkout / 'output')
        self.export()
        with self.assertRaises(ValueError):
            self.export()


@skipUnless(metadata_available(), 'Install core with metadata support')
@skipIf(settings.TEST_RUNNER.endswith('ExistingDatabaseTestRunner'),
        'Run snapshot command tests on disposable PostgreSQL')
class BootstrapSnapshotCommandTests(TransactionTestCase):
    def test_target_mismatch_cannot_export(self):
        with patch('benchmarks.management.commands.export_model_metadata_bootstrap.export_bootstrap') as export:
            with self.assertRaisesMessage(CommandError, 'does not match'):
                call_command('export_model_metadata_bootstrap', domain='vision',
                             checkout='/unused', output='/unused', expected_database='wrong-target')
        export.assert_not_called()

    def test_export_reads_an_enforced_repeatable_read_only_transaction(self):
        def inspect(*args):
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_read_only')
                self.assertEqual(cursor.fetchone()[0], 'on')
                cursor.execute('SHOW transaction_isolation')
                self.assertEqual(cursor.fetchone()[0], 'repeatable read')
            return {'blocked': []}
        with patch('benchmarks.management.commands.export_model_metadata_bootstrap.export_bootstrap', side_effect=inspect):
            call_command('export_model_metadata_bootstrap', domain='vision',
                         checkout='/unused', output='/unused',
                         expected_database=connection.settings_dict['NAME'], stdout=StringIO())
