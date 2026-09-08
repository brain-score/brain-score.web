import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from benchmarks.models import (
    ModelMetadataAssertion,
    ModelMetadataContributor,
    ModelMetadataDataset,
    ModelMetadataIntendedUse,
    ModelMetadataRecord,
    ModelMetadataRelationship,
)

CSV_FILES = (
    'models.csv', 'model_datasets.csv', 'intended_use.csv',
    'contributors.csv', 'model_relationships.csv', 'assertions.csv',
)


def _optional_int(value):
    return int(value) if value else None


def _optional_float(value):
    return float(value) if value else None


def _optional_bool(value):
    if not value:
        return None
    if value not in {'true', 'false'}:
        raise CommandError(f"Invalid boolean value: {value!r}")
    return value == 'true'


def _optional_str(value):
    return value if value else None


class Command(BaseCommand):
    help = (
        "Load the six-table model-metadata catalog CSVs "
        "(built by scripts/build_model_metadata_catalog.py, see PR #539) "
        "into the database. Replaces any existing records for the "
        "(domain, identifier) pairs present in models.csv."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'data_dir', nargs='?', default='benchmarks/model_metadata/data',
            help="Directory containing the six catalog CSV files "
                 "(default: benchmarks/model_metadata/data)")
        parser.add_argument(
            '--wipe', action='store_true',
            help="Delete all existing metadata records before importing")

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        missing = [name for name in CSV_FILES if not (data_dir / name).exists()]
        if missing:
            raise CommandError(f"Missing catalog files in {data_dir}: {', '.join(missing)}")

        rows = {name: self._read_csv(data_dir / name) for name in CSV_FILES}

        model_keys = [(row['domain'], row['identifier']) for row in rows['models.csv']]
        if len(set(model_keys)) != len(model_keys):
            raise CommandError("Duplicate (domain, identifier) rows in models.csv")
        key_set = set(model_keys)
        for name in CSV_FILES[1:]:
            orphans = {(row['domain'], row['identifier']) for row in rows[name]} - key_set
            if orphans:
                raise CommandError(f"{name} references models missing from models.csv: {sorted(orphans)[:5]}")

        with transaction.atomic():
            if options['wipe']:
                deleted, _ = ModelMetadataRecord.objects.all().delete()
                self.stdout.write(f"Wiped {deleted} existing rows")
            else:
                # child rows cascade with their record
                replaced = Q()
                for domain, identifier in key_set:
                    replaced |= Q(domain=domain, identifier=identifier)
                ModelMetadataRecord.objects.filter(replaced).delete()

            records = {}
            for row in rows['models.csv']:
                records[(row['domain'], row['identifier'])] = ModelMetadataRecord.objects.create(
                    domain=row['domain'],
                    identifier=row['identifier'],
                    display_name=_optional_str(row['display_name']),
                    version=_optional_str(row['version']),
                    architecture_family=_optional_str(row['architecture_family']),
                    architecture_description=_optional_str(row['architecture_description']),
                    parameter_count=_optional_int(row['parameter_count']),
                    parameter_count_exact=_optional_bool(row['parameter_count_exact']),
                    trainable_layers=_optional_str(row['trainable_layers']),
                    recurrent=_optional_bool(row['recurrent']),
                    input_modality=_optional_str(row['input_modality']),
                    input_channels=_optional_int(row['input_channels']),
                    input_height=_optional_int(row['input_height']),
                    input_width=_optional_int(row['input_width']),
                    visual_degrees=_optional_float(row['visual_degrees']),
                    visual_degrees_description=_optional_str(row['visual_degrees_description']),
                    supervision_type=_optional_str(row['supervision_type']),
                    supervision_description=_optional_str(row['supervision_description']),
                    interface_description=_optional_str(row['interface_description']),
                    preprocessing_description=_optional_str(row['preprocessing_description']),
                    training_process=_optional_str(row['training_process']),
                    dataset_summary=_optional_str(row['dataset_summary']),
                    weights_provider=_optional_str(row['weights_provider']),
                    checkpoint_identifier=_optional_str(row['checkpoint_identifier']),
                    source_url=_optional_str(row['source_url']),
                    license=_optional_str(row['license']),
                    curation_confidence=_optional_str(row['curation_confidence']),
                )

            ModelMetadataDataset.objects.bulk_create(
                ModelMetadataDataset(
                    record=records[(row['domain'], row['identifier'])],
                    ordinal=int(row['ordinal']),
                    dataset_identifier=_optional_str(row['dataset_identifier']),
                    dataset_name=row['dataset_name'],
                    role=row['role'],
                    description=_optional_str(row['description']),
                ) for row in rows['model_datasets.csv'])

            ModelMetadataIntendedUse.objects.bulk_create(
                ModelMetadataIntendedUse(
                    record=records[(row['domain'], row['identifier'])],
                    category=row['category'],
                    ordinal=int(row['ordinal']),
                    value=row['value'],
                ) for row in rows['intended_use.csv'])

            ModelMetadataContributor.objects.bulk_create(
                ModelMetadataContributor(
                    record=records[(row['domain'], row['identifier'])],
                    kind=row['kind'],
                    ordinal=int(row['ordinal']),
                    name=row['name'],
                ) for row in rows['contributors.csv'])

            ModelMetadataRelationship.objects.bulk_create(
                ModelMetadataRelationship(
                    record=records[(row['domain'], row['identifier'])],
                    ordinal=int(row['ordinal']),
                    base_identifier=_optional_str(row['base_identifier']),
                    base_name=row['base_name'],
                    relationship=row['relationship'],
                ) for row in rows['model_relationships.csv'])

            ModelMetadataAssertion.objects.bulk_create(
                ModelMetadataAssertion(
                    record=records[(row['domain'], row['identifier'])],
                    path=row['path'],
                    status=row['status'],
                    source=_optional_str(row['source']),
                ) for row in rows['assertions.csv'])

        self.stdout.write(self.style.SUCCESS(
            f"Imported {len(records)} models "
            f"({len(rows['model_datasets.csv'])} datasets, "
            f"{len(rows['intended_use.csv'])} intended-use rows, "
            f"{len(rows['contributors.csv'])} contributors, "
            f"{len(rows['model_relationships.csv'])} relationships, "
            f"{len(rows['assertions.csv'])} assertions)"))

    @staticmethod
    def _read_csv(path):
        with path.open(newline='', encoding='utf-8') as stream:
            return list(csv.DictReader(stream))
