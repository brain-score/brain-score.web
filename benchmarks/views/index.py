from collections import ChainMap
import json
import logging
import numpy as np
import pandas as pd
import re
from collections import namedtuple
from colour import Color
from django.shortcuts import render
from django.template.defaulttags import register
from django.views.decorators.cache import cache_page
from tqdm import tqdm

from benchmarks.models import BenchmarkType, BenchmarkInstance, Model, Score, generic_repr

_logger = logging.getLogger(__name__)

BASE_DEPTH = 1

colors_redgreen = list(Color('red').range_to(Color('green'), 101))
colors_gray = list(Color('#f2f2f2').range_to(Color('#404040'), 101))
# scale colors: highlight differences at the top-end of the spectrum more than at the lower end
a, b = 0.2270617, 1.321928  # fit to (0, 0), (60, 50), (100, 100)
colors_redgreen = [colors_redgreen[int(a * np.power(i, b))] for i in range(len(colors_redgreen))]
colors_gray = [colors_gray[int(a * np.power(i, b))] for i in range(len(colors_gray))]
color_suffix = '_color'
color_None = '#e0e1e2'
not_shown_set = set()


@cache_page(24 * 60 * 60)
def view(request):
    context = get_context()
    return render(request, 'benchmarks/index.html', context)


def get_context(user=None):
    benchmarks = _collect_benchmarks()
    models = _collect_models(benchmarks, user)

    # to save vertical space, we strip the lab name in front of benchmarks.
    uniform_benchmarks = {}  # keeps the original benchmark name
    for benchmark in benchmarks:  # remove lab for more compactness
        benchmark.long_name = benchmark.benchmark_type.identifier
        uniform_benchmarks[benchmark.benchmark_type.identifier] = benchmark.benchmark_type.identifier
        match = re.match(r'[^\.]+\.(.+)', benchmark.benchmark_type.identifier)
        if match:
            uniform_benchmarks[benchmark.benchmark_type.identifier] = match.group(1)
            benchmark.identifier = benchmark.benchmark_type.identifier = match.group(1)
        else:
            benchmark.identifier = benchmark.benchmark_type.identifier
        benchmark.ceiling = represent(benchmark.ceiling)
    # map from a benchmark to its parent
    benchmark_parents = {
        benchmark.long_name: benchmark.benchmark_type.parent.identifier if benchmark.benchmark_type.parent else None
        for benchmark in benchmarks}
    # configure benchmark level shown by default
    uniform_parents = set(
        benchmark_parents.values())  # we're going to use the fact that all benchmark instances currently point to their direct parent
    not_shown_set = {benchmark.long_name for benchmark in benchmarks if benchmark.depth > BASE_DEPTH}

    # data for javascript comparison script
    comparison_data = _build_comparison_data(models)

    return {'models': models, 'benchmarks': benchmarks,
            "benchmark_parents": benchmark_parents, "uniform_parents": uniform_parents,
            # "uniform_benchmarks": uniform_benchmarks,
            "not_shown_set": not_shown_set, "has_user": False,
            "comparison_data": json.dumps(comparison_data)}


class Tree:
    def __init__(self, value, depth, parent=None, children=None):
        self.value = value
        self.depth = depth
        self.parent = parent
        self.children = children

    def __repr__(self):
        return generic_repr(self)


