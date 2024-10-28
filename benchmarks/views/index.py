import json
import logging
import re
import datetime
from math import isnan
from collections import ChainMap
from collections import namedtuple
from collections import OrderedDict

import itertools
import numpy as np
import pandas as pd
from colour import Color
from django.shortcuts import render
from django.template.defaulttags import register
from django.views.decorators.cache import cache_page
from tqdm import tqdm

from benchmarks.models import BenchmarkType, BenchmarkInstance, Model, Score, generic_repr

_logger = logging.getLogger(__name__)

BASE_DEPTH = 1
ENGINEERING_ROOT = 'engineering'

colors_redgreen = list(Color('red').range_to(Color('#1BA74D'), 101))
colors_gray = list(Color('#f2f2f2').range_to(Color('#404040'), 101))
# scale colors: highlight differences at the top-end of the spectrum more than at the lower end
a, b = 0.2270617, 1.321928  # fit to (0, 0), (60, 50), (100, 100)
colors_redgreen = [colors_redgreen[int(a * np.power(i, b))] for i in range(len(colors_redgreen))]
colors_gray = [colors_gray[int(a * np.power(i, b))] for i in range(len(colors_gray))]
color_suffix = '_color'
color_None = '#e0e1e2'


@cache_page(24 * 60 * 60)
def view(request, domain: str):
    context = get_context(domain=domain)
    return render(request, 'benchmarks/leaderboard/leaderboard.html', context)


