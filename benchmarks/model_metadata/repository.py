"""Database-backed model metadata and shared card formatting.

Lineage rules (implemented in ``_attach_lineage``):

* **Parent** — a model's single direct base, from its stored relationships
  (``base_identifier``/``base_name``). Ancestors are found by walking parent
  links upward until a model has no base, the base has no catalog record, or
  a cycle would form. A parent does not need its own catalog record: the
  relationship keeps a human-readable ``base_name`` either way, and shared
  synthetic identifiers (e.g. ``resnet-50``) still group families.
* **Siblings** — models that share this model's ``base_identifier`` (same
  parent). Shown under "Related variants".
* **Children** — models whose ``base_identifier`` is this model's identifier
  (this model *is* their parent). Also shown under "Related variants".
* A model is never its own relative; relationship labels (variant / fine-tuned
  / derived) always describe the related model's link to *its* base.
"""
from collections import Counter, defaultdict
from copy import deepcopy

from .licenses import license_labels

SCHEMA_VERSION = '2.0'
INITIAL_RELATED_MODELS = 3

RELATIONSHIP_LABELS = {
    'variant_of': 'Variant',
    'fine_tuned_from': 'Fine-tuned',
    'derived_from': 'Derived',
}
DATASET_ROLE_LABELS = {
    'training': 'Training',
    'pretraining': 'Pretrain',
    'fine_tuning': 'Finetune',
    'test': 'Test',
    'validation': 'Validation',
}
CARD_CONTENT_FIELDS = (
    'architecture_description', 'parameter_count_display', 'input_resolution_display',
    'recurrent_display', 'supervision_description', 'weights_provider',
    'trainable_layers_display', 'checkpoint', 'training_process', 'license',
)

# Assertion path -> template field slot(s). Slots are the keys templates
# look up in ``field_badges`` (prefixes eval_/intended_use_/contributors_ are
# resolved into the nested context dicts by ``_slot_value``). Paths without a
# card slot (/model/display_name, /lineage/base_models, /data/dataset_size)
# are intentionally absent.
ASSERTION_PATH_SLOTS = {
    '/model/version': ('eval_model_version',),
    '/model/architecture': ('architecture_description',),
    '/model/parameter_count': ('parameter_count_display',),
    '/model/trainable_layers': ('trainable_layers_display',),
    '/model/input_resolution': ('input_resolution_display',),
    '/model/recurrent': ('recurrent_display',),
    '/model/visual_degrees': ('visual_degrees',),
    '/model/supervision': ('supervision_description',),
    '/training/process': ('training_process',),
    '/training/objective': ('objective',),
    '/training/loss': ('loss',),
    '/training/learning_rate': ('learning_rate',),
    '/training/batch_size': ('batch_size',),
    '/training/preprocessing': ('preprocessing_description',),
    '/data/training_datasets': ('datasets',),
    '/eval/test_datasets': ('eval_test_datasets',),
    '/eval/validation_datasets': ('eval_validation_datasets',),
    '/io/interface': ('eval_input_format', 'eval_output_format'),
    '/io/input_format': ('eval_input_format',),
    '/io/output_format': ('eval_output_format',),
    '/io/tokenizer': ('eval_tokenizer',),
    '/provenance/weights_provider': ('weights_provider',),
    '/provenance/checkpoint': ('checkpoint',),
    '/legal/license': ('license',),
    '/people/creators': ('contributors_creators',),
    '/people/organizations': ('contributors_organizations',),
    '/use/applications': ('intended_use_applications',),
    '/use/users': ('intended_use_users',),
    '/use/limitations': ('intended_use_limitations',),
    '/use/biases': ('intended_use_biases',),
}
ALL_FIELD_SLOTS = sorted({slot for slots in ASSERTION_PATH_SLOTS.values() for slot in slots})


def _optional(value):
    return value if value else None


def _optional_bool(value):
    return {'true': True, 'false': False}.get(value)


