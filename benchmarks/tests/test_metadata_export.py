"""Bootstrap resolution must preserve siblings without executing plugins."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.test import SimpleTestCase

from benchmarks.model_metadata.github import metadata_available
from unittest import skipUnless


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
