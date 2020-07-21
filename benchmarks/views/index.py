import logging
import numpy as np
import re
from collections import namedtuple
from colour import Color
from django.shortcuts import render
from django.template.defaulttags import register
from django.views.decorators.cache import cache_page
from tqdm import tqdm

from benchmarks.models import BenchmarkInstance, BenchmarkType, Score

_logger = logging.getLogger(__name__)

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

    # insert mock average benchmark
    benchmarks.insert(0, BenchmarkInstance(
        benchmark_type=BenchmarkType(identifier='average', order=0, parent=None, reference=None),
        version=None, ceiling=None, ceiling_error=None))

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
    # map from a benchmark name to its parent name
    benchmark_parents = {
        benchmark.long_name: benchmark.benchmark_type.parent.identifier if benchmark.benchmark_type.parent else None
        for benchmark in benchmarks}
    # configure benchmark level shown by default
    uniform_parents = set(benchmark_parents.values())  # we're going to use the fact
    # that all benchmark instances currently point to their direct parent

    return {'models': models, 'benchmarks': benchmarks,
            "benchmark_parents": benchmark_parents, "uniform_parents": uniform_parents,
            "uniform_benchmarks": uniform_benchmarks, "not_shown_set": set(), "has_user": False}


def _collect_benchmarks():
    benchmarks = BenchmarkInstance.objects.select_related('benchmark_type__reference').order_by('benchmark_type__order')

    # for benchmark in benchmarks:
    #     if benchmark.named_benchmark.parent not in benchmark_parent_order:
    #         if "." in benchmark.named_benchmark.identifier:
    #             add_name = ""
    #             for i in benchmark.named_benchmark.identifier.split(".")[1:]:
    #                 if add_name == "":
    #                     add_name += i
    #                 else:
    #                     add_name += "." + i
    #             not_shown_set.add(add_name)
    #         else:
    #             not_shown_set.add(benchmark.named_benchmark.identifier)
    #
    # for parent in benchmark_parent_order:
    #     recursive_benchmarks(parent, benchmarks)

    # filter to benchmarks that we have scores for
    score_benchmarks = Score.objects.values_list('benchmark', flat=True).distinct()
    benchmarks = [benchmark for benchmark in benchmarks if benchmark.id in score_benchmarks]
    # add name field for simplicity
    for benchmark in benchmarks:
        benchmark.identifier = benchmark.benchmark_type.identifier
    # sort benchmarks
    benchmarks = list(sorted(benchmarks, key=lambda benchmark: benchmark.benchmark_type.order))
    return benchmarks


def recursive_benchmarks(parent, benchmarks):
    for benchmark in benchmarks:
        if benchmark.benchmark_type.parent == parent:
            if parent not in benchmark_parent_order:
                benchmark_parent_order.append(parent)
            benchmark_order.append(benchmark.benchmark_type.identifier)
            recursive_benchmarks(benchmark.benchmark_type.identifier, benchmarks)


def _root_parent(benchmark_type):
    last_parent = benchmark_type
    while last_parent.parent is not None:
        last_parent = last_parent.parent
    return last_parent


