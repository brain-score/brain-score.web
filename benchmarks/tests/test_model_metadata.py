import csv
import importlib.util
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from unittest import skipIf
from django.conf import settings

from bs4 import BeautifulSoup
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import RequestFactory, SimpleTestCase, TestCase

from benchmarks.model_metadata import repository
from benchmarks.model_metadata.catalog import TABLES, read_catalog, scalar_fields
from benchmarks.models import ModelMetadataRecord, ModelMetadataRelationship
from benchmarks.views.model import build_model_card_metadata, view

DATA = Path(__file__).resolve().parents[1] / 'model_metadata' / 'data'


@skipIf(settings.TEST_RUNNER.endswith('ExistingDatabaseTestRunner'),
        'Run metadata database tests with web.metadata_test_settings on disposable PostgreSQL')
class MetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('import_model_metadata', DATA, stdout=StringIO())

    def import_catalog(self, directory=DATA, **options):
        call_command('import_model_metadata', directory, stdout=StringIO(), **options)

    def modified_catalog(self, table, change):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for path in DATA.glob('*.csv'):
            with path.open(newline='') as stream:
                reader = csv.DictReader(stream)
                fields, rows = reader.fieldnames, list(reader)
            if path.stem == table:
                rows = change(rows)
            with (Path(directory.name) / path.name).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        return directory.name

    def test_every_imported_scalar_and_child_value_matches_catalog(self):
        tables = read_catalog(DATA)
        for name, (model, ordering) in TABLES.items():
            with self.subTest(table=name):
                actual = []
                for record in model.objects.select_related(*([] if name == 'models' else ['record'])):
                    row = {field.name: getattr(record, field.name) for field in scalar_fields(model)}
                    if name != 'models':
                        row.update(domain=record.record.domain, identifier=record.record.identifier)
                    actual.append(row)
                self.assertCountEqual(actual, tables[name])

    def test_all_cards_match_csv_context(self):
        tables = {}
        for name in TABLES:
            with (DATA / f'{name}.csv').open(newline='', encoding='utf-8') as stream:
                tables[name] = list(csv.DictReader(stream))
        expected = repository._build_catalog(tables)
        for (domain, identifier), card in expected.items():
            with self.subTest(identifier=identifier):
                actual = repository.get_model_metadata(domain, identifier)
                self.assertEqual(actual, card)

    def test_repeat_import_retains_record_ids_and_unrelated_models(self):
        unrelated = ModelMetadataRecord.objects.create(domain='vision', identifier='unrelated')
        ids = dict(ModelMetadataRecord.objects.values_list('identifier', 'pk'))
        self.import_catalog()
        self.assertEqual(ids, dict(ModelMetadataRecord.objects.values_list('identifier', 'pk')))
        self.assertTrue(ModelMetadataRecord.objects.filter(pk=unrelated.pk).exists())

    def test_partial_import_preserves_other_models(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        selected = ModelMetadataRecord.objects.order_by('identifier').first().identifier
        for path in DATA.glob('*.csv'):
            with path.open(newline='') as stream:
                reader = csv.DictReader(stream)
                fields, rows = reader.fieldnames, [row for row in reader if row['identifier'] == selected]
            with (Path(directory.name) / path.name).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        self.import_catalog(directory.name)
        self.assertEqual(ModelMetadataRecord.objects.count(), 78)

    def test_dry_run_and_empty_catalog_never_delete(self):
        self.import_catalog(dry_run=True, wipe=True)
        self.assertEqual(ModelMetadataRecord.objects.count(), 78)
        directory = self.modified_catalog('models', lambda rows: [])
        for wipe in (False, True):
            with self.subTest(wipe=wipe), self.assertRaises(CommandError):
                self.import_catalog(directory, wipe=wipe)
            self.assertEqual(ModelMetadataRecord.objects.count(), 78)

    def test_invalid_input_leaves_database_unchanged(self):
        cases = [
            ('models', 'recurrent', 'maybe'),
            ('models', 'parameter_count', '-1'),
            ('models', 'visual_degrees', 'nan'),
            ('models', 'identifier', ''),
            ('models', 'weights_provider', 'x' * 501),
            ('assertions', 'status', 'inferred'),
            ('model_datasets', 'role', 'unknown'),
            ('contributors', 'identifier', 'orphan'),
        ]
        for table, field, value in cases:
            with self.subTest(table=table, field=field):
                def change(rows):
                    rows[0][field] = value
                    return rows
                directory = self.modified_catalog(table, change)
                with self.assertRaises(CommandError):
                    self.import_catalog(directory, wipe=True)
                self.assertEqual(ModelMetadataRecord.objects.count(), 78)

    def test_duplicate_case_and_child_keys_are_rejected(self):
        for table in ('models', 'assertions', 'model_datasets'):
            def change(rows):
                row = dict(rows[0])
                row['identifier'] = row['identifier'].upper()
                return rows + [row]
            with self.subTest(table=table), self.assertRaises(CommandError):
                self.import_catalog(self.modified_catalog(table, change))

    def test_missing_headers_rejected(self):
        directory = self.modified_catalog('models', lambda rows: rows)
        path = Path(directory) / 'models.csv'
        path.write_text(path.read_text().replace('training_objective', 'unknown_column', 1))
        with self.assertRaisesMessage(CommandError, 'invalid headers'):
            self.import_catalog(directory)

    def test_database_failure_rolls_back_wipe_and_updates(self):
        with patch('benchmarks.models.ModelMetadataDataset.objects.bulk_create',
                   side_effect=IntegrityError('simulated failure')):
            with self.assertRaisesMessage(CommandError, 'rolled back'):
                self.import_catalog(wipe=True)
        self.assertEqual(ModelMetadataRecord.objects.count(), 78)
        self.assertEqual(TABLES['model_datasets'][0].objects.count(), 225)

    def test_upgrade_normalizes_legacy_confidence_statuses(self):
        from django.apps import apps
        from django.db import connection
        from importlib import import_module
        assertions = TABLES['assertions'][0]
        record = assertions.objects.first()
        migration = import_module('benchmarks.migrations.0029_complete_model_metadata')
        for old, new in (('inferred', 'probable'), ('low', 'uncertain')):
            assertions.objects.filter(pk=record.pk).update(status=old)
            migration.normalize_confidence(apps, SimpleNamespace(connection=connection))
            record.refresh_from_db()
            self.assertEqual(record.status, new)

    def test_case_insensitive_constraint_and_lookup_preserve_checkpoints(self):
        name = 'vit_base_patch16_clip_224:openai_ft_in1k'
        self.assertIsNotNone(repository.get_model_metadata('vision', name.upper()))
        self.assertIsNone(repository.get_model_metadata('vision', name.replace('in1k', 'in12k_in1k')))
        with self.assertRaises(IntegrityError), transaction.atomic():
            ModelMetadataRecord.objects.create(domain='VISION', identifier=name.upper())

    def test_database_updates_are_visible_without_worker_restart(self):
        record = ModelMetadataRecord.objects.first()
        repository.get_model_metadata(record.domain, record.identifier)
        record.training_objective = 'Updated objective'
        record.save()
        with patch('csv.DictReader', side_effect=AssertionError('runtime CSV read')):
            self.assertEqual(repository.get_model_metadata(record.domain, record.identifier)['objective'],
                             'Updated objective')

    def test_database_read_has_bounded_queries(self):
        with self.assertNumQueries(8):
            repository.get_model_metadata('vision', 'resnet-50-robust')

    def test_fallback_and_empty_page_context(self):
        for meta in ({}, {'architecture': 'CNN', 'total_parameter_count': 25000000}):
            card = build_model_card_metadata(SimpleNamespace(name='not-curated', model_meta=meta))
            self.assertEqual(card['source_label'], 'Submission metadata')
            self.assertEqual(card['verification']['verified'], 0)
            self.assertEqual(card['verification']['total'], len(repository.ALL_FIELD_SLOTS))

    def test_lineage_casing_cycles_and_external_base(self):
        for name in ('test-parent', 'test-child', 'test-sibling'):
            ModelMetadataRecord.objects.create(domain='vision', identifier=name, display_name=name)
        for child, base in [('test-child', 'TEST-PARENT'), ('test-sibling', 'test-parent'),
                            ('test-parent', 'TEST-CHILD')]:
            ModelMetadataRelationship.objects.create(
                record=ModelMetadataRecord.objects.get(identifier=child), ordinal=0,
                base_identifier=base, base_name=base, relationship='variant_of')
        card = repository.get_model_metadata('vision', 'test-child')
        self.assertLessEqual(len(card['lineage']['ancestors']), 2)
        self.assertIn('test-sibling', [row['identifier'] for row in card['lineage']['related_models']])
        ModelMetadataRelationship.objects.filter(record__identifier='test-parent').update(base_identifier='external')
        card = repository.get_model_metadata('vision', 'test-child')
        self.assertIn('external', repository.lineage_identifiers(card))
        linked = repository.with_model_card_ids(card, {'EXTERNAL': 12, 'test-parent': 13})
        self.assertEqual(linked['lineage']['ancestors'][0]['model_card_id'], 12)

    def test_complete_page_preserves_original_metadata_layout(self):
        model = SimpleNamespace(name='resnet-50-robust', domain='vision', public=True,
                                model_id=1, id=1, user=None, submitter=None, scores=[],
                                model_meta={}, visual_degrees=8, layers={})
        request = RequestFactory().get('/model/vision/1')
        request.user = AnonymousUser()
        context = dict(models=[model], benchmarks=[], benchmark_parents={},
                       uniform_parents={}, not_shown_set=set(), BASE_DEPTH=1)
        with patch('benchmarks.views.model.FinalModelContext.objects.get', return_value=model), \
                patch('benchmarks.views.model.get_context', return_value=context), \
                patch('benchmarks.views.model.load_and_build_score_trend', return_value=None), \
                patch('benchmarks.views.model.load_and_build_rank_trend', return_value=None):
            response = view(request, 1, 'vision')
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertIsNotNone(soup.select_one('h3#scores'))
        for selector in ('.mc-hero-stats', '.mc-specs', '.mc-grid', '.mc-use-grid',
                         '.model-eval-io', '.mc-verification-bar'):
            self.assertIsNotNone(soup.select_one(selector), selector)
        self.assertContains(response, 'Curated metadata')
        self.assertIn('width=device-width', soup.select_one('meta[name=viewport]')['content'])


class ConverterConfidenceTests(SimpleTestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[2] / 'scripts/build_model_metadata_catalog.py'
        spec = importlib.util.spec_from_file_location('metadata_converter', path)
        self.converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.converter)

    def test_parameter_counts_preserve_exactness_without_rounding(self):
        for text, expected in [('61,100,840', (61100840, True)),
                               ('about 61,100,840', (61100840, False)),
                               ('61100840.0', (61100840, True)),
                               ('~20M', (20000000, False))]:
            with self.subTest(text=text):
                self.assertEqual(self.converter.parse_parameter_count(text), expected)

    def test_meaningful_negative_and_uncertainty_notes_are_preserved(self):
        for text in ['No architecture; raw pixels', 'No training data - hand-crafted filters',
                     'Not known for this checkpoint; paper reports another variant']:
            self.assertEqual(self.converter._clean(text), text)
        for text in ['N/A', 'unknown', 'not documented']:
            self.assertIsNone(self.converter._clean(text))
        self.assertEqual(self.converter.classify_confidence('Medium-High (weights uncertain)'),
                         'medium_high')

    def test_scratch_training_is_not_fine_tuning(self):
        model = {'identifier': 'convnext_tiny_imagenet_full_seed-0', 'raw': {
            'base_model': 'ConvNeXt-Tiny (trained from scratch, not fine-tuned)',
            'training_process': 'Train from scratch'}}
        rows = self.converter.build_relationships(model, {})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['relationship'], 'variant_of')
        model['raw']['base_model'] = 'None (purpose-built architecture)'
        self.assertEqual(self.converter.build_relationships(model, {}), [])

    def test_multiple_named_parents_are_preserved(self):
        model = {'identifier': 'AlexNet_SIN_fov12',
                 'raw': {'base_model': 'AlexNet, AlexNet-SIN'}}
        rows = self.converter.build_relationships(model, {'alexnet': 'alexnet', 'alexnetsin': 'AlexNet_SIN'})
        self.assertEqual([r['base_identifier'] for r in rows], ['alexnet', 'AlexNet_SIN'])

    def test_dataset_notes_do_not_become_datasets_or_disappear(self):
        rows = self.converter.parse_training_datasets(
            'ImageNet-1k; single-stage training, no separate pretraining corpus',
            '~1.28M training images / 50K validation images')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'ImageNet-1k')
        self.assertIn('no separate pretraining corpus', rows[0]['count'])
        self.assertIn('50K validation', rows[0]['count'])
        self.assertEqual(self.converter.parse_training_datasets('No training data - hand-crafted', ''), [])

    def test_unknown_dataset_claims_are_not_dataset_names(self):
        for text in ['training_dataset field is null in metadata; identifier implies ImageNet',
                     'Unconfirmed - checkpoint training data not stated',
                     'N/A - untrained, no training data']:
            self.assertEqual(self.converter.parse_training_datasets(text, ''), [])
        rows = self.converter.parse_training_datasets(
            'Base CrossViT: ImageNet; adversarial fine-tuning dataset not specified', '')
        self.assertEqual([(r['name'], r['role']) for r in rows], [('ImageNet', 'pretraining')])
        self.assertIn('not specified', rows[0]['count'])

    def test_dataset_stage_arrows_and_parenthetical_notes(self):
        rows = self.converter.parse_training_datasets(
            'ImageNet-22k (pretrain; original release) -> ImageNet-1k (fine-tune)', '')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['name'], 'ImageNet-22k (pretrain; original release)')
        self.assertEqual(rows[1]['role'], 'fine_tuning')
        rows = self.converter.parse_training_datasets(
            'ImageNet-22k (pretrain) → ImageNet-1k (fine-tune)', '')
        self.assertEqual([r['role'] for r in rows], ['pretraining', 'fine_tuning'])
        rows = self.converter.parse_training_datasets(
            'Stage 1: ImageNet-22k Stage 2: ImageNet-1k', '')
        self.assertEqual([r['role'] for r in rows], ['pretraining', 'fine_tuning'])
        self.assertEqual([r['name'] for r in rows], ['ImageNet-22k', 'ImageNet-1k'])

    def test_final_crop_is_input_resolution(self):
        self.assertEqual(self.converter.parse_resolution(
            'Resize to 256x256, center crop to 224x224'), (224, 224, 3))

    def test_conversion_preserves_original_notes_in_evidence(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            workbook = root / 'workbook.csv'
            notes = 'ImageNet-22k ~14M; ImageNet-1k ~1.28M; checkpoint scale unconfirmed'
            with workbook.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['Field', 'Type', 'Source', 'Question', 'example'])
                for label, value in [
                    ('model_ID', 'example'), ('base model', 'parent'),
                    ('Dataset_source (training_data)',
                     'Pretrain: ImageNet-22k; Fine-tune: ImageNet-1k'),
                    ('dataset_size', notes), ('Creator', 'Example author'),
                    ('Recommended applications', 'Classification'),
                ]:
                    writer.writerow([label, '', '', '', value])
            with patch('sys.argv', ['converter', str(workbook), '--out', str(root / 'out')]):
                self.converter.main()
            import json
            evidence = json.loads((root / 'out/workbook-claims.json').read_text())
            self.assertEqual(evidence['models'][0]['raw']['dataset_size'], notes)
            self.assertEqual(evidence['models'][0]['identifier'], 'example')
            with (root / 'out/model_datasets.csv').open() as stream:
                datasets = list(csv.DictReader(stream))
            self.assertEqual([row['role'] for row in datasets], ['pretraining', 'fine_tuning'])
            self.assertTrue(all('all stages' not in row['description'] for row in datasets))

    def test_colors_and_unannotated_values_use_shared_vocabulary(self):
        path = Path(__file__).resolve().parents[2] / 'scripts/build_model_metadata_catalog.py'
        spec = importlib.util.spec_from_file_location('metadata_converter', path)
        converter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(converter)
        self.assertEqual(converter._classify_fill('FFFFE599'), 'probable')
        self.assertEqual(converter._classify_fill('FFFF0000'), 'uncertain')
        self.assertEqual(converter._classify_fill('FFF6F8F9'), 'undocumented')
        self.assertIsNone(converter._classify_fill('FFFFFFFF'))
        self.assertEqual(converter.assertion_status('supervised', 'supervision'), 'probable')
        self.assertEqual(converter.assertion_status('', 'supervision', 'verified'), 'undocumented')
        self.assertEqual(converter.assertion_status('supervised', 'supervision', 'verified'), 'verified')
        self.assertEqual(converter.assertion_status('61100840', 'parameter_count', 'undocumented'),
                         'undocumented')