def _format_count(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    for threshold, suffix in ((1_000_000_000, 'B'), (1_000_000, 'M'), (1_000, 'K')):
        if value >= threshold:
            return f'{value / threshold:.1f}'.rstrip('0').rstrip('.') + suffix
    return str(value)


def _model_key(row):
    return row['domain'].lower(), row['identifier'].lower()


def _trainable_layers_display(value):
    if not value:
        return None
    return f'{value} layers' if value.isdigit() else value


def _build_metadata(row):
    parameter_count_display = _format_count(_optional(row['parameter_count']))
    if parameter_count_display and _optional_bool(row['parameter_count_exact']) is False:
        parameter_count_display = f'≈{parameter_count_display}'
    height, width = _optional(row['input_height']), _optional(row['input_width'])
    recurrent = _optional_bool(row['recurrent'])
    return {
        'schema_version': SCHEMA_VERSION,
        'identifier': row['identifier'],
        'display_name': row['display_name'] or row['identifier'],
        'architecture_description': _optional(row['architecture_description']),
        'architecture_family': _optional(row['architecture_family']),
        'parameter_count_display': parameter_count_display,
        'input_resolution_display': f'{width} × {height}' if width and height else None,
        'recurrent_display': 'Yes' if recurrent else 'No' if recurrent is False else None,
        'supervision_description': _optional(row['supervision_description']),
        'supervision_type': _optional(row['supervision_type']),
        'weights_provider': _optional(row['weights_provider']),
        'weights_provider_url': None,
        'trainable_layers_display': _trainable_layers_display(_optional(row['trainable_layers'])),
        'checkpoint': _optional(row['checkpoint_identifier']),
        'training_process': _optional(row['training_process']),
        'objective': _optional(row.get('training_objective')),
        'loss': _optional(row.get('loss_function')),
        'learning_rate': _optional(row.get('learning_rate')),
        'batch_size': _optional(row.get('batch_size')),
        'preprocessing_description': _optional(row['preprocessing_description']),
        'visual_degrees': _optional(row['visual_degrees']),
        'visual_degrees_description': _optional(row['visual_degrees_description']),
        'datasets': [],
        'contributors': {},
        'license': _optional(row['license']),
        'license_nuance': None,
        'source_url': _optional(row['source_url']),
        'curation_confidence': _optional(row['curation_confidence']),
        'intended_use': {'applications': [], 'users': [], 'limitations': [], 'biases': []},
        'eval_io': {
            'test_datasets': None,
            'validation_datasets': None,
            'input_format': _optional(row.get('input_format')),
            'output_format': _optional(row.get('output_format')),
            'tokenizer': _optional(row.get('tokenizer')),
            'model_version': _optional(row['version']),
        },
        'extra_notes': None,
    }


def _attach_lineage(models, relationships, model_keys=None):
    children_by_base = defaultdict(list)
    for model_key, relationship in relationships.items():
        if relationship['base_identifier']:
            children_by_base[(model_key[0], relationship['base_identifier'].lower())].append(model_key)

    for model_key in models if model_keys is None else model_keys:
        model = models[model_key]
        domain, identifier = model_key

        # ancestors: walk parent links upward, guarding against cycles
        ancestors = []
        visited = {model_key}
        ancestor_key = model_key
        while ancestor_key in relationships:
            relationship = relationships[ancestor_key]
            base_identifier = relationship['base_identifier']
            base_key = (domain, base_identifier.lower()) if base_identifier else None
            if base_key in visited:
                break
            base_model = models.get(base_key) if base_key else None
            ancestors.append({
                'identifier': base_identifier,
                'display_name': relationship['base_name'],
                'has_metadata': base_model is not None,
            })
            if not base_model:
                break
            visited.add(base_key)
            ancestor_key = base_key
        ancestors.reverse()

        # related variants: children (I am their parent) + siblings (same parent)
        related_keys = set(children_by_base.get((domain, identifier), []))
        own_relationship = relationships.get(model_key)
        if own_relationship and own_relationship['base_identifier']:
            related_keys.update(children_by_base[(domain, own_relationship['base_identifier'].lower())])
        related_keys.discard(model_key)

        related = []
        for related_key in sorted(
                related_keys,
                key=lambda key: (models[key]['display_name'].casefold(), models[key]['identifier'])):
            related_model = models[related_key]
            relationship = relationships[related_key]
            related.append({
                'identifier': related_model['identifier'],
                'display_name': related_model['display_name'],
                'relationship': relationship['relationship'],
                'relationship_display': RELATIONSHIP_LABELS.get(
                    relationship['relationship'], 'Related'),
            })

        model['lineage'] = {
            'ancestors': ancestors,
            'current': {'identifier': model['identifier'], 'display_name': model['display_name']},
            'related_models': related,
            'hidden_related_count': max(0, len(related) - INITIAL_RELATED_MODELS),
            'has_relationships': bool(ancestors or related),
        }


def _build_catalog(tables):
    models = {}
    for row in tables['models']:
        key = _model_key(row)
        if key in models:
            raise ValueError(f'Duplicate model metadata record: {key}')
        models[key] = _build_metadata(row)

    for row in tables['model_datasets']:
        model = models.get(_model_key(row))
        if model is None:
            continue
        name = row['dataset_name'] or row['dataset_identifier']
        if row['role'] in ('test', 'validation'):
            field = 'test_datasets' if row['role'] == 'test' else 'validation_datasets'
            existing = model['eval_io'][field]
            model['eval_io'][field] = f'{existing}; {name}' if existing else name
        else:
            model['datasets'].append({
                'role': row['role'],
                'role_display': DATASET_ROLE_LABELS.get(row['role'], row['role'].title()),
                'dataset_name': name,
                'dataset_identifier': row['dataset_identifier'],
                'sample_count_display': _optional(row['description']),
            })

    for row in tables['intended_use']:
        model = models.get(_model_key(row))
        if model is not None and row['category'] in model['intended_use']:
            model['intended_use'][row['category']].append(row['value'])

    for row in tables['contributors']:
        model = models.get(_model_key(row))
        if model is not None:
            model['contributors'].setdefault(row['kind'], []).append(row['name'])

    relationships = {}
    for row in tables['model_relationships']:
        key = _model_key(row)
        if int(row['ordinal']) == 0:  # single direct parent drives lineage
            relationships[key] = row

    assertion_counts = defaultdict(Counter)
    badge_slots = defaultdict(dict)  # model key -> {slot: {'status', 'source'}}
    status_priority = {'verified': 0, 'probable': 1, 'uncertain': 2}
    for row in tables['assertions']:
        key = _model_key(row)
        assertion_counts[key][row['status']] += 1
        if row['status'] in ('verified', 'probable', 'uncertain'):
            source = row['source'] or 'curation workbook'
            if source == 'curation_workbook':
                source = 'curation workbook'
            for slot in ASSERTION_PATH_SLOTS.get(row['path'], ()):
                previous = badge_slots[key].get(slot)
                status = row['status']
                slot_source = source
                if previous:
                    status = max((previous['status'], status), key=status_priority.get)
                    slot_source = '; '.join(sorted(set((previous['source'], source))))
                badge_slots[key][slot] = {'status': status, 'source': slot_source}

    for key, model in models.items():
        counts = assertion_counts[key]
        model['verification'] = {
            'verified': counts['verified'],
            'probable': counts['probable'],
            'uncertain': counts['uncertain'],
            'undocumented': counts['undocumented'],
            'total': sum(counts.values()),
        }
        model['field_badges'] = badge_slots[key]
        model['assertions'] = sorted(
            (row for row in tables['assertions'] if _model_key(row) == key),
            key=lambda row: row['path'])
        model['has_card_content'] = any(model[field] for field in CARD_CONTENT_FIELDS) \
            or bool(model['datasets'] or model['contributors'])

    _attach_lineage(models, relationships)
    return models


def _database_row(record):
    """Serialize typed scalars into the formatter's CSV-compatible representation."""
    from .catalog import scalar_fields
    row = {}
    for field in scalar_fields(type(record)):
        value = getattr(record, field.name)
        if value is None:
            value = ''
        elif isinstance(value, bool):
            value = 'true' if value else 'false'
        elif isinstance(value, float):
            value = format(value, 'g')
        else:
            value = str(value)
        row[field.name] = value
    return row


def get_model_metadata(domain, identifier):
    """Read current database values; missing records use the submission fallback."""
    from benchmarks.models import ModelMetadataRecord, ModelMetadataRelationship

    if not identifier:
        return None
    record = ModelMetadataRecord.objects.filter(
        domain__iexact=domain, identifier__iexact=identifier).prefetch_related(
            'datasets', 'intended_use', 'contributors', 'relationships', 'assertions').first()
    if record is None:
        return None
    tables = {'models': [_database_row(record)]}
    for name, relation in (('model_datasets', 'datasets'), ('intended_use', 'intended_use'),
                           ('contributors', 'contributors'), ('model_relationships', 'relationships'),
                           ('assertions', 'assertions')):
        tables[name] = [dict(_database_row(child), domain=record.domain,
                            identifier=record.identifier) for child in getattr(record, relation).all()]
    key = _model_key(tables['models'][0])
    metadata = _build_catalog(tables)[key]
    # Only identifiers and names are needed for the rest of the lineage graph.
    family = {_model_key(row): row for row in ModelMetadataRecord.objects.filter(
        domain__iexact=domain).values('domain', 'identifier', 'display_name')}
    family[key] = metadata
    relationships = {}
    for row in ModelMetadataRelationship.objects.filter(
            record__domain__iexact=domain, ordinal=0).values(
                'record__domain', 'record__identifier', 'base_identifier', 'base_name', 'relationship'):
        relationships[(row.pop('record__domain').lower(), row.pop('record__identifier').lower())] = row
    for entry in family.values():
        entry['display_name'] = entry['display_name'] or entry['identifier']
    _attach_lineage(family, relationships, model_keys=[key])
    return metadata


def with_model_card_ids(metadata, model_ids_by_identifier):
    """Deep-copy ``metadata`` and attach model-card page ids to lineage links."""
    if metadata is None:
        return None
    metadata = deepcopy(metadata)
    ids = {name.lower(): value for name, value in model_ids_by_identifier.items()}
    for entry in metadata['lineage']['ancestors'] + metadata['lineage']['related_models']:
        entry['model_card_id'] = ids.get((entry['identifier'] or '').lower())
    return metadata


def _slot_value(metadata, slot):
    """Resolve a badge/assertion slot name to its value in the card context."""
    for prefix, container in (('eval_', 'eval_io'), ('intended_use_', 'intended_use')):
        if slot.startswith(prefix):
            return metadata[container].get(slot[len(prefix):])
    if slot.startswith('contributors_'):
        return metadata['contributors'].get(slot[len('contributors_'):])
    return metadata.get(slot)


def finalize_card_context(metadata, source):
    """Add source labels and comparable field-level confidence summaries."""
    from .schema import schema_yaml
    metadata['schema_yaml'] = schema_yaml()
    architecture_labels = {
        'convolutional_neural_network': 'CNN',
        'vision_transformer': 'Vision transformer',
        'recurrent_convolutional_neural_network': 'Recurrent CNN',
        'hybrid_biological_convolutional': 'Bio-inspired CNN',
        'hybrid_convolutional_transformer': 'CNN + transformer',
        'raw_pixels': 'Raw pixels',
    }
    supervision_labels = {
        'supervised': 'Supervised',
        'self_supervised': 'Self-supervised',
        'weakly_supervised': 'Weakly supervised',
        'contrastive_pretrain_supervised_finetune': 'Contrastive + supervised',
        'supervised_neural_alignment': 'Supervised + alignment',
    }
    def short_label(kind, description, labels):
        if kind in labels:
            return labels[kind]
        if description and len(description) <= 28:
            return description
        return 'View details' if description else None

    metadata['header_architecture'] = short_label(
        metadata.get('architecture_family'), metadata.get('architecture_description'), architecture_labels)
    metadata['header_supervision'] = short_label(
        metadata.get('supervision_type'), metadata.get('supervision_description'), supervision_labels)
    metadata['header_licenses'] = license_labels(metadata.get('license'))
    metadata['source'] = source
    metadata['source_label'] = 'Submission metadata' if source == 'legacy' else 'Curated metadata'
    metadata.setdefault('assertions', [])
    badges = metadata.setdefault('field_badges', {})
    documented = [slot for slot in ALL_FIELD_SLOTS if _slot_value(metadata, slot)]
    for slot in documented:
        if source == 'legacy' or slot not in badges:
            badges[slot] = {'status': 'probable', 'source': (
                'submission record' if source == 'legacy' else 'Confidence not documented')}
    counts = Counter(badges[slot]['status'] for slot in documented)
    metadata['verification'] = dict(
        verified=counts['verified'], probable=counts['probable'], uncertain=counts['uncertain'],
        undocumented=len(ALL_FIELD_SLOTS) - len(documented), total=len(ALL_FIELD_SLOTS),
        documented=len(documented))
    metadata['section_summary'] = {
        'intended_use': {
            'documented': sum(bool(value) for value in metadata['intended_use'].values()),
            'total': len(metadata['intended_use']),
        },
        'eval_io': {
            'documented': sum(bool(value) for value in metadata['eval_io'].values()),
            'total': len(metadata['eval_io']),
        },
    }
    return metadata


def lineage_identifiers(metadata):
    """Catalog identifiers referenced by this model's lineage panel."""
    if metadata is None:
        return []
    lineage = metadata['lineage']
    identifiers = [ancestor['identifier'] for ancestor in lineage['ancestors']
                   if ancestor['identifier']]
    identifiers += [related['identifier'] for related in lineage['related_models']]
    return identifiers
