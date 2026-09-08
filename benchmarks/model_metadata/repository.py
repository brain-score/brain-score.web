"""Read-side of the six-table model-metadata catalog.

Loads the CSVs in ``data/`` (built by ``scripts/build_model_metadata_catalog.py``
from the curation workbook) into the exact context shape the model-card
templates consume (``_model_metadata*.html``). Pure stdlib — no Django, no
database — so the card works before migration 0027 is ever applied.

Lineage rules (implemented in ``_attach_lineage``):

* **Parent** — a model's single direct base, from ``model_relationships.csv``
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
import csv
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / 'data'
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

# assertions.csv path -> template field slot(s). Slots are the keys templates
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


def _read_csv(name):
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


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
    return row['domain'], row['identifier']


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


def _attach_lineage(models, relationships):
    children_by_base = defaultdict(list)
    for model_key, relationship in relationships.items():
        if relationship['base_identifier']:
            children_by_base[(model_key[0], relationship['base_identifier'])].append(model_key)

    for model_key, model in models.items():
        domain, identifier = model_key

        # ancestors: walk parent links upward, guarding against cycles
        ancestors = []
        visited = {model_key}
        ancestor_key = model_key
        while ancestor_key in relationships:
            relationship = relationships[ancestor_key]
            base_identifier = relationship['base_identifier']
            base_key = (domain, base_identifier) if base_identifier else None
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
            related_keys.update(children_by_base[(domain, own_relationship['base_identifier'])])
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
            'current': {'identifier': identifier, 'display_name': model['display_name']},
            'related_models': related,
            'hidden_related_count': max(0, len(related) - INITIAL_RELATED_MODELS),
            'has_relationships': bool(ancestors or related),
        }


@lru_cache(maxsize=1)
def _load_catalog():
    models = {}
    for row in _read_csv('models.csv'):
        key = _model_key(row)
        if key in models:
            raise ValueError(f'Duplicate model metadata record: {key}')
        models[key] = _build_metadata(row)

    for row in _read_csv('model_datasets.csv'):
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

    for row in _read_csv('intended_use.csv'):
        model = models.get(_model_key(row))
        if model is not None and row['category'] in model['intended_use']:
            model['intended_use'][row['category']].append(row['value'])

    for row in _read_csv('contributors.csv'):
        model = models.get(_model_key(row))
        if model is not None:
            model['contributors'].setdefault(row['kind'], []).append(row['name'])

    relationships = {}
    for row in _read_csv('model_relationships.csv'):
        key = _model_key(row)
        if int(row['ordinal']) == 0:  # single direct parent drives lineage
            relationships[key] = row

    assertion_counts = defaultdict(Counter)
    badge_slots = defaultdict(dict)  # model key -> {slot: {'status', 'source'}}
    for row in _read_csv('assertions.csv'):
        key = _model_key(row)
        assertion_counts[key][row['status']] += 1
        if row['status'] in ('probable', 'uncertain'):  # verified fields stay clean
            source = (row['source'] or 'curation workbook').replace('_', ' ')
            for slot in ASSERTION_PATH_SLOTS.get(row['path'], ()):
                badge_slots[key][slot] = {'status': row['status'], 'source': source}

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
        model['has_card_content'] = any(model[field] for field in CARD_CONTENT_FIELDS) \
            or bool(model['datasets'] or model['contributors'])

    _attach_lineage(models, relationships)
    return models


@lru_cache(maxsize=1)
def _identifier_index():
    """Case-insensitive identifier lookup, since DB model names and workbook
    identifiers occasionally disagree on casing."""
    return {(domain, identifier.casefold()): (domain, identifier)
            for domain, identifier in _load_catalog()}


def get_model_metadata(domain, identifier):
    """Return the card-ready metadata dict for ``identifier``, or None."""
    if not identifier:
        return None
    catalog = _load_catalog()
    entry = catalog.get((domain, identifier))
    if entry is None:
        key = _identifier_index().get((domain, str(identifier).casefold()))
        entry = catalog.get(key) if key else None
    return entry


def with_model_card_ids(metadata, model_ids_by_identifier):
    """Deep-copy ``metadata`` and attach model-card page ids to lineage links."""
    if metadata is None:
        return None
    metadata = deepcopy(metadata)
    for entry in metadata['lineage']['ancestors'] + metadata['lineage']['related_models']:
        entry['model_card_id'] = model_ids_by_identifier.get(entry['identifier'])
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
    """Last step for both metadata paths ('catalog' | 'legacy'): tag the source,
    add per-section documented/total counts (drives the collapsed empty-section
    UI), and — for legacy models — replace the provenance counts with honest
    ones: legacy values are auto-extracted from the submission record, so they
    are *probable* at best, never verified.

    Denominators differ slightly by source (catalog: 31 assertion paths,
    legacy: the ~29 card slots) — near-comparable, not identical.
    """
    metadata['source'] = source
    intended_use = metadata['intended_use']
    eval_io = metadata['eval_io']
    # tokenizer excluded: "not applicable" for vision models is not a gap
    eval_fields = ('test_datasets', 'validation_datasets', 'input_format',
                   'output_format', 'model_version')
    metadata['section_summary'] = {
        'intended_use': {
            'documented': sum(1 for values in intended_use.values() if values),
            'total': len(intended_use),
        },
        'eval_io': {
            'documented': sum(1 for field in eval_fields if eval_io.get(field)),
            'total': len(eval_fields),
        },
    }
    if source == 'legacy':
        documented = [slot for slot in ALL_FIELD_SLOTS if _slot_value(metadata, slot)]
        metadata['verification'] = {
            'verified': 0,
            'probable': len(documented),
            'uncertain': 0,
            'undocumented': len(ALL_FIELD_SLOTS) - len(documented),
            'total': len(ALL_FIELD_SLOTS),
        }
        metadata['field_badges'] = {
            slot: {'status': 'probable', 'source': 'submission record'}
            for slot in documented}
    return metadata


def lineage_identifiers(metadata):
    """Catalog identifiers referenced by this model's lineage panel."""
    if metadata is None:
        return []
    lineage = metadata['lineage']
    identifiers = [ancestor['identifier'] for ancestor in lineage['ancestors']
                   if ancestor['identifier'] and ancestor['has_metadata']]
    identifiers += [related['identifier'] for related in lineage['related_models']]
    return identifiers
