"""Atomic persistence shared by reviewed imports and repository publication."""

from django.db import connection, transaction
from .catalog import TABLES, model_key
from benchmarks.models import ModelMetadataRecord


def lock_metadata_publication():
    """Serialize CSV bootstrap checks with repository publication."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [67256020])


@transaction.atomic
def write_tables(tables, wipe=False):
    if not tables["models"]:
        raise ValueError("Refusing to write an empty metadata catalog")
    if wipe:
        ModelMetadataRecord.objects.all().delete()
    records = {}
    for row in tables["models"]:
        values = dict(row)
        domain, identifier = values.pop("domain"), values.pop("identifier")
        record = (
            ModelMetadataRecord.objects.select_for_update()
            .filter(domain__iexact=domain, identifier__iexact=identifier)
            .first()
        )
        if record is None:
            record = ModelMetadataRecord(domain=domain, identifier=identifier)
        record.domain, record.identifier = domain, identifier
        for field, value in values.items():
            setattr(record, field, value)
        record.save()
        records[model_key(domain, identifier)] = record
    for name, (model, _) in TABLES.items():
        if name == "models":
            continue
        model.objects.filter(record__in=records.values()).delete()
        children = []
        for row in tables[name]:
            values = dict(row)
            key = model_key(values.pop("domain"), values.pop("identifier"))
            children.append(model(record=records[key], **values))
        model.objects.bulk_create(children)
