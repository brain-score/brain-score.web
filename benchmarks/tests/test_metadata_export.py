"""Bootstrap resolution must preserve siblings without executing plugins."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from benchmarks.model_metadata.github import metadata_available
from unittest import skipUnless


@skipUnless(metadata_available(), 'Install core with metadata support')
class MetadataExportTests(SimpleTestCase):
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