@skipIf(settings.TEST_RUNNER.endswith('ExistingDatabaseTestRunner'),
        'Run metadata database tests with web.metadata_test_settings on disposable PostgreSQL')
class PublicLineageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.db import connection
        from django.utils import timezone
        from benchmarks.models import BenchmarkInstance, BenchmarkType, Model, Score, User
        owner = User.objects.create(email='metadata-test@example.invalid')
        kind = BenchmarkType.objects.create(identifier='average_vision', owner=owner, visible=True)
        leaf = BenchmarkType.objects.create(identifier='metadata-test-leaf', owner=owner,
                                            visible=True, parent=kind)
        benchmark = BenchmarkInstance.objects.create(benchmark_type=leaf, version=0)
        cls.site_models = {}
        for name, public in [('External-Base', True), ('private-sibling', False), ('child', True)]:
            model = Model.objects.create(name=name, owner=owner, public=public)
            cls.site_models[name] = model
            Score.objects.create(model=model, benchmark=benchmark, score_ceiled=0.5,
                                 start_timestamp=timezone.now())
        for name in ('child', 'private-sibling'):
            record = ModelMetadataRecord.objects.create(domain='vision', identifier=name)
            ModelMetadataRelationship.objects.create(record=record, ordinal=0,
                base_identifier='external-base', base_name='External base', relationship='variant_of')
        with connection.cursor() as cursor:
            cursor.execute('SELECT refresh_all_materialized_views()')

    def test_public_external_base_resolves_but_private_sibling_does_not_link(self):
        card = build_model_card_metadata(self.site_models['child'])
        self.assertEqual(card['lineage']['ancestors'][0]['model_card_id'],
                         self.site_models['External-Base'].pk)
        self.assertIsNone(card['lineage']['related_models'][0]['model_card_id'])

    def test_private_page_does_not_render_curated_metadata_for_anonymous_users(self):
        response = self.client.get(f'/model/vision/{self.site_models["private-sibling"].pk}')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-model-metadata')
        self.assertNotContains(response, 'data-model-lineage')

    def test_public_check_reports_unmatched_identifiers_without_writes(self):
        output = StringIO()
        call_command('import_model_metadata', DATA, dry_run=True, check_public=True, stdout=output)
        self.assertIn('No public model page:', output.getvalue())
        self.assertEqual(ModelMetadataRecord.objects.count(), 2)


