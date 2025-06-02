import json
import logging
import numpy as np
from collections import defaultdict
from django.shortcuts import render

from .index import get_context
from benchmarks.models import FinalBenchmarkContext, FinalModelContext

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


def ag_grid_leaderboard(request, domain: str):
    # 1) Determine user and fetch context
    user = request.user if request.user.is_authenticated else None
    context = get_context(user=user, domain=domain, show_public=(user is None))

    # Extract model metadata for filters
    model_metadata = {
        'architectures': set(),
        'model_families': set(),
        'parameter_ranges': {'min': float('inf'), 'max': 0},
        'layer_ranges': {'min': float('inf'), 'max': 0},
        'size_ranges': {'min': float('inf'), 'max': 0},
        'runnable_options': set()
    }

    # 2) Build `row_data` from materialized-view models
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
                'complete': score.get('is_complete', True)
            }
        row_data.append(rd)

    # 3) Build `column_defs` to show only root-level parents first,
    #    then grouping rows and leaves hidden by default.
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

    # 3a) Root parents (no parent ⇒ visible)
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
            'context': { 'parentField': None, 'benchmarkId': field }
        })

    # 3b) All other groupings (version==0 & has parent) hidden initially
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

    # 3c) Leaf benchmarks hidden initially
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
            'context': { 'parentField': parent_field }
        })

    # 4) Attach JSON-serialized data to template context
    context['row_data'] = json.dumps([json_serializable(r) for r in row_data])
    context['column_defs'] = json.dumps(column_defs)
    context['benchmark_groups'] = json.dumps(make_benchmark_groups(context['benchmarks']))
    filtered_benchmarks = [b for b in context['benchmarks'] if b.identifier != 'average_vision_v0']
    context['benchmark_tree'] = json.dumps(build_benchmark_tree(filtered_benchmarks))

    # 5) Render the AG-Grid template
    return render(request, 'benchmarks/leaderboard/ag-grid-leaderboard.html', context)
