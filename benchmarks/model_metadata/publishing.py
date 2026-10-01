"""Trusted publication entry point. Never called by the editor or preview."""

import hashlib
from django.db import connection, transaction
from .github import ProposalError, target, allowed_path
from .writer import write_tables, lock_metadata_publication
from benchmarks.models import (
    ModelMetadataPublication,
    ModelMetadataRevision,
    Model,
    ModelMeta,
)


@transaction.atomic
def publish_pull_request(domain, number, github):
    from brainscore_metadata import load, protected_changes
    from brainscore_metadata.storage import to_tables, legacy_projection

    config = target(domain)
    repo = config["repository"]
    pr = github.request("GET", f"/repos/{repo}/pulls/{number}")
    if (
        not pr.get("merged")
        or pr["base"]["ref"] != config["branch"]
        or pr["base"]["repo"]["full_name"] != repo
    ):
        raise ProposalError(
            "Only a merged PR targeting the configured repository branch can publish metadata."
        )
    files = github.pages(f"/repos/{repo}/pulls/{number}/files")
    candidates = [
        item
        for item in files
        if allowed_path(config, item["filename"])
        or allowed_path(config, item.get("previous_filename", ""))
    ]
    if any(item["status"] in {"removed", "renamed"} for item in candidates):
        raise ProposalError(
            "Metadata file removal/rename requires a separate reviewed migration."
        )
    lock_metadata_publication()
    result = []
    for item in candidates:
        path = item["filename"]
        content, merged_blob = github.file(repo, path, pr["merge_commit_sha"])
        # Legacy files continue through their existing adapter until converted.
        from brainscore_metadata.contract import read_yaml

        header = read_yaml(content)
        old_header = {}
        if item["status"] != "added":
            old_content, _ = github.file(repo, path, pr["base"]["sha"])
            old_header = read_yaml(old_content)
        was_v2 = (
            isinstance(old_header, dict) and old_header.get("schema_version") == "2.0"
        )
        if not isinstance(header, dict) or header.get("schema_version") != "2.0":
            if (
                was_v2
                or ModelMetadataPublication.objects.filter(
                    repository=repo, path=path
                ).exists()
            ):
                raise ProposalError(
                    "Published metadata cannot be downgraded to a legacy schema."
                )
            continue
        document = load(content, domain)
        _, reviewed_blob = github.file(repo, path, pr["head"]["sha"])
        if reviewed_blob != merged_blob:
            raise ProposalError(
                "Merged metadata differs from the reviewed PR revision. A new reviewed PR is required."
            )
        if was_v2 and set(load(old_content, domain)["models"]) != set(
            document["models"]
        ):
            raise ProposalError(
                "Model additions/removals require a separate registration migration."
            )
        approved_by = github.approved_reviewer(repo, pr)
        if not approved_by:
            raise ProposalError(
                "Publication requires maintainer approval on the current PR revision."
            )
        reviewer = None
        with transaction.atomic():
            if connection.vendor != "postgresql":
                raise ProposalError(
                    "Publication requires PostgreSQL transaction locks."
                )
            lock = int.from_bytes(
                hashlib.sha256(f"{repo}:{path}".encode()).digest()[:8],
                "big",
                signed=True,
            )
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock])
            _, current_blob = github.file(repo, path, config["branch"])
            if current_blob != merged_blob:
                result.append({"path": path, "status": "superseded"})
                continue
            existing = list(
                ModelMetadataPublication.objects.select_for_update().filter(
                    repository=repo, path=path
                )
            )
            if (
                existing
                and len(existing) == len(document["models"])
                and all(record.blob_sha == merged_blob for record in existing)
            ):
                result.append({"path": path, "status": "unchanged"})
                continue
            if existing and {record.identifier for record in existing} != set(
                document["models"]
            ):
                raise ProposalError(
                    "Adding or removing models in a published file requires a separate reviewed migration."
                )
            previous_documents = {
                record.identifier: record.document for record in existing
            }
            for identifier, entry in document["models"].items():
                if not Model.objects.filter(
                    domain__iexact=domain, name__iexact=identifier
                ).exists():
                    raise ProposalError(
                        "Metadata must identify a registered model in the same domain."
                    )
                publication = (
                    ModelMetadataPublication.objects.select_for_update()
                    .filter(domain__iexact=domain, identifier__iexact=identifier)
                    .first()
                )
                if publication and (
                    publication.repository != repo or publication.path != path
                ):
                    raise ProposalError(
                        "Model is already bound to a different repository file."
                    )
                if publication and publication.blob_sha == merged_blob:
                    continue
                bootstrap = publication is None
                blocked = (
                    protected_changes(publication.document, entry)
                    if publication
                    else []
                )
                if blocked or bootstrap:
                    if reviewer is None:
                        reviewer = github.override_reviewer(repo, pr)
                    if not reviewer:
                        raise ProposalError(
                            "Protected changes or first publication require metadata-source-override and independent maintainer approval on the latest PR commit."
                        )
            # Validate the complete file and policy before any canonical writes.
            write_tables(to_tables(document))
            for identifier, entry in document["models"].items():
                previous = previous_documents.get(identifier)
                values = legacy_projection(entry, previous)
                if "huggingface_link" in values:
                    values["hugging_face_link"] = values.pop("huggingface_link")
                for model in Model.objects.filter(
                    domain__iexact=domain, name__iexact=identifier
                ):
                    meta = ModelMeta.objects.filter(model=model).first()
                    # Bootstrap adds descriptive metadata without changing the
                    # existing fields used by leaderboard contexts and filters.
                    if previous is None and meta is not None:
                        continue
                    meta = meta or ModelMeta(model=model)
                    for key, value in values.items():
                        setattr(meta, key, value)
                    for key, value in values.items():
                        field = ModelMeta._meta.get_field(key)
                        if value is not None:
                            field.run_validators(field.to_python(value))
                    meta.save()

            for identifier, entry in document["models"].items():
                publication = ModelMetadataPublication.objects.filter(
                    domain__iexact=domain, identifier__iexact=identifier
                ).first()
                if publication is None:
                    publication = ModelMetadataPublication(
                        domain=domain, identifier=identifier
                    )
                publication.repository, publication.path = repo, path
                publication.commit_sha, publication.blob_sha = (
                    pr["merge_commit_sha"],
                    merged_blob,
                )
                publication.pull_request, publication.document = number, entry
                publication.save()
                ModelMetadataRevision.objects.get_or_create(
                    publication=publication,
                    commit_sha=pr["merge_commit_sha"],
                    defaults={
                        "pull_request": number,
                        "document": entry,
                        "override_reviewer": reviewer or "",
                        "reviewer": reviewer or approved_by,
                    },
                )
            result.append(
                {"path": path, "status": "published", "models": len(document["models"])}
            )
    return result