class MetadataEvidenceDisplayTests(SimpleTestCase):
    def test_input_uncertainty_survives_interface_evidence_in_either_order(self):
        from brainscore_core.metadata.storage import to_tables

        document = {
            'schema_version': '2.0', 'domain': 'vision',
            'models': {'example': {
                'io': {'interface': 'Classifier', 'input_format': 'Resolution disputed',
                       'output_format': 'Class logits'},
                'sources': {
                    'loader': {'kind': 'other', 'citation': 'Loader code'},
                    'processor': {'kind': 'huggingface', 'citation': 'Processor config'},
                },
                'assertions': [
                    {'path': '/io/interface', 'status': 'probable', 'sources': ['loader']},
                    {'path': '/io/input_format', 'status': 'uncertain',
                     'sources': ['processor']},
                    {'path': '/io/output_format', 'status': 'probable',
                     'sources': ['loader']},
                ],
            }},
        }
        tables = to_tables(document)
        tables = {name: [{key: '' if value is None else str(value)
                          for key, value in row.items()} for row in rows]
                  for name, rows in tables.items()}
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                tables['assertions'] = sorted(tables['assertions'],
                                              key=lambda row: row['path'], reverse=reverse)
                card = repository._build_catalog(tables)[('vision', 'example')]
                card = repository.finalize_card_context(card, 'database')
                badges = card['field_badges']
                self.assertEqual(badges['eval_input_format']['status'], 'uncertain')
                self.assertIn('Processor config', badges['eval_input_format']['source'])
                self.assertEqual(badges['eval_output_format']['status'], 'probable')
                self.assertNotIn('Processor config', badges['eval_output_format']['source'])


