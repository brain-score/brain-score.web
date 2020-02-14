import numpy as np
import re
from collections import namedtuple
from django.template.defaulttags import register
from colour import Color
from django.shortcuts import render
from tqdm import tqdm

from benchmarks.models import Score, Benchmark, ModelReference, ModelMeta

colors = list(Color('red').range_to(Color('green'), 101))
# scale colors: highlight differences at the top-end of the spectrum more than at the lower end
a, b = 0.2270617, 1.321928  # fit to (0, 0), (60, 50), (100, 100)
colors = [colors[int(a * np.power(i, b))] for i in range(len(colors))]
color_suffix = '_color'
color_None = '#e0e1e2'
benchmark_parent_order = [None, 'V1', 'V2', 'V4', 'IT', 'IT-temporal', 'behavior', 'ImageNet']
benchmark_order = []
not_shown_set = set()

def view(request):
    benchmarks = _collect_benchmarks()
    models = _collect_models(benchmarks)
    for benchmark in benchmarks:  # remove lab for more compactness
        match = re.match(r'[^\.]+\.(.+)', benchmark.name)
        if match:
            benchmark.name = match.group(1)
        benchmark.ceiling = represent(benchmark.ceiling)

    # There was previously no way to find the parent of a benchmark from a model score because it did not save that as a value.
    #   Now, using get_item with benchmark_parents allows the HTML to know the parent of that benchmark.
    benchmark_parents = {}

    # The benchmark names in the score cells were altered from the original, so this dictionary allows the new values to map to the originals.
    #   Used for some checks
    uniform_benchmarks = {}

    for i in benchmarks:
        setup_parent_dictionary(benchmark_parents, i)

    for i in models:
        for score_row in i.scores:
            setup_uniform_dictionary(uniform_benchmarks, score_row)

    for i in uniform_benchmarks:
        benchmark_parents[i] = benchmark_parents[uniform_benchmarks[i]]

    uniform_parents = set()
    for i in benchmark_parent_order:
        if i in uniform_benchmarks:
            uniform_parents.add(uniform_benchmarks[i])
        uniform_parents.add(i)

    context = {'models': models, 'benchmarks': benchmarks, "benchmark_parents": benchmark_parents,
               "uniform_parents": uniform_parents, "uniform_benchmarks": uniform_benchmarks,
               "not_shown_set": not_shown_set}
    return render(request, 'benchmarks/index.html', context)


def _collect_benchmarks():
    benchmarks = sorted(Benchmark.objects.all(), key=lambda benchmark: benchmark.name)

    for benchmark in benchmarks:
        if benchmark.parent not in benchmark_parent_order:
            if "." in benchmark.name:
                add_name = ""
                for i in benchmark.name.split(".")[1:]:
                    if add_name == "":
                        add_name += i
                    else:
                        add_name += "." + i
                not_shown_set.add(add_name)
            else:
                not_shown_set.add(benchmark.name)

    for parent in benchmark_parent_order:
        recursive_benchmarks(parent, benchmarks)
    # filter to benchmarks that we have scores for
    score_benchmarks = Score.objects.values_list('benchmark', flat=True).distinct()
    benchmarks = [benchmark for benchmark in benchmarks if benchmark.name in score_benchmarks]
    # sort benchmarks
    benchmarks = _order_benchmarks(benchmarks, identifier_fnc=lambda benchmark: benchmark.name)
    return benchmarks


def recursive_benchmarks(parent, benchmarks):
    for benchmark in benchmarks:
        if benchmark.parent == parent:
            if parent not in benchmark_parent_order:
                benchmark_parent_order.append(parent)
            benchmark_order.append(benchmark.name)
            recursive_benchmarks(benchmark.name, benchmarks)