def get_context(user=None, domain: str = "vision", benchmark_filter=None, model_filter=None, show_public=False):
    benchmarks = _collect_benchmarks(domain, user_page=True if user is not None else False,
                                     benchmark_filter=benchmark_filter)
    model_rows = _collect_models(domain, benchmarks, show_public, user, score_filter=model_filter)

    # calculate lightweight, downloadable version of model scores
    csv_data = _build_scores_dataframe(benchmarks, model_rows)

    # to save vertical space, we strip the lab name in front of benchmarks.
    uniform_benchmarks = {}  # keeps the original benchmark name
    for benchmark in benchmarks:  # remove lab for more compactness
        uniform_benchmarks[benchmark.benchmark_type.identifier] = benchmark.identifier
        benchmark.ceiling = represent(benchmark.ceiling)
        benchmark.identifier = f'{benchmark.identifier}_v{benchmark.version}'
    # map from a benchmark to its parent, the benchmark id is <benchmarkname>_v<version>,
    # parent have always version 0 (only to match the pattern).
    # We set here parent nodes as value -> abstract nodes so they must have version 0.
    benchmark_parents = {
        benchmark.identifier: f'{benchmark.benchmark_type.parent.identifier}_v0'
        if benchmark.benchmark_type.parent else None
        for benchmark in benchmarks}
    # configure benchmark level shown by default
    # we're going to use the fact that all benchmark instances currently point to their direct parent
    uniform_parents = set(benchmark_parents.values())
    not_shown_set = {benchmark.identifier for benchmark in benchmarks
                     if benchmark.depth > BASE_DEPTH or
                     # show engineering benchmarks collapsed, but still show root
                     (ENGINEERING_ROOT not in benchmark.identifier and ENGINEERING_ROOT in benchmark.root_parent)}

    # data for javascript comparison script
    public_models = [model_row for model_row in model_rows if model_row.public]
    comparison_data = _build_comparison_data(public_models)

    # benchmarks to select from for resubmission in user profile
    submittable_benchmarks = None
    if user is not None:
        submittable_benchmarks = _collect_submittable_benchmarks(benchmarks=benchmarks, user=user)

    # need to hardcode this
    if domain is "vision":
        citation_domain_url = 'https://www.biorxiv.org/content/early/2018/09/05/407007'
        citation_domain_title = "Brain-Score: Which Artificial Neural Network for Object Recognition is most " \
                                "Brain-Like? "
        citation_domain_bibtex = "@article{SchrimpfKubilius2018BrainScore,\n\t\t\t\t" \
                                  "title={Brain-Score: Which Artificial Neural Network for Object Recognition is most Brain-Like?},\n\t\t\t\t" \
                                  "author={Martin Schrimpf and Jonas Kubilius and Ha Hong and Najib J. Majaj and " \
                                  "Rishi Rajalingham and Elias B. Issa and Kohitij Kar and Pouya Bashivan and Jonathan " \
                                  "Prescott-Roy and Franziska Geiger and Kailyn Schmidt and Daniel L. K. Yamins and James J. DiCarlo},\n\t\t\t\t" \
                                  "journal={bioRxiv preprint},\n\t\t\t\t" \
                                  "year={2018},\n\t\t\t\t" \
                                  "url={https://www.biorxiv.org/content/10.1101/407007v2}\n\t\t\t}"
    elif domain is "language":
        citation_domain_url = 'https://www.pnas.org/content/118/45/e2105646118'
        citation_domain_title = "The neural architecture of language: Integrative modeling converges on predictive processing"
        citation_domain_bibtex = "@article{schrimpf2021neural,\n\t\t\t\t" \
                                  "title={The neural architecture of language: Integrative modeling converges on predictive processing},\n\t\t\t\t" \
                                  "author={Schrimpf, Martin and Blank, Idan Asher and Tuckute, Greta and Kauf, Carina " \
                                  "and Hosseini, Eghbal A and Kanwisher, Nancy and Tenenbaum, Joshua B and Fedorenko, Evelina},\n\t\t\t\t" \
                                  "journal={Proceedings of the National Academy of Sciences},\n\t\t\t\t" \
                                  "volume={118},\n\t\t\t\t" \
                                  "number={45},\n\t\t\t\t" \
                                  "pages={e2105646118},\n\t\t\t\t" \
                                  "year={2021},\n\t\t\t\t" \
                                  "publisher={National Acad Sciences}\n\t\t\t" \
                                  "}"
    else:
        citation_domain_url = ''
        citation_domain_title = ''
        citation_domain_bibtex = ''

    benchmark_names = [b.identifier for b in list(filter(lambda b: b.number_of_all_children == 0, benchmarks))]

    return {'domain': domain, 'models': model_rows, 'benchmarks': benchmarks, 'benchmark_names': benchmark_names,
            'submittable_benchmarks': submittable_benchmarks,
            "benchmark_parents": benchmark_parents, "uniform_parents": uniform_parents,
            "not_shown_set": not_shown_set, "BASE_DEPTH": BASE_DEPTH, "has_user": False,
            "comparison_data": json.dumps(comparison_data),
            'citation_general_url': 'https://www.cell.com/neuron/fulltext/S0896-6273(20)30605-X',
            'citation_general_title': 'Integrative Benchmarking to Advance Neurally Mechanistic Models of Human Intelligence',
            'citation_general_bibtex': '@article{Schrimpf2020integrative,\n\t\t\t\t'
                                       'title={Integrative Benchmarking to Advance '
                                       'Neurally Mechanistic Models of Human Intelligence},\n\t\t\t\t'
                                       'author={Schrimpf, Martin and Kubilius, Jonas and Lee, Michael J and Murty, '
                                       'N Apurva Ratan and Ajemian, Robert and DiCarlo, James J},\n\t\t\t\t'
                                       'journal={Neuron},\n\t\t\t\t'
                                       'year={2020},\n\t\t\t\t'
                                       'url={https://www.cell.com/neuron/fulltext/S0896-6273(20)30605-X}\n\t\t\t}',
            'citation_domain_url': citation_domain_url,
            'citation_domain_title': citation_domain_title,
            'citation_domain_bibtex': citation_domain_bibtex,
            'csv_downloadable': csv_data
            }


def _build_scores_dataframe(benchmarks, model_rows):
    csv_scores = []
    benchmark_names = [benchmark.identifier for benchmark in benchmarks]
    for model in model_rows:
        csv_dict = {"model_name": model.name, "scores": {}}
        for score in model.scores:
            benchmark_identifier = score.benchmark.identifier
            if benchmark_identifier in benchmark_names:
                csv_dict["scores"][benchmark_identifier] = score.score_ceiled
        csv_scores.append(csv_dict)
    csv_df = pd.DataFrame([{**{"model_name": model["model_name"]}, **model["scores"]} for model in csv_scores])

    if not csv_df.empty:  # check if the DataFrame is empty
        csv_df.set_index('model_name', inplace=True)
        csv_data = csv_df.to_csv(index=True)
    else:
        csv_data = "No models submitted yet."

    return csv_data


