"""Run merged-PR synchronization inside the deployed website environment."""
import json
import os
from datetime import datetime, timezone
from io import StringIO

from django.conf import settings
from django.core.cache import caches
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from benchmarks.model_metadata.github import GitHub, ProposalError, domains
from benchmarks.model_metadata.monitoring import report_run
from benchmarks.model_metadata.synchronization import DryRunState, RedisState, sync_domain, timestamp

LOCK_ID = 67256021


class Command(BaseCommand):
    help = "Synchronize merged metadata PRs using the deployed database, App and shared cache."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--since", help="Explicit UTC start for a read-only dry run")

    def handle(self, *args, **options):
        if not options["dry_run"] and not getattr(settings, "MODEL_METADATA_SYNC_ENABLED", False):
            self.stdout.write("Metadata synchronization disabled.")
            return
        if options["since"] and not options["dry_run"]:
            raise CommandError("Use --since only with --dry-run; activation sets the persistent start time.")
        monitor = not options["dry_run"]
        success = False
        try:
            start = timestamp(options["since"] or getattr(settings, "MODEL_METADATA_SYNC_START_AT", ""))
            now = datetime.now(timezone.utc)
            if start > now:
                raise ProposalError("Synchronization start time is in the future.")
            expected = getattr(settings, "MODEL_METADATA_SYNC_EXPECTED_DATABASE", "")
            if not expected or connection.vendor != "postgresql":
                raise ProposalError("Configure the expected PostgreSQL synchronization database.")
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                if cursor.fetchone()[0] != expected:
                    raise ProposalError("Synchronization database does not match the configured target.")
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SET statement_timeout = '120s'")
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [LOCK_ID])
                acquired = cursor.fetchone()[0]
            if not acquired:
                monitor = False
                self.stdout.write("Another metadata synchronization is running.")
                return
            try:
                # Direct Redis operations fail closed even if cache IGNORE_EXCEPTIONS is enabled.
                state = DryRunState() if options["dry_run"] else RedisState(caches["redis"])
                registry = domains()
                if not registry:
                    raise ProposalError("No metadata repositories are configured.")
                reports = []
                for domain, config in registry.items():
                    try:
                        with GitHub.reader(config) as github:
                            reports.append(sync_domain(domain, config, github, state, start, now,
                                                       self.publish, dry_run=options["dry_run"]))
                    except Exception as exc:
                        reports.append({"domain": domain, "errors": [{"error": type(exc).__name__}]})
                self.stdout.write(json.dumps(reports, sort_keys=True))
                if any(report["errors"] for report in reports):
                    raise CommandError("Metadata synchronization has failed PRs; cursors retained for retry.")
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", [LOCK_ID])
            success = True
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError("Metadata synchronization failed: " + type(exc).__name__) from None
        finally:
            if monitor:
                report_run(success)

    @staticmethod
    def publish(domain, number, github):
        previous = os.environ.get("METADATA_PUBLISH_GITHUB_TOKEN")
        os.environ["METADATA_PUBLISH_GITHUB_TOKEN"] = github.session.headers["Authorization"].split(" ", 1)[1]
        try:
            call_command("publish_model_metadata_pr", domain=domain, pr=number, stdout=StringIO())
        finally:
            if previous is None:
                os.environ.pop("METADATA_PUBLISH_GITHUB_TOKEN", None)
            else:
                os.environ["METADATA_PUBLISH_GITHUB_TOKEN"] = previous
