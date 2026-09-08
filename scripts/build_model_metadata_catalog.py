"""Convert the model-metadata curation workbook into the six-table catalog CSVs.

The workbook (a Google-Sheets export) is transposed: row 1 holds one column per
model, and each subsequent row is one metadata field ("parameter_count",
"License", ...). This script normalises it into the six relational tables that
mirror the ``ModelMetadata*`` Django models of migration 0027 (see
``benchmarks/management/commands/import_model_metadata.py``):

    models.csv               one row per model (scalar fields)
    model_datasets.csv       training/pretraining/fine-tuning/test/validation datasets
    intended_use.csv         applications / users / limitations / biases
    contributors.csv         creators / organizations
    model_relationships.csv  direct base-model links (lineage)
    assertions.csv           per-field provenance: verified / inferred / undocumented

Usage:
    python scripts/build_model_metadata_catalog.py <workbook.csv> \
        [--out benchmarks/model_metadata/data]

The output is deterministic (sorted rows) so reruns produce clean git diffs.
"""
import argparse
import csv
import re
from pathlib import Path

DOMAIN = 'vision'
MODEL_COLUMNS_START = 4  # columns 0-3 are Field / Type / Preferred source / Question answered

# Workbook row labels -> canonical field keys used throughout this script.
FIELD_ALIASES = {
    'model_name': 'model_name',
    'base model': 'base_model',
    'model_version': 'version',
    'model_ID': 'model_id',
    'architecture_family': 'architecture',
    'model_recipe/model_process (steps that model takes)': 'training_process',
    'parameter_count': 'parameter_count',
    'trainable_layer_count': 'trainable_layers',
    'input_resolution': 'input_resolution',
    'recurrent': 'recurrent',
    'Dataset_source (training_data)': 'dataset_source',
    'dataset_size': 'dataset_size',
    'supervision_type': 'supervision',
    'training_objective': 'training_objective',
    'weights_provider': 'weights_provider',
    'checkpoint_identifier': 'checkpoint_identifier',
    'preprocessing_recipe (Maybe reconsider how we store this)': 'preprocessing',
    'learning rate': 'learning_rate',
    'Batch size': 'batch_size',
    'Test dataset': 'test_datasets',
    'Validation dataset': 'validation_datasets',
    'Loss function': 'loss_function',
    'Recommended applications': 'applications',
    'Target users': 'users',
    'Known weaknesses': 'limitations',
    'Biases': 'biases',
    'Expected input and output format': 'interface',
    'Tokenizer?': 'tokenizer',
    'Creator': 'creators',
    'Organization': 'organizations',
    'License': 'license',
    'Confidence': 'confidence',
    'Visual Degrees': 'visual_degrees',
}

# Values in these families mean "the curator could not document this" -- they
# become empty cells plus an `undocumented` assertion rather than card text.
UNDOCUMENTED_RE = re.compile(
    r'^\s*(n/?a\b|none\b|nonw\b|not\b|unconfirmed\b|unknown\b|uncertain\b|\?+\s*$|no\b)',
    re.IGNORECASE)
# Recurrent/tokenizer answers legitimately start with "No"/"None (0)".
LITERAL_FIELDS = {'recurrent', 'tokenizer'}

# Markers that the value was derived rather than read off the primary source.
# Fallback only — the workbook's cell colors (see --colors) are the primary
# confidence signal.
INFERRED_RE = re.compile(
    r'\b(inferred|assumed|presumed|likely|probably|per naming convention|'
    r'general knowledge|not explicit|implied|unofficial|commonly)\b|\?',
    re.IGNORECASE)

# Curator cell-color convention in the Sheets workbook:
#   green = verified / high confidence, yellow = medium (inferred),
#   red = low confidence, uncolored = no annotation (fall back to text).
COLOR_STATUSES = (
    ({'FF93C47D', 'FFB6D7A8', 'FF6AA84F', 'FF38761D', 'FFD9EAD3'}, 'verified'),
    ({'FFFFE599', 'FFFFD966', 'FFF1C232', 'FFBF9000', 'FFFFF2CC'}, 'inferred'),
    ({'FFFF0000', 'FFE06666', 'FFCC0000', 'FF990000', 'FFF4CCCC'}, 'low'),
)