def _collect_models(benchmarks, user=None):
    # pre-compute aggregates
    benchmarks_meta = {}
    for benchmark in benchmarks:
        benchmark_scores = Score.objects.filter(benchmark=benchmark)
        benchmark_scores = [score.score_ceiled if score.score_ceiled is not None else 0 for score in benchmark_scores]
        min_value, max_value = min(benchmark_scores), max(benchmark_scores)
        ceiling = benchmark.ceiling
        benchmarks_meta[benchmark.benchmark_type.identifier] = {
            'ceiling': ceiling, 'min': min_value, 'max': max_value,
            'parent': benchmark.benchmark_type.parent.identifier,
            'root_parent': _root_parent(benchmark.benchmark_type).identifier}

    # arrange scores
    scores = Score.objects.select_related('model__reference').select_related('benchmark__benchmark_type').all()
    ModelRow = namedtuple('ModelRow', field_names=[
        'identifier', 'reference_identifier', 'reference_link', 'rank', 'scores', 'user', 'public'])
    ScoreDisplay = namedtuple('ScoreDiplay', field_names=[
        'benchmark', 'score_raw', 'score_ceiled', 'color'])

    data = {}
    for score in tqdm(scores, desc='scores'):
        if score.benchmark.benchmark_type.identifier not in benchmarks_meta:
            _logger.warning(f"Benchmark {score.benchmark.benchmark_type.identifier} from score {score} "
                            f"not found in benchmarks_meta {benchmarks_meta}")
            continue

        # if model information is not present yet, fill it
        if score.model.identifier not in data:
            index = re.search(r'(--)', score.model.identifier)
            model = score.model
            # meta = _order_model_meta(meta, identifier_fnc=lambda meta_row: [
            #     prefix for prefix in benchmark_parent_order if
            #     isinstance(prefix, str) and meta_row.key.startswith(prefix)][0])
            reference_identifier = f"{model.reference.author} et al., {model.reference.year}"
            data[score.model.identifier] = ModelRow(identifier=score.model.identifier,
                                                    reference_identifier=reference_identifier,
                                                    reference_link=model.reference.url,
                                                    rank=None,
                                                    scores={},
                                                    user=model.owner,
                                                    public=model.public
                                                    )

        benchmark_meta = benchmarks_meta[score.benchmark.benchmark_type.identifier]
        color = representative_color(
            score.score_ceiled,
            colors=colors_redgreen if benchmark_meta['root_parent'] != 'engineering' else colors_gray,
            alpha_min=benchmark_meta['min'],
            alpha_max=benchmark_meta['max'] if benchmark_meta['root_parent'] != 'engineering'
            else 2.5 * benchmark_meta['max'])  # this is a hack to make the gray less visually dominant on the page
        score_ceiled, score_raw = represent(score.score_ceiled), represent(score.score_raw)
        score_display = ScoreDisplay(benchmark=score.benchmark.benchmark_type.identifier,
                                     score_ceiled=score_ceiled, score_raw=score_raw, color=color)
        data[score.model.identifier].scores[score.benchmark.benchmark_type.identifier] = score_display

    # sort score benchmarks
    no_score = {}
    for benchmark in benchmarks:
        benchmark_identifier = benchmark.benchmark_type.identifier
        meta = benchmarks_meta[benchmark_identifier]
        no_score[benchmark_identifier] = ScoreDisplay(
            benchmark=benchmark_identifier, score_ceiled="", score_raw="",
            color=representative_color(None, alpha_min=meta['min'], alpha_max=meta['max']))
    data = [model_row._replace(scores=[
        model_row.scores[benchmark.benchmark_type.identifier]
        if benchmark.benchmark_type.identifier in model_row.scores else no_score[benchmark.benchmark_type.identifier]
        for benchmark in benchmarks])
        for model_row in tqdm(data.values(), desc='sort benchmarks')]

    # Remove all non-public models from the sorting and ranking. Allow users to see their own models in the ranking.
    data = [row for row in data
            # if we are not in a user profile, only show rows that are public
            if (user is None and row.public)
            # if we are in a user profile, show all rows that this user owns (regardless of public/private)
            or (user is not None and row.user == user)]

    # compute average scores for models, infer rank by finding index in sorted average scores
    average_scores = {}
    for model_row in data:
        scores = []
        for score in model_row.scores:
            if benchmarks_meta[score.benchmark]['root_parent'] == 'engineering':
                continue
            scores.append(float(score.score_ceiled) if score.score_ceiled != 'X' else 0)
        average_scores[model_row.identifier] = np.mean(scores)
    # prepend average score to model scores
    average_min, average_max = min(list(average_scores.values())), max(list(average_scores.values()))
    for model_row in data:
        average_score = average_scores[model_row.identifier]
        color = representative_color(average_score, colors=colors_redgreen,
                                     alpha_min=average_min, alpha_max=average_max)
        score_ceiled = represent(average_score)
        score_display = ScoreDisplay(benchmark="average", score_ceiled=score_ceiled, score_raw=None, color=color)
        model_row.scores.insert(0, score_display)
    all_scores = list(sorted(average_scores.values(), reverse=True))

    ranks = {model: all_scores.index(score) + 1 for model, score in average_scores.items()}
    data = [model_row._replace(rank=ranks[model_row.identifier]) for model_row in tqdm(data, desc='ranking')]
    return data


# Split benchmark ordering and row ordering to avoid having to redo the sorting function. Necessary because
# the benchmarks are now explicitly ordered by name now instead of by parent.
def _order_benchmarks(values, identifier_fnc):
    return [value for parent_index, value in sorted(zip(
        [benchmark_order.index(identifier_fnc(value)) for value in values],
        values))]


# Order model meta on layer assignments the same way that benchmarks are ordered.
def _order_model_meta(values, identifier_fnc):
    return [value for parent_index, value in sorted(zip(
        [benchmark_parent_order.index(identifier_fnc(value)) for value in values],
        values))]


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


def setup_parent_dictionary(dictionary, benchmark):
    dictionary[benchmark.identifier] = benchmark.parent


# At some point, the Score Cells have their name changed to remove the name before the
# actual test, so a dictionary is necessary to provide a uniform name for both cases.
def setup_uniform_dictionary(dictionary, score_row):
    if '.' in score_row.benchmark:
        split_name = score_row.benchmark.split('.')
        actual_test = ""
        for i in range(1, len(split_name)):
            if i == 1:
                actual_test = split_name[i]
            else:
                actual_test += "." + split_name[i]
        dictionary[score_row.benchmark] = actual_test
    else:
        dictionary[score_row.benchmark] = score_row.benchmark


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


# Used to assign columns to a certain css profile to alter the perceived size. (Children look smaller than parents)
@register.filter
def get_depth_number(dictionary, key):
    number_of_characters = -1
    checking_key = key
    while checking_key in dictionary:
        checking_key = dictionary[checking_key]
        number_of_characters += 1

    # CSS did not like numbers for classNames
    ints_to_strings = {
        0: "zero",
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven"
    }
    return ints_to_strings[number_of_characters]


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