def _collect_benchmarks(domain: str, user_page: bool = False, benchmark_filter=None):
    # build tree structure of parent relationships
    benchmark_types = BenchmarkType.objects.select_related('reference')
    if not user_page:  # on public overview, only show visible benchmarks
        benchmark_types = benchmark_types.filter(visible=True)
    root_benchmarks = benchmark_types.filter(identifier__in=[f"average_{domain}", f"engineering_{domain}"])
    if benchmark_filter:
        root_benchmarks = benchmark_filter(root_benchmarks)
    root_benchmarks = root_benchmarks.order_by('order')
    root_trees = []
    for root_benchmark in root_benchmarks:
        root_tree = Tree(value=root_benchmark, depth=0)
        root_trees.append(root_tree)
        traverse_todo = [root_tree]
        # traverse the tree, filling in children in the process
        while traverse_todo:
            node = traverse_todo.pop()
            children = benchmark_types.filter(parent=node.value)
            if benchmark_filter:
                children = benchmark_filter(children)
            children = children.order_by('order')
            children = [Tree(value=child, parent=node, depth=node.depth + 1) for child in children]
            node.children = children
            traverse_todo += children

    def count_all_children(tree: Tree):
        """ compute total number of children per tree """
        count = 0
        for child in tree.children:
            count += count_all_children(child)
        tree.number_of_all_children = count
        if len(tree.children) == 0:
            count += 1  # count as instance if no further children
        return count

    overall_order = 0

    def set_instance_meta(instance, node, tree):
        """ sets meta attributes of a benchmark instance according to its tree node """
        instance.parent = node.parent.value if node.parent else None
        instance.root_parent = tree.value.identifier
        instance.depth = node.depth
        instance.number_of_all_children = node.number_of_all_children
        nonlocal overall_order
        instance.overall_order = overall_order
        overall_order += 1

    # gather actual benchmark instances and insert dummy instances for parents
    benchmarks = []
    for tree in root_trees:
        count_all_children(tree)
        # traverse the tree depth-first to go from highest parent to lowest child, corresponding to the website display
        traverse_todo = [tree]
        while traverse_todo:
            node = traverse_todo.pop(0)  # pop first item --> recent child hierarchy with lowest order
            if node.children:  # if abstract benchmark hierarchy, insert dummy instance
                instance = BenchmarkInstance(benchmark_type=node.value, version=None, ceiling=None, ceiling_error=None)
                instance.children = [child.value.identifier for child in node.children]
                traverse_todo = node.children + traverse_todo
                instance.version = int(0)
                set_instance_meta(instance, node, tree)
                benchmarks.append(instance)
            else:  # no children --> it's a specific instance
                if user_page:
                    instances = BenchmarkInstance.objects.select_related('benchmark_type') \
                        .filter(benchmark_type=node.value)
                    for instance in instances:
                        set_instance_meta(instance, node, tree)
                        benchmarks.append(instance)
                else:
                    instance = BenchmarkInstance.objects \
                        .select_related('benchmark_type', 'benchmark_type__reference', 'meta') \
                        .filter(benchmark_type=node.value).latest('version')  # latest instance for this type
                    set_instance_meta(instance, node, tree)
                    benchmarks.append(instance)
    # add shortcut to identifier
    for benchmark in benchmarks:
        benchmark.identifier = benchmark.benchmark_type.identifier
        shortname = _get_benchmark_shortname(benchmark.benchmark_type.identifier)
        benchmark.short_name = shortname
    return benchmarks