def _classify_fill(rgb):
    """Map a cell fill to a status: exact Sheets-palette match first, then a
    crude hue fallback so tint variations still classify."""
    if not rgb or len(rgb) != 8:
        return None
    for palette, status in COLOR_STATUSES:
        if rgb in palette:
            return status
    red, green, blue = (int(rgb[i:i + 2], 16) for i in (2, 4, 6))
    if max(red, green, blue) - min(red, green, blue) < 24:  # white/gray, no signal
        return None
    if green > red and green > blue:
        return 'verified'
    if red > 180 and green > 150 and blue < 140:
        return 'inferred'
    if red > green and red > blue:
        return 'low'
    return None


def load_cell_statuses(xlsx_path):
    """Read the color-coded workbook and return {(field_key, column_name): status}."""
    import openpyxl  # optional dependency, only needed with --colors
    worksheet = openpyxl.load_workbook(xlsx_path).active
    headers = {column: (worksheet.cell(1, column).value or '').strip()
               for column in range(MODEL_COLUMNS_START + 1, worksheet.max_column + 1)}
    statuses = {}
    for row in range(2, worksheet.max_row + 1):
        label = (worksheet.cell(row, 1).value or '').strip()
        field = FIELD_ALIASES.get(label)
        if not field:
            continue
        for column, column_name in headers.items():
            if not column_name:
                continue
            fill = worksheet.cell(row, column).fill
            if fill and fill.fill_type == 'solid':
                status = _classify_fill(getattr(fill.start_color, 'rgb', None))
                if status:
                    statuses[(field, column_name)] = status
    return statuses

# Assertion path -> workbook field feeding it. Drives the provenance meter on
# the model card (verified / inferred / undocumented counts).
ASSERTION_PATHS = (
    ('/model/display_name', 'model_name'),
    ('/model/version', 'version'),
    ('/model/architecture', 'architecture'),
    ('/model/parameter_count', 'parameter_count'),
    ('/model/trainable_layers', 'trainable_layers'),
    ('/model/input_resolution', 'input_resolution'),
    ('/model/recurrent', 'recurrent'),
    ('/model/visual_degrees', 'visual_degrees'),
    ('/model/supervision', 'supervision'),
    ('/training/process', 'training_process'),
    ('/training/objective', 'training_objective'),
    ('/training/loss', 'loss_function'),
    ('/training/learning_rate', 'learning_rate'),
    ('/training/batch_size', 'batch_size'),
    ('/training/preprocessing', 'preprocessing'),
    ('/data/training_datasets', 'dataset_source'),
    ('/data/dataset_size', 'dataset_size'),
    ('/eval/test_datasets', 'test_datasets'),
    ('/eval/validation_datasets', 'validation_datasets'),
    ('/io/interface', 'interface'),
    ('/io/tokenizer', 'tokenizer'),
    ('/provenance/weights_provider', 'weights_provider'),
    ('/provenance/checkpoint', 'checkpoint_identifier'),
    ('/legal/license', 'license'),
    ('/people/creators', 'creators'),
    ('/people/organizations', 'organizations'),
    ('/lineage/base_models', 'base_model'),
    ('/use/applications', 'applications'),
    ('/use/users', 'users'),
    ('/use/limitations', 'limitations'),
    ('/use/biases', 'biases'),
)


