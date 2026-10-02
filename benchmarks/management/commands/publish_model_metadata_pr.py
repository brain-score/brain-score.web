import os
from django.core.management.base import BaseCommand, CommandError
from benchmarks.model_metadata.github import GitHub, ProposalError


class Command(BaseCommand):
    help = "Publish validated model metadata authorized by a merged domain-repository PR."

    def add_arguments(self, parser):
        parser.add_argument("--domain", required=True)
        parser.add_argument("--pr", type=int, required=True)

    def handle(self, *args, **options):
        from brainscore_core.metadata import MetadataError
        from benchmarks.model_metadata.publishing import publish_pull_request

        token = os.environ.get("METADATA_PUBLISH_GITHUB_TOKEN")
        if not token:
            raise CommandError(
                "METADATA_PUBLISH_GITHUB_TOKEN is required for trusted publication."
            )
        try:
            results = publish_pull_request(
                options["domain"], options["pr"], GitHub(token, read_only=True)
            )
        except (ProposalError, MetadataError) as exc:
            raise CommandError(str(exc)) from exc
        if any(result["status"] in {"published", "unchanged"} for result in results):
            # Retry also refreshes contexts if a previous run published successfully
            # but failed during refresh or cache invalidation.
            from django.db import connection
            from benchmarks.utils import invalidate_domain_cache

            with connection.cursor() as cursor:
                cursor.execute("REFRESH MATERIALIZED VIEW mv_final_model_context")
            invalidate_domain_cache(options["domain"])
        for result in results:
            self.stdout.write(f"{result['path']}: {result['status']}")
