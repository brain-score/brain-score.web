from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from benchmarks.model_metadata.catalog import TABLES, model_key, read_catalog
from benchmarks.models import ModelMetadataRecord, FinalModelContext


class Command(BaseCommand):
    help = 'Validate and import model metadata; preserve models outside the supplied catalog.'

    def add_arguments(self, parser):
        parser.add_argument('data_dir', nargs='?', default=str(
            Path(__file__).resolve().parents[2] / 'model_metadata' / 'data'))
        parser.add_argument('--dry-run', action='store_true', help='Validate and report without writing')
        parser.add_argument('--check-public', action='store_true',
                            help='Report catalog identifiers without a public model page')
        parser.add_argument('--wipe', action='store_true', help='Replace all metadata with this nonempty catalog')

    def handle(self, *args, **options):
        tables = read_catalog(options['data_dir'])
        summary = ', '.join(f'{len(rows)} {name}' for name, rows in tables.items())
        if options['check_public']:
            public_keys = {model_key(domain, name) for domain, name in
                           FinalModelContext.objects.filter(public=True).values_list('domain', 'name')}
            unmatched = [f"{row['domain']}/{row['identifier']}" for row in tables['models']
                         if model_key(row['domain'], row['identifier']) not in public_keys]
            self.stdout.write(f'Public model matches: {len(tables["models"]) - len(unmatched)} '
                              f'of {len(tables["models"])}')
            for identifier in unmatched:
                self.stdout.write(self.style.WARNING(f'No public model page: {identifier}'))
        if options['dry_run']:
            existing = {model_key(domain, name) for domain, name in
                        ModelMetadataRecord.objects.values_list('domain', 'identifier')}
            keys = {model_key(row['domain'], row['identifier']) for row in tables['models']}
            self.stdout.write(self.style.SUCCESS(f'Validated {summary}; no changes made'))
            if not options['wipe']:
                self.stdout.write(f'{len(keys - existing)} new, {len(keys & existing)} updated, '
                                  f'{len(existing - keys)} preserved model records')
            if options['wipe']:
                self.stdout.write('Import would replace all existing metadata.')
            else:
                self.stdout.write('Import would update these model keys and preserve all other models.')
            return
        try:
            with transaction.atomic():
                if options['wipe']:
                    ModelMetadataRecord.objects.all().delete()
                records = {}
                for row in tables['models']:
                    values = dict(row)
                    domain, identifier = values.pop('domain'), values.pop('identifier')
                    record = ModelMetadataRecord.objects.select_for_update().filter(
                        domain__iexact=domain, identifier__iexact=identifier).first()
                    if record is None:
                        record = ModelMetadataRecord(domain=domain, identifier=identifier)
                    record.domain, record.identifier = domain, identifier
                    for field, value in values.items():
                        setattr(record, field, value)
                    record.save()
                    records[model_key(domain, identifier)] = record
                for name, (model, _) in TABLES.items():
                    if name == 'models':
                        continue
                    model.objects.filter(record__in=records.values()).delete()
                    children = []
                    for row in tables[name]:
                        values = dict(row)
                        key = model_key(values.pop('domain'), values.pop('identifier'))
                        children.append(model(record=records[key], **values))
                    model.objects.bulk_create(children)
        except IntegrityError as exc:
            raise CommandError(f'Import rolled back because of a database constraint: {exc}') from exc
        self.stdout.write(self.style.SUCCESS(f'Imported {summary}'))