def _clean(value, field=None):
    """Collapse whitespace; drop cells that only say the value is unknown."""
    value = re.sub(r'\s+', ' ', (value or '')).strip()
    if not value:
        return None
    if field not in LITERAL_FIELDS and UNDOCUMENTED_RE.match(value):
        return None
    return value


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _norm(text):
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def parse_workbook(path):
    with open(path, newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.reader(stream))
    header, field_rows = rows[0], rows[1:]

    fields_by_key = {}
    trailing_row = None
    for row in field_rows:
        label = row[0].strip()
        if label in FIELD_ALIASES:
            fields_by_key[FIELD_ALIASES[row[0].strip() and row[0].rstrip()]] = row
        elif not label and any(cell.strip() for cell in row[MODEL_COLUMNS_START:]):
            trailing_row = row  # unlabeled links row at the bottom of the sheet

    models = []
    for col in range(MODEL_COLUMNS_START, len(header)):
        column_name = header[col].strip()
        if not column_name or column_name.lower().startswith('column '):
            continue
        raw = {key: (row[col] if col < len(row) else '')
               for key, row in fields_by_key.items()}
        if not any(value.strip() for value in raw.values()):
            continue
        if trailing_row is not None and col < len(trailing_row):
            link = trailing_row[col].strip()
            raw['source_url'] = link if link.startswith('http') else ''
        raw.setdefault('source_url', '')
        models.append({'column_name': column_name, 'raw': raw})
    return models


def resolve_identifier(model):
    """Brain-Score identifier: prefer a clean model_ID cell, else the column header."""
    for candidate in (model['raw'].get('model_id', ''), model['column_name']):
        candidate = candidate.strip()
        if candidate and ' ' not in candidate and '(' not in candidate:
            return candidate
    return model['column_name'].strip()


def dedupe(models):
    """The workbook's first pilot columns (AlexNet, Cornet, ...) reappear later
    under canonical identifiers; keep whichever column documents more fields."""
    by_identifier = {}
    for model in models:
        identifier = resolve_identifier(model)
        model['identifier'] = identifier
        filled = sum(1 for v in model['raw'].values() if v.strip())
        key = _norm(identifier)
        if key not in by_identifier or filled >= by_identifier[key][0]:
            by_identifier[key] = (filled, model)
    return [entry[1] for entry in by_identifier.values()]


def parse_parameter_count(text):
    if not text:
        return None, None
    exact_match = re.search(r'\d{1,3}(?:,\d{3})+', text)
    if exact_match:
        count = int(exact_match.group().replace(',', ''))
        return count, not INFERRED_RE.search(text)
    scaled_match = re.search(r'[~≈]?\s*(\d+(?:\.\d+)?)\s*([KMB])\b', text)
    if scaled_match:
        scale = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000}[scaled_match.group(2)]
        return int(float(scaled_match.group(1)) * scale), False
    if re.fullmatch(r'\d+', text):
        return int(text), True
    return None, None


def parse_resolution(text):
    if not text:
        return None, None, None
    match = re.search(r'(\d{2,4})\s*[x×]\s*(\d{2,4})(?:\s*[x×]\s*(\d))?', text)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3) or 3)
    crop = re.search(r'crop\s+(\d{2,4})', text, re.IGNORECASE)
    if crop:
        size = int(crop.group(1))
        return size, size, 3
    return None, None, None


def parse_recurrent(text):
    if not text:
        return None
    lowered = text.strip().lower()
    if lowered.startswith('yes'):
        return 'true'
    if lowered.startswith('no'):
        return 'false'
    return None


def parse_visual_degrees(text):
    if not text:
        return None
    if re.search(r'not set|not specified|unconfirmed|not actively|commonly', text, re.IGNORECASE):
        return None
    match = re.search(r'(?:visual_degrees\s*=\s*)?(\d+(?:\.\d+)?)\s*(?:degrees|degree|\()', text + '(', re.IGNORECASE)
    return match.group(1) if match else None


