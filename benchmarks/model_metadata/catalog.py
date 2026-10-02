"""Validated import format shared by the metadata command and parity tests."""
import csv
import math
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import CommandError
from django.db import models

from benchmarks.models import (
    ModelMetadataAssertion, ModelMetadataContributor, ModelMetadataDataset,
    ModelMetadataIntendedUse, ModelMetadataRecord, ModelMetadataRelationship,
)

TABLES = {
    'models': (ModelMetadataRecord, ()),
    'model_datasets': (ModelMetadataDataset, ('ordinal',)),
    'intended_use': (ModelMetadataIntendedUse, ('category', 'ordinal')),
    'contributors': (ModelMetadataContributor, ('kind', 'ordinal')),
    'model_relationships': (ModelMetadataRelationship, ('ordinal',)),
    'assertions': (ModelMetadataAssertion, ('path',)),
}
ALLOWED = {
    ('model_datasets', 'role'): {'training', 'pretraining', 'fine_tuning', 'test', 'validation'},
    ('intended_use', 'category'): {'applications', 'users', 'limitations', 'biases'},
    ('contributors', 'kind'): {'creators', 'organizations'},
    ('model_relationships', 'relationship'): {'variant_of', 'fine_tuned_from', 'derived_from'},
    ('assertions', 'status'): {'verified', 'probable', 'uncertain', 'undocumented'},
}


def model_key(domain, identifier):
    """Ignore casing, but retain punctuation and checkpoint suffixes."""
    return domain.lower(), identifier.lower()


def scalar_fields(model):
    return [field for field in model._meta.fields if field.name not in ('id', 'record')]


def read_catalog(directory):
    """Validate the entire catalog before any database changes are possible."""
    tables = {}
    for name, (model, unique_fields) in TABLES.items():
        path = Path(directory) / f'{name}.csv'
        fields = {field.name: field for field in scalar_fields(model)}
        expected = set(fields) | {'domain', 'identifier'}
        seen = set()
        rows = []
        try:
            with path.open(newline='', encoding='utf-8-sig') as stream:
                reader = csv.DictReader(stream)
                headers = reader.fieldnames or []
                if set(headers) != expected or len(headers) != len(expected):
                    raise CommandError(
                        f'{path.name}: invalid headers; missing {sorted(expected - set(headers))}, '
                        f'unexpected {sorted(set(headers) - expected)} (duplicate headers are invalid)')
                for line, raw in enumerate(reader, 2):
                    try:
                        if None in raw or any(value is None for value in raw.values()):
                            raise ValueError('wrong number of columns')
                        row = dict(raw)
                        row['domain'] = row['domain'].strip()
                        row['identifier'] = row['identifier'].strip()
                        if not row['domain'] or not row['identifier']:
                            raise ValueError('domain and identifier must not be empty')
                        row['domain'] = row['domain'].lower()
                        for key, field in fields.items():
                            value = row[key]
                            if not value:
                                if not field.null:
                                    raise ValueError(f'{key} must not be empty')
                                row[key] = None
                                continue
                            if isinstance(field, models.BooleanField):
                                if value not in ('true', 'false'):
                                    raise ValueError(f'{key} must be true or false')
                                value = value == 'true'
                            value = field.to_python(value)
                            field.run_validators(value)
                            if isinstance(value, float) and not math.isfinite(value):
                                raise ValueError(f'{key} must be finite')
                            if isinstance(value, (int, float)) and value < 0:
                                raise ValueError(f'{key} must not be negative')
                            allowed = ALLOWED.get((name, key))
                            if allowed and value not in allowed:
                                raise ValueError(f'unknown {key}: {value!r}')
                            row[key] = value
                        key = model_key(row['domain'], row['identifier'])
                        unique = key + tuple(row[field] for field in unique_fields)
                        if unique in seen:
                            raise ValueError(f'duplicate key {unique!r}')
                        seen.add(unique)
                        rows.append(row)
                    except (ValueError, TypeError, ValidationError) as exc:
                        raise CommandError(f'{path.name}:{line}: {exc}') from exc
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f'Cannot read {path}: {exc}') from exc
        tables[name] = rows
    if not tables['models']:
        raise CommandError('models.csv is empty; refusing to modify metadata, including with --wipe')
    keys = {model_key(row['domain'], row['identifier']) for row in tables['models']}
    for name, rows in tables.items():
        orphans = {model_key(row['domain'], row['identifier']) for row in rows} - keys
        if orphans:
            raise CommandError(f'{name}.csv references models missing from models.csv: {sorted(orphans)[:5]}')
    return tables