def _collect_benchmarks():
    # build tree structure of parent relationships
    benchmark_types = BenchmarkType.objects.select_related('reference')
    root_benchmarks = benchmark_types.filter(parent=None).order_by('order')
    root_trees = []
    for root_benchmark in root_benchmarks:
        root_tree = Tree(value=root_benchmark, depth=0)
        root_trees.append(root_tree)
        traverse_todo = [root_tree]
        # traverse the tree, filling in children in the process
        while traverse_todo:
            node = traverse_todo.pop()
            children = benchmark_types.filter(parent=node.value).order_by('order')
            children = [Tree(value=child, parent=node, depth=node.depth + 1) for child in children]
            node.children = children
            traverse_todo += children

    # gather actual benchmark instances and insert dummy instances for parents
    benchmarks = []
    overall_order = 0
    for tree in root_trees:
        # traverse the tree depth-first to go from highest parent to lowest child, corresponding to the website display
        traverse_todo = [tree]
        while traverse_todo:
            node = traverse_todo.pop(0)  # pop first item --> recent child hierarchy with lowest order
            if node.children:  # if abstract benchmark hierarchy, insert dummy instance
                instance = BenchmarkInstance(benchmark_type=node.value, version=None, ceiling=None, ceiling_error=None)
                instance.children = [child.value.identifier for child in node.children]
                traverse_todo = node.children + traverse_todo
            else:  # no children --> it's a specific instance
                instance = BenchmarkInstance.objects.select_related('benchmark_type__reference') \
                    .filter(benchmark_type=node.value).latest('version')  # latest instance for this type
            instance.parent = node.parent.value if node.parent else None
            instance.root_parent = tree.value.identifier
            instance.depth = node.depth
            instance.overall_order = overall_order
            overall_order += 1
            benchmarks.append(instance)
    # add shortcut to identifier
    for benchmark in benchmarks:
        benchmark.identifier = benchmark.benchmark_type.identifier
    return benchmarks


def _collect_models(benchmarks, user=None):
    """
    :param user: The user whose profile we are currently on, if any
    """
    # iteratively collect scores for all benchmarks. We start with the actual instances, storing their respective
    # parents to traverse up the hierarchy which we iteratively visit until empty.
    benchmark_todos = [benchmark for benchmark in benchmarks if not hasattr(benchmark, 'children')]
    scores = None
    while benchmark_todos:
        benchmark = benchmark_todos.pop(0)
        if not hasattr(benchmark, 'children'):  # actual instance without children, we can just retrieve the scores
            benchmark_scores = Score.objects.filter(benchmark=benchmark).select_related('model')
            benchmark_scores = pd.DataFrame([
                {'benchmark': benchmark.identifier, 'overall_order': benchmark.overall_order,
                 'model': score.model.identifier,
                 'score_ceiled': score.score_ceiled, 'score_raw': score.score_raw, 'error': score.error}
                for score in benchmark_scores])
        else:  # hierarchy level, we need to aggregate the scores in the hierarchy below
            children_scores = scores[scores['benchmark'].isin(benchmark.children)]
            benchmark_scores = children_scores.fillna(0).groupby('model').mean().reset_index()
            benchmark_scores['benchmark'] = benchmark.identifier
        scores = benchmark_scores if scores is None else pd.concat((scores, benchmark_scores))
        if benchmark.parent:
            # because of copy-by-value, `benchmark.parent` does not have a `.children` attribute
            parent = [b for b in benchmarks if b.identifier == benchmark.parent.identifier][0]
            if parent in benchmark_todos:
                continue  # already in list
            benchmark_todos.append(parent)
    # setup benchmark metadata for all scores
    benchmark_lookup = {benchmark.identifier: benchmark for benchmark in benchmarks}
    minmax = {benchmark: (
        min(group['score_ceiled'].fillna(0)),
        max(group['score_ceiled'].fillna(0))
        # this is an ugly hack to make the gray less visually dominant on the page
        * (2.5 if benchmark_lookup[benchmark].root_parent == 'engineering' else 1))
        for benchmark, group in scores.groupby('benchmark')}

    # arrange into per-model scores
    # - prepare model meta
    model_meta = Model.objects.select_related('reference')
    model_meta = {model.identifier: model for model in model_meta}
    # - prepare rank
    model_ranks = scores[scores['benchmark'] == 'average']
    model_ranks['rank'] = model_ranks['score_ceiled'].rank(method='min', ascending=False).astype(int)
    # - prepare data structures
    ModelRow = namedtuple('ModelRow', field_names=[
        'identifier', 'reference_identifier', 'reference_link', 'rank', 'scores', 'user', 'public'])
    ScoreDisplay = namedtuple('ScoreDiplay', field_names=[
        'benchmark', 'benchmark_depth', 'order', 'score_raw', 'score_ceiled', 'error', 'color'])
    # - convert scores DataFrame into rows
    data = []
    for model_identifier, group in tqdm(scores.groupby('model'), desc='model rows'):
        model_scores = []
        for _, score in group.iterrows():
            benchmark_min, benchmark_max = minmax[score['benchmark']]
            benchmark = benchmark_lookup[score['benchmark']]
            color = representative_color(
                score['score_ceiled'],
                colors=colors_redgreen if benchmark.root_parent != 'engineering'
                else colors_gray,
                alpha_min=benchmark_min, alpha_max=benchmark_max)
            score_ceiled = represent(score['score_ceiled'])
            score_display = ScoreDisplay(benchmark=score['benchmark'], benchmark_depth=benchmark.depth,
                                         score_ceiled=score_ceiled, score_raw=score['score_raw'], error=score['error'],
                                         color=color, order=benchmark.overall_order)
            model_scores.append(score_display)
        model_scores = sorted(model_scores, key=lambda score_display: score_display.order)

        meta = model_meta[model_identifier]
        model_row = ModelRow(
            identifier=model_identifier,
            scores=model_scores, rank=model_ranks[model_ranks['model'] == model_identifier]['rank'].squeeze(),
            reference_identifier=f"{meta.reference.author} et al., {meta.reference.year}" if meta.reference else None,
            reference_link=meta.reference.url if meta.reference else None, user=meta.owner, public=meta.public)
        data.append(model_row)
    data = list(sorted(data, key=lambda model_row: model_row.rank))
    return data