def _collect_submittable_benchmarks(benchmarks, user):
    """
    gather benchmarks that:
    - any of a user's models have been evaluated on, if user is not a superuser
    - all benchmarks, if user is a superuser
    """

    benchmark_types = {benchmark.identifier: benchmark.benchmark_type_id
                       for benchmark in benchmarks if not hasattr(benchmark, 'children')}
    # the above dictionary creation will already deal with duplicates from benchmarks with multiple versions
    if user.is_superuser:  # superusers can resubmit on all available benchmarks
        return benchmark_types

    previously_evaluated_benchmarks = [benchmark_type_id
                                       for benchmark_type_id in Score.objects
                                       .select_related('benchmark')
                                       .filter(model__owner=user)
                                       .distinct('benchmark__benchmark_type_id')
                                       .values_list('benchmark__benchmark_type_id', flat=True)]
    benchmark_selection = {identifier: benchmark_type_id for identifier, benchmark_type_id in benchmark_types.items()
                           if benchmark_type_id in previously_evaluated_benchmarks}
    return benchmark_selection


def _collect_models(domain: str, benchmarks, show_public, user=None, score_filter=None):
    """
    :param user: The user whose profile we are currently on, if any
    """
    # Remove all non-public model scores, but allow users to see their own models in the table.
    if user is None:  # if we are not in a user profile, only show rows that are public
        if not show_public:
            # show public only set for competition context. See competition2022.py get_context
            user_selection = dict(model__public=True)
        else:
            # also only show non-null, i.e. non-erroneous scores. Successful zero scores would be NaN
            user_selection = dict(score_raw__isnull=False)
    elif user.is_superuser:
        user_selection = dict()
    else:
        # if we are in a user profile, show all rows that this user owns (regardless of public/private)
        # also only show non-null, i.e. non-erroneous scores. Successful zero scores would be NaN
        user_selection = dict(model__owner=user, score_raw__isnull=False)

    # Database stores scores for actual instances
    benchmark_todos = [benchmark for benchmark in benchmarks if not hasattr(benchmark, 'children')]
    benchmark_lookup = {f'{benchmark.identifier}_v{benchmark.version}': benchmark for benchmark in benchmarks}
    all_scores = Score.objects.filter(**user_selection,
                                      **(score_filter if score_filter else {}),
                                      benchmark__in=benchmark_todos)
    all_scores = all_scores.select_related('model')

    # iteratively collect scores for all benchmarks. We start with the actual instances, storing their respective
    # parents to traverse up the hierarchy which we iteratively visit until empty.
    scores = None
    while benchmark_todos:
        benchmark = benchmark_todos.pop(0)
        _logger.debug(f"Processing scores for benchmark {benchmark}")
        if not hasattr(benchmark, 'children'):  # actual instance without children, we can just retrieve the scores
            benchmark_scores = all_scores.filter(benchmark=benchmark)
            if len(benchmark_scores) > 0:
                rows = []
                for score in benchmark_scores:
                    # many engineering benchmarks (e.g. ImageNet) don't have a notion of a primate ceiling.
                    # instead, we display the raw score if there is no ceiled score.
                    benchmark_id = f'{benchmark.identifier}_v{benchmark.version}'
                    if ENGINEERING_ROOT not in benchmark_lookup[benchmark_id].root_parent \
                            or score.score_ceiled is not None:
                        score_ceiled = score.score_ceiled
                    else:
                        score_ceiled = score.score_raw
                    rows.append({'benchmark': benchmark.identifier, 'benchmark_version': benchmark.version,
                                 'overall_order': benchmark.overall_order,
                                 'model': score.model.id,
                                 'score_ceiled': score_ceiled, 'score_raw': score.score_raw, 'error': score.error,
                                 'comment': score.comment, 'is_complete': 1})
                benchmark_scores = pd.DataFrame(rows)
                scores = benchmark_scores if scores is None else pd.concat((scores, benchmark_scores))
        else:  # hierarchy level, we need to aggregate the scores in the hierarchy below
            if scores is not None:
                children_scores = scores[scores['benchmark'].isin(benchmark.children)]
                # guard against multiple scores for one combination of (benchmark, version, model)
                children_scores = children_scores.drop_duplicates()
                # fill in models that don't have a score
                combinatorial_model_benchmark_set = set(itertools.product(
                    set(children_scores['model']), benchmark.children))  # the full combination of models x benchmarks
                actual_model_benchmark_set = set(zip(children_scores['model'], children_scores['benchmark']))
                missing_scores = combinatorial_model_benchmark_set - actual_model_benchmark_set
                if len(missing_scores) > 0:
                    missing_scores = pd.DataFrame(missing_scores, columns=['model', 'benchmark'])
                    missing_scores['score_raw'] = missing_scores['score_ceiled'] = np.nan
                    missing_scores['is_complete'] = 0
                    children_scores = pd.concat((children_scores, missing_scores))
                # compute average of children scores -- treat missing scores as 0 for averaging
                benchmark_scores = children_scores.fillna(0).groupby('model').mean(numeric_only=True)
                # for children scores that are all nan, set average to nan as well (rather than 0 from `fillna`)
                if len(benchmark_scores) > 0:
                    all_children_nan = children_scores.groupby('model').apply(
                        lambda group: all(group['score_raw'].isna()))
                    for value_column in ['score_ceiled', 'score_raw', 'error']:
                        benchmark_scores[value_column][all_children_nan] = np.nan
                # restore model index
                benchmark_scores = benchmark_scores.reset_index()
                # add meta
                benchmark_scores['benchmark'] = benchmark.identifier
                benchmark_scores['benchmark_version'] = 0
                benchmark_scores['comment'] = None
                scores = benchmark_scores if scores is None else pd.concat((scores, benchmark_scores))
        if benchmark.parent:
            parent = [parent_candidate for parent_candidate in benchmarks
                      if parent_candidate.identifier == benchmark.parent.identifier]
            assert len(parent) == 1
            parent = parent[0]
            if parent in benchmark_todos:
                continue  # already in list
            # Process benchmarks deeper in the hierarchy first, i.e. process benchmarks with more parents before
            # benchmarks with fewer parents. This is to avoid cases such as the following:
            # ```
            #   V1
            #     - FreemanZiemba2013.V1-pls
            #     - V1-response_magnitude
            #       - Marques2020_Ringach2002-max_dc
            # ```
            # In this case, if the FreemanZiemba2013.V1-pls benchmark is processed first, it will add V1 to the todos.
            # V1 will thus be processed next, at which point the scores for V1-response_magnitude are however not
            # processed yet. Thus, we want to work our way from the bottom up.
            benchmark_todos.append(parent)
            benchmark_todos = list(sorted(benchmark_todos, key=lambda benchmark: benchmark.depth, reverse=True))
    # setup benchmark metadata for all scores
    if scores is None:
        return []
    minmax = {}
    for criteria, group in scores.groupby(['benchmark', 'benchmark_version']):
        benchmark_id = f'{criteria[0]}_v{int(criteria[1])}'
        bench_minmax = (
            np.nanmin(group['score_ceiled'].fillna(value=np.nan)),
            np.nanmax(group['score_ceiled'].fillna(value=np.nan))
            # this is an ugly hack to make the gray less visually dominant on the page
            * (2.5 if ENGINEERING_ROOT in benchmark_lookup[benchmark_id].root_parent else 1))
        if bench_minmax[0] == bench_minmax[1]:
            bench_minmax = (0, 1)
        minmax[benchmark_id] = bench_minmax

    # arrange into per-model scores
    # - prepare model meta
    model_meta = Model.objects.select_related('reference', 'owner', 'submission')
    model_meta = {model.id: model for model in model_meta}
    # - prepare rank
    model_ranks = scores[scores['benchmark'] == f'average_{domain}']
    model_ranks['rank'] = model_ranks['score_ceiled'].fillna(0).rank(method='min', ascending=False).astype(int)
    # - prepare data structures
    ModelRow = namedtuple('ModelRow', field_names=[
        'id', 'name',
        'reference_identifier', 'reference_link',
        'user', 'public', 'competition', 'domain',
        'rank', 'scores',
        'build_status', 'submitter', 'submission_id', 'jenkins_id', 'timestamp'])
    ScoreDisplay = namedtuple('ScoreDisplay', field_names=[
        'benchmark', 'versioned_benchmark_identifier',
        'score_raw', 'score_ceiled', 'error', 'color', 'comment', 'is_complete'])
    # - prepare "no score" objects for when a model-benchmark score is missing
    no_score = {}
    for benchmark in benchmarks:
        versioned_benchmark_identifier = f'{benchmark.identifier}_v{benchmark.version}'
        if versioned_benchmark_identifier in minmax:
            benchmark_min, benchmark_max = minmax[versioned_benchmark_identifier]
            no_score[versioned_benchmark_identifier] = ScoreDisplay(
                benchmark=benchmark, versioned_benchmark_identifier=versioned_benchmark_identifier,
                score_ceiled="", score_raw="", error="",
                color=representative_color(None, min_value=benchmark_min, max_value=benchmark_max),
                comment="", is_complete=False)
        else:
            no_score[versioned_benchmark_identifier] = ScoreDisplay(
                benchmark=benchmark, versioned_benchmark_identifier=versioned_benchmark_identifier,
                score_ceiled="", score_raw="", error="",
                color=representative_color(None, min_value=0, max_value=1),
                comment="", is_complete=False)
    # - convert scores DataFrame into rows
    data = []
    for model_id, group in tqdm(scores.groupby('model'), desc='model rows'):
        model_scores = {}
        # fill in computed scores
        for score_ceiled, score_raw, error, benchmark, version, comment, is_complete in zip(
                group['score_ceiled'], group['score_raw'], group['error'],
                group['benchmark'], group['benchmark_version'],
                group['comment'], group['is_complete']):
            versioned_benchmark_identifier = f'{benchmark}_v{version}'
            benchmark_min, benchmark_max = minmax[versioned_benchmark_identifier]
            benchmark = benchmark_lookup[versioned_benchmark_identifier]
            color = representative_color(
                score_ceiled,
                colors=colors_redgreen if ENGINEERING_ROOT not in benchmark.root_parent
                else colors_gray,
                min_value=benchmark_min, max_value=benchmark_max)
            score_ceiled = represent(score_ceiled)
            score_display = ScoreDisplay(benchmark=benchmark,
                                         versioned_benchmark_identifier=versioned_benchmark_identifier,
                                         score_ceiled=score_ceiled, score_raw=score_raw, error=error,
                                         color=color, comment=comment, is_complete=is_complete)
            model_scores[versioned_benchmark_identifier] = score_display
        # fill in missing scores
        model_scores = [model_scores[f'{benchmark.identifier}_v{benchmark.version}']
                        if f'{benchmark.identifier}_v{benchmark.version}' in model_scores
                        else no_score[f'{benchmark.identifier}_v{benchmark.version}']
                        for benchmark in benchmarks]

        # put everything together, adding model meta
        meta = model_meta[model_id]
        if model_id in model_ranks['model'].values:
            rank = model_ranks[model_ranks['model'] == model_id]['rank'].squeeze()
        else:  # if a model does not have an average score, it will not be included in the rank
            _logger.warning(f"Model {model_id} not found in model_ranks")
            rank = max(model_ranks['rank']) + 1
        reference_identifier = f"{meta.reference.author} et al., {meta.reference.year}" if meta.reference else None

        # model
        competition = meta.competition
        domain = meta.domain

        # submission
        submitter = meta.submission.submitter
        submission_id = meta.submission.id
        timestamp = meta.submission.timestamp
        build_status = meta.submission.status
        jenkins_id = meta.submission.jenkins_id

        model_row = ModelRow(
            id=meta.id,
            name=meta.name,
            reference_identifier=reference_identifier, reference_link=meta.reference.url if meta.reference else None,
            user=meta.owner, public=meta.public, competition=competition, domain=domain,
            scores=model_scores, rank=rank, build_status=build_status,
            submitter=submitter, submission_id=submission_id, jenkins_id=jenkins_id, timestamp=timestamp
        )
        data.append(model_row)
    data = list(sorted(data, key=lambda model_row: model_row.rank))

    return data


