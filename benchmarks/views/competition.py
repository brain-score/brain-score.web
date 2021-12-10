from collections import namedtuple

from numpy.random.mtrand import RandomState

from .index import get_context
from django.shortcuts import render

NUM_STIMULI_SAMPLES = 150


def view(request):
    # brain benchmarks only, ignore temporal benchmark
    context = get_context(benchmark_filter=lambda benchmarks: benchmarks.exclude(
        identifier__in=['engineering', 'dicarlo.Kar2019-ost']),
                          model_filter=dict(model__competition='cosyne2022'))
    benchmark_instances = [benchmark for benchmark in context['benchmarks'] if benchmark.id is not None
                           # ignore Marques2020 benchmarks for now since the sampled stimuli are only those from
                           # receptive-field-mapping
                           and not benchmark.benchmark_type_id.startswith('dicarlo.Marques2020')
                           ]
    context['stimuli_samples'] = create_stimuli_samples(benchmark_instances, num_samples=NUM_STIMULI_SAMPLES)
    return render(request, 'benchmarks/competition.html', context)


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
