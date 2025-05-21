import logging
from collections import namedtuple

from django.db.models import F
from django.shortcuts import render

from benchmarks.models import BenchmarkInstance, Score
from benchmarks.views.index import represent, reference_identifier
from benchmarks.utils import representative_color

_logger = logging.getLogger(__name__)


def view(request, id: int, domain: str):
    # benchmark
    benchmark = (BenchmarkInstance.objects
                 .select_related('benchmark_type', 'benchmark_type__reference', 'meta')
                 .get(id=id))  # `benchmark_type__domain=domain` is not needed since ids are unique)
    benchmark_identifier = benchmark.benchmark_type.identifier
    versioned_benchmark_identifier = f'{benchmark_identifier}_v{benchmark.version}'

    # scores
    filtered_scores = (Score.objects
                       .filter(benchmark_id=id, model__public=True))
    ordered_raw_scores = (filtered_scores
                          .values_list('score_raw', flat=True)
                          .exclude(score_raw__isnull=True)
                          .order_by('-score_raw'))
    benchmark_max = ordered_raw_scores.first()
    benchmark_min = ordered_raw_scores.last()

    # score display
    scores = (filtered_scores
              .order_by(F('score_raw').desc(nulls_last=True))
              .select_related('model', 'model__reference'))
    BenchmarkDisplay = namedtuple('BenchmarkDisplay', field_names=[
        'short_name', 'depth'])
    ScoreDisplay = namedtuple('ScoreDisplay', field_names=[
        'score_ceiled', 'score_raw', 'color', 'versioned_benchmark_identifier', 'benchmark'])
    ModelRow = namedtuple('ModelRow', field_names=[
        'id', 'name', 'rank', 'public', 'competition', 'scores', 'reference_identifier',
        'owner', 'primary_model_id', 'num_secondary_models'])
    models = []
    for model_rank, score_row in enumerate(scores, start=1):
        models.append(ModelRow(
            id=score_row.model.id,
            name=score_row.model.name,
            rank=model_rank,
            public=score_row.model.public, competition=score_row.model.competition,
            scores=[ScoreDisplay(
                score_ceiled=represent(score_row.score_ceiled),
                score_raw=score_row.score_raw,
                color=representative_color(score_row.score_raw, min_value=benchmark_min, max_value=benchmark_max),
                versioned_benchmark_identifier=versioned_benchmark_identifier,
                benchmark=BenchmarkDisplay(short_name=benchmark_identifier, depth=0),
            )],
            # make table-body.html happy
            owner=None, primary_model_id=None, num_secondary_models=None,
            reference_identifier=reference_identifier(score_row.model.reference)
        ))

    data_identifier, metric_identifier = benchmark_identifier.rsplit('-', 1)
    reference = benchmark.benchmark_type.reference
    context = {'benchmark': benchmark, 'domain': domain,
               'versioned_benchmark_identifier': versioned_benchmark_identifier,
               'data_identifier': data_identifier, 'metric_identifier': metric_identifier,
               'reference_identifier': reference_identifier(reference),
               'reference_url': reference.url if reference is not None else None,
               'reference_bibtex': reference.bibtex if reference is not None else None,
               # scores
               'models': models,
               # make table-body.html happy
               'has_user': False, 'not_shown_set': set(), 'benchmark_parents': None}

    return render(request, 'benchmarks/benchmark.html', context)