def _collect_models(benchmarks):
    # pre-compute aggregates
    benchmarks_meta = {}
    for benchmark in [benchmark.name for benchmark in benchmarks]:
        benchmark_scores = Score.objects.filter(benchmark=benchmark)
        benchmark_scores = [score.score_ceiled if score.score_ceiled is not None else 0 for score in benchmark_scores]
        min_value, max_value = min(benchmark_scores), max(benchmark_scores)
        ceiling = Benchmark.objects.filter(name=benchmark)[0].ceiling
        benchmarks_meta[benchmark] = {'ceiling': ceiling, 'min': min_value, 'max': max_value}

    # arrange scores
    scores = Score.objects.all().select_related()
    ModelRow = namedtuple('ModelRow', field_names=[
        'name', 'reference_identifier', 'reference_link', 'meta', 'rank', 'scores'])
    ScoreDisplay = namedtuple('ScoreDiplay', field_names=[
        'benchmark', 'score_raw', 'score_ceiled', 'color', 'layer'])

    data = {}
    for score in tqdm(scores, desc='scores'):
        if score.benchmark not in benchmarks_meta:
            continue

        # if model information is not present yet, fill it
        if score.model not in data:
            index = re.search(r'(--)', score.model)
            model_base_identifier = score.model[:index.start()] if index else score.model
            reference = ModelReference.objects.filter(model=model_base_identifier)
            reference = reference[0] if len(reference) > 0 else None
            meta = ModelMeta.objects.filter(model=model_base_identifier)
            meta = _order_models(meta, identifier_fnc=lambda meta_row: [
                prefix for prefix in benchmark_parent_order
                if isinstance(prefix, str) and meta_row.key.startswith(prefix)][0])
            meta = '\n'.join([f"{meta_row.key}: {meta_row.value}" for meta_row in meta])
            data[score.model] = ModelRow(name=score.model,
                                         reference_identifier=reference.short_reference if reference else None,
                                         reference_link=reference.link if reference else None,
                                         meta=meta,
                                         rank=None,
                                         scores={})

        benchmark_meta = benchmarks_meta[score.benchmark]
        color = representative_color(score.score_ceiled,
                                     alpha_min=benchmark_meta['min'], alpha_max=benchmark_meta['max'])
        score_ceiled, score_raw = represent(score.score_ceiled), represent(score.score_raw)
        score_display = ScoreDisplay(benchmark=score.benchmark, score_ceiled=score_ceiled, score_raw=score_raw,
                                     color=color, layer=score.layer)
        data[score.model].scores[score.benchmark] = score_display

    # sort score benchmarks
    no_score = {}
    for benchmark in benchmarks:
        meta = benchmarks_meta[benchmark.name]
        no_score[benchmark.name] = ScoreDisplay(
            benchmark=benchmark.name, score_ceiled="", score_raw="",
            color=representative_color(None, alpha_min=meta['min'], alpha_max=meta['max']),
            layer="not yet run")
    data = [model_row._replace(scores=[
        model_row.scores[benchmark.name] if benchmark.name in model_row.scores else no_score[benchmark.name]
        for benchmark in benchmarks])
        for model_row in tqdm(data.values(), desc='sort benchmarks')]

    # infer rank
    average_scores = {model_row.name: [score.score_ceiled for score in model_row.scores
                                       if score.benchmark == 'average'][0]
                      for model_row in data}
    all_scores = list(sorted(average_scores.values(), reverse=True))
    ranks = {model: all_scores.index(score) + 1 for model, score in average_scores.items()}
    data = [model_row._replace(rank=ranks[model_row.name]) for model_row in tqdm(data, desc='ranking')]
    return data


# Split benchmark ordering and row ordering to avoid having to redo the sorting function. Necessary because
# the benchmarks are now explicitly ordered by name now instead of by parent.
def _order_benchmarks(values, identifier_fnc):
    return [value for parent_index, value in sorted(zip(
        [benchmark_order.index(identifier_fnc(value)) for value in values],
        values))]


# Model ordering is unchanged.
def _order_models(values, identifier_fnc):
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
    if value is None or np.isnan(value):
        return "X"
    return "{:.3f}".format(value).lstrip('0') if value < 1 else "{:.1f}".format(value)


def setup_parent_dictionary(dictionary, benchmark):
    dictionary[benchmark.name] = benchmark.parent


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


def representative_color(value, alpha_min=None, alpha_max=None):
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
