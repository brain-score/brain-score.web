import json
import logging
import numpy as np
from collections import defaultdict
from django.shortcuts import render
from .index import get_context
from ..utils import cache_get_context
from django.views.decorators.cache import cache_page
logger = logging.getLogger(__name__)

def json_serializable(obj):
    """Recursively convert NumPy and other types to Python native types"""
    if isinstance(obj, dict):
        return {k: json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_serializable(i) for i in obj]
    elif isinstance(obj, tuple):
        return tuple(json_serializable(i) for i in obj)
    elif isinstance(obj, (np.integer, np.int64)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif obj is None or obj == "X" or obj == "":
        return obj
    elif hasattr(obj, '__dict__'):
        return str(obj)
    return obj


def make_benchmark_groups(benchmarks):
    groups = defaultdict(list)
    for b in benchmarks:
        if b.number_of_all_children == 0:  # leaf benchmark
            parent_id = b.parent['identifier'] if b.parent else 'ungrouped'
            groups[parent_id].append({
                'identifier': b.identifier,
                'short_name': b.short_name,
            })
    return groups


def get_attr(obj, attr, default=None):
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def normalize_id(identifier):
    if identifier in ('average_vision', 'average_vision_v0'):
        return None  # treat neural and behavior as root-level
    return identifier.split('_v')[0] if identifier else None


def build_benchmark_tree(benchmarks, parent_id=None):
    tree = []

    for b in benchmarks:
        b_identifier = get_attr(b, 'identifier')
        b_short_name = get_attr(b, 'short_name')
        b_parent = get_attr(b, 'parent')

        b_parent_id = get_attr(b_parent, 'identifier') if b_parent else None

        if normalize_id(b_parent_id) == normalize_id(parent_id):
            node = {
                'id': b_identifier,
                'label': b_short_name
            }

            children = build_benchmark_tree(benchmarks, parent_id=b_identifier)
            if children:
                node['children'] = children

            tree.append(node)

    return tree


def round_up_aesthetically(value):
    """Round a number up to an aesthetically pleasing value (for range sliders)"""
    if value <= 0:
        return 100  # fallback

    # Convert to string to work with magnitude
    str_val = str(int(value))
    magnitude = len(str_val)

    if magnitude == 1:  # 1-9
        return 10
    elif magnitude == 2:  # 10-99
        return ((int(value) // 10) + 1) * 10
    elif magnitude == 3:  # 100-999
        return ((int(value) // 100) + 1) * 100
    elif magnitude == 4:  # 1000-9999
        return ((int(value) // 1000) + 1) * 1000
    else:  # 10000+
        # For very large numbers, round to nearest 10k, 100k, etc.
        power = 10 ** (magnitude - 2)
        return ((int(value) // power) + 1) * power


@cache_get_context(timeout=24 * 60 * 60)
def get_ag_grid_context(user=None, domain="vision", benchmark_filter=None, model_filter=None, show_public=False):
    """
    Get processed context data for AG Grid leaderboard.
    This function handles all the expensive data processing and is cached.
    """
    # Get the base context (this is already cached)
    context = get_context(user=user, domain=domain, show_public=show_public)

    # Extract model metadata for filters
    model_metadata = {
        'architectures': set(),
        'model_families': set(),
        'training_datasets': set(),
        'task_specializations': set(),
        'parameter_ranges': {'min': float('inf'), 'max': 0},
        'layer_ranges': {'min': float('inf'), 'max': 0},
        'size_ranges': {'min': float('inf'), 'max': 0},
        'runnable_options': set()
    }

    benchmark_metadata = {
        'regions': set(),
        'species': set(),
        'tasks': set(),
        'stimuli_ranges': {'min': float('inf'), 'max': 0},
        'public_data_available': set()
    }

    # Process benchmarks to extract metadata
    for benchmark in context['benchmarks']:
        if hasattr(benchmark, 'benchmark_data_meta') and benchmark.benchmark_data_meta:
            data = benchmark.benchmark_data_meta

            if data.get('region'):
                benchmark_metadata['regions'].add(data['region'])
            if data.get('species'):
                benchmark_metadata['species'].add(data['species'])
            if data.get('task'):
                benchmark_metadata['tasks'].add(data['task'])
            if data.get('data_publicly_available') is not None:
                benchmark_metadata['public_data_available'].add(data['data_publicly_available'])

        if hasattr(benchmark, 'benchmark_stimuli_meta') and benchmark.benchmark_stimuli_meta:
            stimuli = benchmark.benchmark_stimuli_meta
            if stimuli.get('num_stimuli'):
                benchmark_metadata['stimuli_ranges']['min'] = min(
                    benchmark_metadata['stimuli_ranges']['min'],
                    stimuli['num_stimuli']
                )
                benchmark_metadata['stimuli_ranges']['max'] = max(
                    benchmark_metadata['stimuli_ranges']['max'],
                    stimuli['num_stimuli']
                )

    benchmark_metadata_list = []
    for benchmark in context['benchmarks']:
        metadata_entry = {
            'identifier': benchmark.identifier,
            'region': None,
            'species': None,
            'task': None,
            'data_publicly_available': True,  # default
            'num_stimuli': None
        }

        # Extract data metadata
        if hasattr(benchmark, 'benchmark_data_meta') and benchmark.benchmark_data_meta:
            data = benchmark.benchmark_data_meta
            metadata_entry.update({
                'region': data.get('region'),
                'species': data.get('species'),
                'task': data.get('task'),
                'data_publicly_available': data.get('data_publicly_available', True)
            })

        # Extract stimuli metadata
        if hasattr(benchmark, 'benchmark_stimuli_meta') and benchmark.benchmark_stimuli_meta:
            stimuli = benchmark.benchmark_stimuli_meta
            metadata_entry['num_stimuli'] = stimuli.get('num_stimuli')

        benchmark_metadata_list.append(metadata_entry)

    # Build `row_data` from materialized-view models WITH metadata
    row_data = []
    for model in context['models']:
        # base fields
        rd = {
            'id': model.model_id,
            'rank': model.rank,
            'model': {
                'id': model.model_id,
                'name': model.name,
                'submitter': model.submitter.get('display_name') if model.submitter else None
            }
        }

        # Process model metadata if available
        metadata = {}
        if hasattr(model, 'model_meta') and model.model_meta:
            meta = model.model_meta

            # Extract metadata for this model
            metadata = {
                'architecture': meta.get('architecture', ''),
                'model_family': meta.get('model_family', ''),
                'total_parameter_count': meta.get('total_parameter_count', 0),
                'total_layers': meta.get('total_layers', 0),
                'model_size_mb': meta.get('model_size_mb', 0),
                'runnable': meta.get('runnable', False),
                'training_dataset': meta.get('training_dataset', ''),
                'task_specialization': meta.get('task_specialization', '')
            }

            # Collect values for filter options
            if meta.get('architecture'):
                # Split by comma and strip whitespace
                architectures = [arch.strip() for arch in meta['architecture'].split(',')]
                for arch in architectures:
                    if arch:  # Only add non-empty values
                        model_metadata['architectures'].add(arch)

            if meta.get('model_family'):
                families = [fam.strip() for fam in meta['model_family'].split(',')]
                for fam in families:
                    if fam:
                        model_metadata['model_families'].add(fam)

            if meta.get('training_dataset'):
                datasets = [ds.strip() for ds in meta['training_dataset'].split(',')]
                for ds in datasets:
                    if ds:
                        model_metadata['training_datasets'].add(ds)

            if meta.get('task_specialization'):
                specs = [spec.strip() for spec in meta['task_specialization'].split(',')]
                for spec in specs:
                    if spec:
                        model_metadata['task_specializations'].add(spec)

            # Parameter Count (convert to millions for display)
            if meta.get('total_parameter_count'):
                param_count_millions = meta['total_parameter_count'] / 1_000_000
                model_metadata['parameter_ranges']['min'] = min(
                    model_metadata['parameter_ranges']['min'],
                    param_count_millions
                )
                model_metadata['parameter_ranges']['max'] = max(
                    model_metadata['parameter_ranges']['max'],
                    param_count_millions
                )

            # Layer Count
            if meta.get('total_layers'):
                model_metadata['layer_ranges']['min'] = min(
                    model_metadata['layer_ranges']['min'],
                    meta['total_layers']
                )
                model_metadata['layer_ranges']['max'] = max(
                    model_metadata['layer_ranges']['max'],
                    meta['total_layers']
                )

            # Model Size (MB)
            if meta.get('model_size_mb'):
                model_metadata['size_ranges']['min'] = min(
                    model_metadata['size_ranges']['min'],
                    meta['model_size_mb']
                )
                model_metadata['size_ranges']['max'] = max(
                    model_metadata['size_ranges']['max'],
                    meta['model_size_mb']
                )

            # Runnable
            if 'runnable' in meta and meta['runnable'] is not None:
                model_metadata['runnable_options'].add(meta['runnable'])
        else:
            # Default metadata if none exists
            metadata = {
                'architecture': '',
                'model_family': '',
                'total_parameter_count': 0,
                'total_layers': 0,
                'model_size_mb': 0,
                'runnable': False,
                'training_dataset': '',
                'task_specialization': ''
            }

        # Add metadata to row data
        rd['metadata'] = metadata

        # now flatten out each score dict
        for score in model.scores or []:
            vid = score.get('versioned_benchmark_identifier')
            # fallback for missing IDs
            if not vid:
                continue
            rd[vid] = {
                'value': score.get('score_ceiled', 'X'),
                'raw': score.get('score_raw'),
                'error': score.get('error'),
                'color': score.get('color'),
                'complete': score.get('is_complete', True),
                'benchmark': score.get('benchmark', {})  # Include benchmark metadata for bibtex collection
            }
        row_data.append(rd)

    # Build `column_defs` to show only root-level parents first,
    # then grouping rows and leaves hidden by default.
    # Rank & Model pinned columns
    column_defs = [
        {'field': 'rank',
         'headerName': 'Rank',
         'pinned': 'left',
         'width': 100,
         'filter': False
         },
        {'field': 'model',
         'headerName': 'Model',
         'pinned': 'left',
         'width': 400,
         'minWidth': 180,
         'resizable': True,
         'cellRenderer': 'modelCellRenderer',
         'comparator': 'modelComparator',
         'getQuickFilterText': 'function(params) { return params.value?.name || ""; }'
         }
    ]

    # Root parents (no parent ⇒ visible)
    root_parents = [b for b in context['benchmarks'] if not b.parent]
    for b in root_parents:
        field = b.identifier
        column_defs.append({
            'field': field,
            'headerName': b.short_name,
            'headerComponent': 'expandableHeaderComponent',
            'cellRenderer': 'scoreCellRenderer',
            'hide': False,
            'sortable': True,
            'width': 150,
            'context': {'parentField': None, 'benchmarkId': field}
        })

    # All other groupings (version==0 & has parent) hidden initially
    groupings = [b for b in context['benchmarks'] if b.parent and b.version == 0]
    for b in groupings:
        field = b.identifier
        parent_field = b.parent['identifier']
        hide = not parent_field.startswith('average_')  # show if neural or behavioral
        column_defs.append({
            'field': field,
            'headerName': b.short_name,
            'headerComponent': 'expandableHeaderComponent',
            'cellRenderer': 'scoreCellRenderer',
            'hide': hide,
            'sortable': True,
            'width': 150,
            'context': {
                'parentField': parent_field,
                'benchmarkId': field
            }
        })

    # sorting so roots
    priority_order = ['average', 'neural', 'behavior', 'engineering']

    def get_priority(field):
        if not isinstance(field, str):
            return 999  # fallback for unexpected values
        prefix = field.split('_')[0]
        return priority_order.index(prefix) if prefix in priority_order else 999

    column_defs.sort(key=lambda col: get_priority(col.get('field')))

    # Leaf benchmarks hidden initially
    leaves = [b for b in context['benchmarks'] if b.number_of_all_children == 0]
    for b in leaves:
        field = b.identifier
        parent_field = b.parent['identifier']
        column_defs.append({
            'field': field,
            'width': 150,
            'headerName': b.short_name,
            'headerComponent': 'leafComponent',
            'cellRenderer': 'scoreCellRenderer',
            'hide': True,
            'sortable': True,
            'context': {'parentField': parent_field}
        })

    # Convert filter metadata to frontend-friendly format
    filter_options = {
        'architectures': sorted(list(model_metadata['architectures'])),
        'model_families': sorted(list(model_metadata['model_families'])),
        'training_datasets': sorted(list(model_metadata['training_datasets'])),
        'task_specializations': sorted(list(model_metadata['task_specializations'])),
        'parameter_ranges': {
            'min': 0,  # Always start at 0
            'max': round_up_aesthetically(model_metadata['parameter_ranges']['max']) if
            model_metadata['parameter_ranges']['max'] > 0 else 100
        },
        'layer_ranges': {
            'min': 0,  # Always start at 0
            'max': round_up_aesthetically(model_metadata['layer_ranges']['max']) if model_metadata['layer_ranges'][
                                                                                        'max'] > 0 else 500
        },
        'size_ranges': {
            'min': 0,  # Always start at 0
            'max': round_up_aesthetically(model_metadata['size_ranges']['max']) if model_metadata['size_ranges'][
                                                                                       'max'] > 0 else 1000
        },
        'runnable_options': sorted(list(model_metadata['runnable_options'])),
        'benchmark_regions': sorted(list(benchmark_metadata['regions'])),
        'benchmark_species': sorted(list(benchmark_metadata['species'])),
        'benchmark_tasks': sorted(list(benchmark_metadata['tasks'])),
        'stimuli_ranges': {
            'min': 0,
            'max': round_up_aesthetically(benchmark_metadata['stimuli_ranges']['max']) if benchmark_metadata['stimuli_ranges']['max'] > 0 else 1000
        }
    }


    # 4) Attach JSON-serialized data to template context
    stimuli_map = {}
    data_map = {}
    metric_map = {}

    for b in context['benchmarks']:
        stimuli_map[b.identifier] = getattr(b, 'benchmark_stimuli_meta', {}) or {}
        data_map[b.identifier] = getattr(b, 'benchmark_data_meta', {}) or {}
        metric_map[b.identifier] = getattr(b, 'benchmark_metric_meta', {}) or {}

    # dump benchmark metadata (all three tables)
    context['benchmarkStimuliMetaMap'] = json.dumps(stimuli_map)
    context['benchmarkDataMetaMap'] = json.dumps(data_map)
    context['benchmarkMetricMetaMap'] = json.dumps(metric_map)

    layer_map = context.get('layer_mapping', {})

    # now rebuild your model_metadata_map, merging in layer_mapping
    model_meta_map = {}
    for m in context['models']:
        if not (hasattr(m, 'model_meta') and m.model_meta):
            continue

        # start from the existing metadata dict
        meta = dict(m.model_meta)

        # if this model has a .layers attribute, add it under "layer_mapping"
        if hasattr(m, 'layers'):
            meta['layer_mapping'] = m.layers

        model_meta_map[m.name] = meta

    # serialize out to JSON (and make sure all numpy types etc. are native Python)
    context['model_metadata_map'] = json.dumps(json_serializable(model_meta_map))
    context['column_defs'] = json.dumps(column_defs)
    context['benchmark_groups'] = json.dumps(make_benchmark_groups(context['benchmarks']))
    context['filter_options'] = json.dumps(filter_options)
    context['benchmark_metadata'] = json.dumps(benchmark_metadata_list)
    filtered_benchmarks = [b for b in context['benchmarks'] if b.identifier != 'average_vision_v0']
    context['benchmark_tree'] = json.dumps(build_benchmark_tree(filtered_benchmarks))
    
    # Create simple benchmark ID mapping for frontend navigation links
    benchmark_ids = {}
    for benchmark in context['benchmarks']:
        if benchmark.id:  # Only include benchmarks with valid IDs
            benchmark_ids[benchmark.identifier] = benchmark.id

    # Return processed AG Grid context
    ag_context = {
        'row_data': json.dumps([json_serializable(r) for r in row_data]),
        'column_defs': json.dumps(column_defs),
        'benchmark_groups': json.dumps(make_benchmark_groups(context['benchmarks'])),
        'filter_options': json.dumps(filter_options),
        'benchmark_metadata': json.dumps(benchmark_metadata_list),
        'benchmark_tree': json.dumps(build_benchmark_tree([b for b in context['benchmarks'] if b.identifier != 'average_vision_v0'])),
        'benchmark_ids': json.dumps(benchmark_ids)
    }
    
    # Merge with original context
    context.update(ag_context)
    return context

@cache_page(24 * 60 * 60)
def ag_grid_leaderboard(request, domain: str):
    # 1) Determine user and fetch context
    user = request.user if request.user.is_authenticated else None
    context = get_ag_grid_context(user=user, domain=domain, show_public=(user is None))

    # Render the AG-Grid template
    return render(request, 'benchmarks/leaderboard/ag-grid-leaderboard.html', context)