def _get_benchmark_shortname(benchmark_type_identifier: str):
    """
    Removes the lab identifier from a benchmark name.
    e.g. "dicarlo.MajajHong2015.V4-pls --> MajajHong2015.V4-pls"
    
    Assumes that lab identifiers do not contain capital letters.
    e.g. "MajajHong2015.V4-pls --> MajajHong2015.V4-pls"
    """
    # 
    # E.g., 
    # 
    match = re.match(r'[^A-Z]+\.(.+)', benchmark_type_identifier)
    if match:
        return match.group(1)
    else:
        return benchmark_type_identifier


class Tree:
    def __init__(self, value, depth, parent=None, children=None):
        self.value = value
        self.depth = depth
        self.parent = parent
        self.children = children

    def __repr__(self):
        return generic_repr(self)


def normalize_value(value, min_value, max_value):
    normalized_value = (value - min_value) / (max_value - min_value)
    return .7 * normalized_value  # scale down to avoid extremely green colors


def normalize_alpha(value, min_value, max_value):
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


def representative_color(value, min_value=None, max_value=None, colors=colors_redgreen):
    if value is None or np.isnan(value):  # it seems that depending on database backend, nans are either None or nan
        return f"background-color: {color_None}"
    normalized_value = normalize_value(value, min_value=min_value, max_value=max_value)  # normalize to range
    step = int(100 * normalized_value)
    color = colors[step]
    color = tuple(c * 255 for c in color.rgb)
    fallback_color = tuple(round(c) for c in color)
    normalized_alpha = normalize_alpha(value, min_value=min_value, max_value=max_value) \
        if min_value is not None else (100 * value)
    color += (normalized_alpha,)
    return f"background-color: rgb{fallback_color}; background-color: rgba{color};"