class LicenseLabelTests(SimpleTestCase):
    def test_aliases_and_applicable_license_are_selected(self):
        from benchmarks.model_metadata.licenses import license_labels
        cases = [
            ('Apache 2.0', ['Apache-2.0']),
            ('GNU GPL v3+', ['GPL-3.0-or-later']),
            ('CC-BY-NC 4.0', ['CC-BY-NC-4.0']),
            ('BSD-3-Clause (torchvision). Historical code is BSD-2-Clause.', ['BSD-3-Clause']),
            ('Apache-2.0 (HF tag); LAION-2B metadata CC-BY 4.0', ['Apache-2.0']),
            ('Apache-2.0 (checkpoint); original code MIT-licensed', ['Apache-2.0']),
            ('Submission code: MIT; timm weights: Apache 2.0', ['MIT', 'Apache-2.0']),
            ('Submission code: MIT; timm weights: MIT (per HF model card)', ['MIT']),
            ('Same as ReAlnet04', [None]),
            ('BSD-3-Clause-Clear', [None]),
            ('', []),
        ]
        for text, identifiers in cases:
            with self.subTest(text=text):
                self.assertEqual([item['identifier'] for item in license_labels(text)], identifiers)

    def test_code_license_does_not_claim_unknown_weights_are_licensed(self):
        from benchmarks.model_metadata.licenses import license_labels
        labels = license_labels('Submission code: MIT; underlying weights license unconfirmed')
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]['scope'], 'Code license')
        self.assertFalse(labels[0]['uncertain'])
        self.assertTrue(license_labels('Submission code: MIT (assumed)')[0]['uncertain'])