def normalize(value, min_value, max_value):
    # intercept and slope equations are from solving `y = slope * x + intercept`
    # with points [min_value, 10] (10 instead of 0 to not make it completely transparent) and [max_value, 100].
    slope = -.9 / (min_value - max_value)
    intercept = .1 - slope * min_value
    result = slope * value + intercept
    return result


def represent(value):
    if value is None or np.isnan(value):  # None in sqlite, nan in postgres
        return "X"
    return "{:.3f}".format(value).lstrip('0') if value < 1 else "{:.1f}".format(value)


def representative_color(value, alpha_min=None, alpha_max=None, colors=colors_redgreen):
    if value is None or np.isnan(value):  # it seems that depending on database backend, nans are either None or nan
        return f"background-color: {color_None}"
    step = int(100 * value)
    color = colors[step]
    color = tuple(c * 255 for c in color.rgb)
    fallback_color = tuple(round(c) for c in color)
    normalized_value = normalize(value, min_value=alpha_min, max_value=alpha_max) \
        if alpha_min is not None else (100 * value)
    color += (normalized_value,)
    return f"background-color: rgb{fallback_color}; background-color: rgba{color};"


def _build_comparison_data(models):
    data = [dict(ChainMap(*[{'model': model_row.identifier}] +
                           [{f"{score_row.benchmark}-score": score_row.score_ceiled,
                             f"{score_row.benchmark}-error": score_row.error}
                            for score_row in model_row.scores]))
            for model_row in models]
    return data


# Adds python functions so the HTML can do several things
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


# Used to determine whether a column should be visible to begin with
@register.filter
def in_set(hidden_set, key):
    if key in hidden_set:
        return "none"
    else:
        return ""


# Same as above, but used for headers, because their names are different than the cells.
@register.filter
def in_set_hidden(hidden_set, key):
    if hidden_set[key] in hidden_set:
        return "none"
    else:
        return ""


# Allows children to have defining symbols before their names
@register.filter
def get_initial_characters(dictionary, key):
    number_of_characters = -1
    checking_key = key
    while checking_key in dictionary:
        checking_key = dictionary[checking_key]
        number_of_characters += 1

    return "∟" * number_of_characters


# Checks if the parent's name or the part of the parent's name after the first period are in the given dictionary.
@register.filter
def get_parent_item(dictionary, key):
    return_value = dictionary[key]
    return_string = ""
    if not return_value:
        return None
    if "." in return_value:
        for i in return_value.split('.')[1:]:
            if return_string == "":
                return_string += i
            else:
                return_string += "." + i
    else:
        return_string = return_value
    return return_string


@register.filter
def is_public(model):
    if model.public:
        return "checked"
    else:
        return ""