def classify_architecture(text):
    if not text:
        return ''
    lowered = text.lower()
    if 'pixel' in lowered and 'no architecture' in lowered:
        return 'raw_pixels'
    if 'v1 front-end' in lowered or 'biologically-fixed' in lowered or 'gabor' in lowered:
        return 'hybrid_biological_convolutional'
    if 'hybrid' in lowered and 'transformer' not in lowered:
        return 'recurrent_convolutional_neural_network' if 'rnn' in lowered else 'convolutional_neural_network'
    if ('resnet-vit' in lowered or ('hybrid' in lowered and 'transformer' in lowered)
            or 'conv stem' in lowered):
        return 'hybrid_convolutional_transformer'
    if 'transformer' in lowered or lowered.startswith('vit') or 'focal-modulation' in lowered:
        return 'vision_transformer'
    if 'recurrent' in lowered or 'cnn+rnn' in lowered:
        return 'recurrent_convolutional_neural_network'
    if 'hand-crafted' in lowered or 'hmax' in lowered:
        return 'other'
    if ('cnn' in lowered or 'convolutional' in lowered or 'convnext' in lowered
            or 'resnet' in lowered or 'efficientnet' in lowered or 'mobilenet' in lowered
            or 'nas-derived' in lowered or 'shufflenet' in lowered):
        return 'convolutional_neural_network'
    return 'other'


def classify_supervision(text):
    if not text:
        return ''
    lowered = text.lower()
    if 'no training' in lowered or lowered.startswith('n/a'):
        return 'none'
    if 'neural-alignment' in lowered:
        return 'supervised_neural_alignment'
    if 'self-supervised' in lowered or 'self-training' in lowered:
        return 'self_supervised'
    if 'weakly' in lowered:
        return 'weakly_supervised'
    if 'contrastive' in lowered:
        return 'contrastive_pretrain_supervised_finetune' if ('fine' in lowered or 'supervised' in lowered) else 'contrastive'
    if 'supervised' in lowered:
        return 'supervised'
    return 'other'


def classify_confidence(text):
    if not text:
        return ''
    head = re.split(r'[(\-–]', text.replace('/', '-'), maxsplit=1)[0].strip().lower()
    return {'high': 'high', 'medium-high': 'medium_high', 'medium high': 'medium_high',
            'medium': 'medium', 'low': 'low'}.get(head.replace('/', '-'), _slug(text[:20]))


