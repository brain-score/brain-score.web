import random
import string
from collections import namedtuple
from operator import itemgetter

from django.shortcuts import render
from numpy.random.mtrand import RandomState

from .index import get_context

NUM_STIMULI_SAMPLES = 150


def view(request):
    context = {'leaderboard_keys': ['average', 'V1', 'behavior']}
    for key, selection_filter in [
        ('V1', lambda benchmarks: benchmarks.exclude(identifier__in=['V2', 'V4', 'IT', 'behavior'])),
        ('behavior', lambda benchmarks: benchmarks.exclude(identifier__in=['V1', 'V2', 'V4', 'IT'])),
        ('average', lambda benchmarks: benchmarks),  # average last to have full set of adjacent variables in context
    ]:
        # brain benchmarks only, ignore temporal benchmark
        base_filter = lambda benchmarks: benchmarks.exclude(identifier__in=['engineering', 'dicarlo.Kar2019-ost'])
        benchmark_filter = lambda benchmarks: selection_filter(base_filter(benchmarks))
        key_context = get_context(benchmark_filter=benchmark_filter,
                                  model_filter=dict(model__competition='cosyne2022'), show_public=True)
        key_context['models'] = group_by_user(key_context['models'])
        key_context[f"benchmarks_{key}"] = key_context['benchmarks']
        key_context[f"models_{key}"] = key_context['models']
        del key_context['benchmarks'], key_context['models']
        context = {**context, **key_context}
    benchmark_instances = [benchmark for benchmark in context['benchmarks_average'] if benchmark.id is not None
                           # ignore Marques2020 benchmarks for now since the sampled stimuli are only those from
                           # receptive-field-mapping
                           and not benchmark.benchmark_type_id.startswith('dicarlo.Marques2020')
                           ]
    context['stimuli_samples'] = create_stimuli_samples(benchmark_instances, num_samples=NUM_STIMULI_SAMPLES)
    return render(request, 'benchmarks/competition.html', context)


def group_by_user(models):
    # group
    submitters = [m.user.email +
                  # append random string to superuser to treat baselines as coming from separate users
                  (''.join(random.choices(string.ascii_uppercase, k=3)) if m.user.is_superuser else '')
                  for m in models]
    unique_submitters, unique_indices = unique_in_order(submitters, return_index=True)
    top_models = itemgetter(*unique_indices)(models)
    # re-rank
    reranked_models = []
    for rank, top_model in enumerate(top_models, start=1):
        # find secondary models that also belong to this user
        secondary_models = [model for model in models
                            if model.user == top_model.user
                            and model.id != top_model.id
                            and not model.user.is_superuser]
        # if any of the models is set to private, we have to set everything to private to avoid revealing identities
        all_public = top_model.public and all(secondary_model.public for secondary_model in secondary_models)
        top_model = top_model._replace(rank=rank, public=all_public)
        # add count to model row
        model_dict = top_model._asdict()
        TopModel = namedtuple('TopModel', list(model_dict.keys()) + ['num_secondary_models'])
        top_model = TopModel(*(list(model_dict.values()) + [len(secondary_models)]))
        reranked_models.append(top_model)
        # append secondary models
        for secondary_model in secondary_models:
            secondary_model = secondary_model._replace(rank='', public=all_public)
            model_dict = secondary_model._asdict()
            SecondaryModel = namedtuple('SecondaryModel', list(model_dict.keys()) + ['primary_model_id'])
            secondary_model = SecondaryModel(*(list(model_dict.values()) + [top_model.id]))
            reranked_models.append(secondary_model)

    return reranked_models


def create_stimuli_samples(benchmark_instances, num_samples, available_sample_per_benchmark=30):
    """
    :param benchmark_instances:
    :param num_samples:
    :param available_sample_per_benchmark: how many image files have been pre-generated per benchmark
    :return:
    """
    StimulusSample = namedtuple('StimulusSample', field_names=['path', 'benchmark_short_name'])

    samples = set()
    random = RandomState(42)
    while len(samples) < num_samples:
        benchmark = random.choice(benchmark_instances)
        sample_num = random.randint(low=0, high=available_sample_per_benchmark)
        path = f"{benchmark.identifier}/{sample_num}.png"
        sample = StimulusSample(path=path, benchmark_short_name=benchmark.identifier)
        samples.add(sample)
    samples = list(sorted(samples))  # make order deterministic
    random.shuffle(samples)  # reshuffle
    return samples


def unique_in_order(sequence, return_index=False):
    """
    returns the unique items in the sequence, in the order that they occur in the sequence
    """
    # from https://stackoverflow.com/a/480227/2225200
    seen = set()
    seen_add = seen.add
    unique = [(x, index) for index, x in enumerate(sequence) if not (x in seen or seen_add(x))]
    unique, indices = zip(*unique)
    return (unique, indices) if return_index else unique
