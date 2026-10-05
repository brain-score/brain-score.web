"""Export unpublished database records as reviewable metadata.yaml proposals."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from benchmarks.model_metadata.bootstrap_export import export_bootstrap


class Command(BaseCommand):
    help = 'Export unpublished metadata from an explicitly named, read-only PostgreSQL snapshot.'

    def add_arguments(self, parser):
        parser.add_argument('--domain', required=True, choices=['vision', 'language'])
        parser.add_argument('--checkout', required=True, type=Path)
        parser.add_argument('--output', required=True, type=Path)
        parser.add_argument('--expected-database', required=True)

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Bootstrap export requires PostgreSQL.')
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                cursor.execute('SELECT current_database()')
                if cursor.fetchone()[0] != options['expected_database']:
                    raise CommandError('Export database does not match the configured target.')
            try:
                report = export_bootstrap(options['domain'], options['checkout'], options['output'])
            except (ValueError, OSError) as exc:
                raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps(report, sort_keys=True))
        if report['blocked']:
            raise CommandError('Some bootstrap models require identity or metadata review; inspect the report.')
