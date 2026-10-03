"""Read approved bootstrap values for proposals without writing metadata."""

import hashlib
import json
from copy import deepcopy


def document_revision(document):
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def read_bootstrap_entries(domain, identifiers):
    from django.db.models.functions import Lower
    from django.db.models import Prefetch
    from brainscore_core.metadata.storage import from_tables
    from benchmarks.models import ModelMetadataRecord, ModelMetadataPublication
    from .catalog import TABLES, scalar_fields

    names = {name.lower() for name in identifiers}
    published = set(ModelMetadataPublication.objects.filter(
        domain__iexact=domain
    ).annotate(metadata_name=Lower("identifier")).filter(
        metadata_name__in=names
    ).values_list("metadata_name", flat=True))
    relations = {
        "model_datasets": "datasets", "intended_use": "intended_use",
        "contributors": "contributors", "model_relationships": "relationships",
        "assertions": "assertions",
    }
    records = ModelMetadataRecord.objects.filter(domain__iexact=domain).annotate(
        metadata_name=Lower("identifier")
    ).filter(metadata_name__in=names - published).prefetch_related(*[
        Prefetch(relation, queryset=TABLES[name][0].objects.order_by(*TABLES[name][1]))
        for name, relation in relations.items()
    ])
    tables = {name: [] for name in TABLES}
    for record in records:
        tables["models"].append(dict({
            field.name: getattr(record, field.name)
            for field in scalar_fields(ModelMetadataRecord)
        }, domain=domain))
        for name, relation in relations.items():
            for child in getattr(record, relation).all():
                tables[name].append(dict(
                    {field.name: getattr(child, field.name)
                     for field in scalar_fields(type(child))},
                    domain=domain, identifier=record.identifier,
                ))
    # Flat bootstrap evidence does not establish a paper or Hugging Face source
    # kind. The converter preserves its status and marks its source unreviewed.
    if not tables["models"]:
        return {}
    return {name.lower(): entry for name, entry in
            from_tables(tables, domain)["models"].items()}


def proposal_baseline(document, content):
    """Enrich legacy siblings; an existing v2 repository file stays authoritative."""
    from brainscore_core.metadata import validate
    from brainscore_core.metadata.contract import FIELD_SPECS, LIST_PATHS, get_path, put_path, read_yaml
    from brainscore_core.metadata.policy import evidence, is_verified

    if content and read_yaml(content).get("schema_version") == "2.0":
        return document
    entries = read_bootstrap_entries(document["domain"], document["models"])
    result = deepcopy(document)
    for identifier, legacy in document["models"].items():
        if identifier.lower() not in entries:
            continue
        entry = deepcopy(entries[identifier.lower()])
        if "legacy" in legacy:
            entry["legacy"] = deepcopy(legacy["legacy"])
        entry["sources"].update(deepcopy(legacy.get("sources", {})))
        for path in (*FIELD_SPECS, *LIST_PATHS):
            value = get_path(legacy, path)
            if (get_path(entry, path) not in (None, "", [])
                    or value in (None, "", []) or is_verified(entry, path)):
                continue
            put_path(entry, path, deepcopy(value))
            for assertion in evidence(legacy, path)[0]:
                entry["assertions"] = [a for a in entry["assertions"]
                                       if a["path"] != assertion["path"]]
                entry["assertions"].append(deepcopy(assertion))
        result["models"][identifier] = entry
    return validate(result, document["domain"])


def require_complete_bootstrap(document):
    """A first publication must not erase populated bootstrap fields."""
    from brainscore_core.metadata.contract import FIELD_SPECS, LIST_PATHS, get_path
    from .github import ProposalError

    entries = read_bootstrap_entries(document["domain"], document["models"])
    for identifier, proposed in document["models"].items():
        approved = entries.get(identifier.lower(), {})
        missing = [path for path in (*FIELD_SPECS, *LIST_PATHS)
                   if get_path(approved, path) not in (None, "", [])
                   and get_path(proposed, path) in (None, "", [])]
        if missing:
            raise ProposalError(
                f"Initial publication omits existing metadata for {identifier}: "
                + ", ".join(missing)
                + ". Include the complete bootstrap metadata before publication."
            )