def _build_comparison_data(models):
    """
    Build an array object for use by the JavaScript frontend to dynamically compare trends across benchmarks.
    :return: an array where each dictionary element contains a model's scores on all benchmarks, e.g.
        ```
        [
            {"dicarlo.Rajalingham2018-i2n_v2-score": .521,
             "dicarlo.Rajalingham2018-i2n_v2-error": 0.00391920504344273,
             "behavior_v0-score": ".521",
             ...,
             "model": "mobilenet_v2_1.0_224",
            },
            ...
        ]
        ```
    """
    data = [dict(ChainMap(*[{'model': model_row.name}] +
                           [{f"{score_row.versioned_benchmark_identifier}-score": score_row.score_ceiled,
                             f"{score_row.versioned_benchmark_identifier}-error": score_row.error,
                             f"{score_row.versioned_benchmark_identifier}-is_complete": score_row.is_complete}
                            for score_row in model_row.scores]))
            for model_row in models]
    return data


# controls how model name and submitter appear on leaderboard:
def get_visibility(model, user):
    # Handles private competition models:
    if (not model.public) and (model.competition is not None):

        # Model is a private competition model, and user is logged in (or superuser)
        if (user is not None) and (user.is_superuser or model.user.id == user.id):
            return "private_owner"

        # Model is a private competition model, and user is NOT logged in (or NOT superuser)
        else:
            return "private_not_owner"

    # Model is public
    else:
        return "public"

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

    return "–" * number_of_characters


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
def format_score(score):
    try:
        return f"{score:.3f}"
    except:  # e.g. 'X'
        return score


@register.filter
def display_model(model, user):
    visibility = get_visibility(model, user)
    if visibility == "private_owner":
        return model.name
    elif visibility == "private_not_owner":
        return f"Model #{model.id}"
    else:
        return model.name


# controls the way model submitter appears (name vs Anonymous Submitter) in table
@register.filter
def display_submitter(model, user):
    visibility = get_visibility(model, user)
    if visibility == "private_owner":
        return model.user.display_name
    elif visibility == "private_not_owner":
        return f"Anonymous Submitter #{model.user.id}"
    else:
        return model.user.display_name


# controls how the benchmark roots are displayed in the comparison graphs
@register.filter
def simplify_domain(benchmark_name: str) -> str:
    suffixed_benchmarks = ['average', 'engineering', "neural", "behavior"]
    for suffixed_name in suffixed_benchmarks:
        if benchmark_name.startswith(f"{suffixed_name}_"):
            return suffixed_name
    return benchmark_name