def parse_interface(text):
    """Split 'RGB tensor 3x224x224 -> 1000-class logits' style strings."""
    if not text:
        return None, None
    for pattern in (r'\s*->\s*', r'\s*→\s*'):
        parts = re.split(pattern, text, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    match = re.match(r'Input:\s*(.+?);?\s*Output:\s*(.+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip(' ;'), match.group(2).strip()
    if re.fullmatch(r'[\w ]+,\s*[\w_ ]+', text):
        left, right = text.split(',', 1)
        return left.strip(), right.strip()
    return text, None


ROLE_KEYWORDS = (
    (re.compile(r'^(pre-?train(?:ing)?|stage\s*1)\s*[:\-]\s*', re.IGNORECASE), 'pretraining'),
    (re.compile(r'^(fine-?tun\w*|stage\s*[2-9])\s*[:\-]\s*', re.IGNORECASE), 'fine_tuning'),
)


def parse_training_datasets(source_text, size_text):
    """Split 'Pretrain: X; Fine-tune: Y' into per-role dataset rows."""
    if not source_text:
        return []
    rows = []
    for segment in re.split(r';|(?=Stage\s*\d\s*:)', source_text):
        segment = segment.strip(' ;')
        if not segment:
            continue
        role = 'training'
        for pattern, mapped_role in ROLE_KEYWORDS:
            match = pattern.match(segment)
            if match:
                role = mapped_role
                segment = segment[match.end():].strip()
                break
        if segment:
            rows.append({'role': role, 'name': segment})
    if rows and size_text:
        size_text = size_text.strip()
        if re.fullmatch(r'[~≈]?[\d,]+(\s*images)?', size_text):
            # a clean single number becomes the (single) chip's sample count
            rows[0]['count'] = size_text
        else:
            # multi-dataset sizes ("WIT-400M ~400M pairs; ImageNet-1k 1.28M/50K"):
            # match each chip to its size segment by the dataset's head token
            segments = [seg.strip() for seg in re.split(r'[;]', size_text) if seg.strip()]
            for row in rows:
                head = re.split(r'[\s(:,]', row['name'], maxsplit=1)[0].lower()
                for segment in segments:
                    position = segment.lower().find(head) if head else -1
                    if position < 0:
                        continue
                    remainder = segment[position + len(head):]
                    count = re.search(r'[~≈]?\s*\d[\d,.]*\s*[KMB]?\b[^;)]*', remainder)
                    if count:
                        row['count'] = count.group().strip()
                    break
    return rows


def split_list(text):
    """Intended-use cells hold either one statement or a delimited list."""
    if not text:
        return []
    if ';' in text:
        parts = [part.strip(' ;') for part in text.split(';')]
    elif text.count(',') >= 2 and all(len(part.strip()) < 80 for part in text.split(',')):
        parts = [part.strip() for part in text.split(',')]
    else:
        parts = [text.strip()]
    return [part for part in parts if part]


def assertion_status(raw_value, field, color_status=None):
    """Per-field provenance. An empty/'N/A' cell is undocumented no matter its
    color; otherwise the curator's cell color wins, and only uncolored cells
    fall back to the hedge-word heuristic."""
    cleaned = _clean(raw_value, field)
    if cleaned is None:
        return 'undocumented'
    if color_status:
        return color_status
    if INFERRED_RE.search(cleaned):
        return 'inferred'
    return 'verified'


def build_relationship(model, identifier_lookup):
    base_raw = _clean(model['raw'].get('base_model', ''))
    if not base_raw:
        return None
    primary = re.split(r'[;,]| \+ ', base_raw)[0].strip()
    # keep the readable head, drop trailing qualifiers
    base_name = re.split(r'\s+[-(]', primary, maxsplit=1)[0].strip() or primary
    base_identifier = identifier_lookup.get(_norm(base_name), _slug(base_name))
    if _norm(base_identifier) == _norm(model['identifier']):
        return None
    context = f"{base_raw} {model['raw'].get('training_process', '')}".lower()
    if 'derivative' in base_raw.lower() or 'derived' in base_raw.lower():
        relationship = 'derived_from'
    elif 'fine-tun' in context or 'finetun' in context:
        relationship = 'fine_tuned_from'
    else:
        relationship = 'variant_of'
    return {'base_identifier': base_identifier, 'base_name': base_name,
            'relationship': relationship}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', help='Path to the curation workbook CSV (transposed sheet)')
    parser.add_argument('--out', default='benchmarks/model_metadata/data',
                        help='Output directory for the six catalog CSVs')
    parser.add_argument('--colors', metavar='XLSX', default=None,
                        help='Matching .xlsx export of the same sheet; its cell fill '
                             'colors set per-field confidence (green=verified, '
                             'yellow=inferred, red=low). Requires openpyxl.')
    args = parser.parse_args()
    cell_statuses = load_cell_statuses(args.colors) if args.colors else {}

    models = dedupe(parse_workbook(args.workbook))
    models.sort(key=lambda m: m['identifier'].casefold())
    identifier_lookup = {}
    for model in models:
        for alias in (model['identifier'], model['column_name'],
                      model['raw'].get('model_name', '')):
            if alias.strip():
                identifier_lookup.setdefault(_norm(alias), model['identifier'])

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_rows, dataset_rows, use_rows = [], [], []
    contributor_rows, relationship_rows, assertion_rows = [], [], []

    for model in models:
        raw = model['raw']
        identifier = model['identifier']
        get = lambda key: _clean(raw.get(key, ''), key)

        parameter_count, parameter_exact = parse_parameter_count(get('parameter_count'))
        width, height, channels = parse_resolution(get('input_resolution'))
        input_format, output_format = parse_interface(get('interface'))
        tokenizer = get('tokenizer')
        if tokenizer and re.match(r'^(none|n/?a)\b', tokenizer, re.IGNORECASE):
            tokenizer = None  # vision models: card renders "not applicable"

        model_rows.append({
            'domain': DOMAIN,
            'identifier': identifier,
            'display_name': raw.get('model_name', '').strip() or model['column_name'],
            'version': get('version') or '',
            'architecture_family': classify_architecture(raw.get('architecture', '')),
            'architecture_description': get('architecture') or '',
            'parameter_count': parameter_count if parameter_count is not None else '',
            'parameter_count_exact': {True: 'true', False: 'false', None: ''}[parameter_exact],
            'trainable_layers': get('trainable_layers') or '',
            'recurrent': parse_recurrent(get('recurrent')) or '',
            'input_modality': 'image',
            'input_channels': channels or '',
            'input_height': height or '',
            'input_width': width or '',
            'visual_degrees': parse_visual_degrees(raw.get('visual_degrees', '')) or '',
            'visual_degrees_description': get('visual_degrees') or '',
            'supervision_type': classify_supervision(get('supervision')),
            'supervision_description': get('supervision') or '',
            'interface_description': get('interface') or '',
            'preprocessing_description': get('preprocessing') or '',
            'training_process': get('training_process') or '',
            'dataset_summary': get('dataset_source') or '',
            'weights_provider': get('weights_provider') or '',
            'checkpoint_identifier': get('checkpoint_identifier') or '',
            'source_url': raw.get('source_url', ''),
            'license': get('license') or '',
            'curation_confidence': classify_confidence(get('confidence')),
            # extended columns (not yet in migration 0027; the DB import command
            # reads only the columns it knows, so these ride along harmlessly)
            'training_objective': get('training_objective') or '',
            'loss_function': get('loss_function') or '',
            'learning_rate': get('learning_rate') or '',
            'batch_size': get('batch_size') or '',
            'input_format': input_format or '',
            'output_format': output_format or '',
            'tokenizer': tokenizer or '',
        })

        ordinal = 0
        for dataset in parse_training_datasets(get('dataset_source'), raw.get('dataset_size', '')):
            dataset_rows.append({
                'domain': DOMAIN, 'identifier': identifier, 'ordinal': ordinal,
                'dataset_identifier': _slug(dataset['name'][:40]),
                'dataset_name': dataset['name'], 'role': dataset['role'],
                'description': dataset.get('count', ''),
            })
            ordinal += 1
        for role, field in (('test', 'test_datasets'), ('validation', 'validation_datasets')):
            value = get(field)
            if value:
                dataset_rows.append({
                    'domain': DOMAIN, 'identifier': identifier, 'ordinal': ordinal,
                    'dataset_identifier': _slug(value[:40]), 'dataset_name': value,
                    'role': role, 'description': '',
                })
                ordinal += 1

        for category, field in (('applications', 'applications'), ('users', 'users'),
                                ('limitations', 'limitations'), ('biases', 'biases')):
            for index, value in enumerate(split_list(get(field))):
                use_rows.append({'domain': DOMAIN, 'identifier': identifier,
                                 'category': category, 'ordinal': index, 'value': value})

        for kind, field in (('creators', 'creators'), ('organizations', 'organizations')):
            value = get(field)
            if value:
                contributor_rows.append({'domain': DOMAIN, 'identifier': identifier,
                                         'kind': kind, 'ordinal': 0, 'name': value})

        relationship = build_relationship(model, identifier_lookup)
        if relationship:
            relationship_rows.append({'domain': DOMAIN, 'identifier': identifier,
                                      'ordinal': 0, **relationship})

        for path, field in ASSERTION_PATHS:
            color_status = cell_statuses.get((field, model['column_name']))
            assertion_rows.append({
                'domain': DOMAIN, 'identifier': identifier, 'path': path,
                'status': assertion_status(raw.get(field, ''), field, color_status),
                'source': 'curation_workbook',
            })

    tables = (
        ('models.csv', model_rows, None),
        ('model_datasets.csv', dataset_rows, None),
        ('intended_use.csv', use_rows, None),
        ('contributors.csv', contributor_rows, None),
        ('model_relationships.csv', relationship_rows, None),
        ('assertions.csv', assertion_rows, None),
    )
    for name, rows, _ in tables:
        path = out_dir / name
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f'{path}: {len(rows)} rows')


if __name__ == '__main__':
    main()
