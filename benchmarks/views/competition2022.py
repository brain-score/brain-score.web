import random
import string
import pickle
import os
from collections import namedtuple
from operator import itemgetter
from pathlib import Path

from django.shortcuts import render
from django.conf import settings
from numpy.random.mtrand import RandomState

# Keep original functions for backward compatibility
try:
    from .index import get_context
except ImportError:
    get_context = None

NUM_STIMULI_SAMPLES = 150


def view(request):
    """
    Competition 2022 view with pickle fallback.
    First tries to load from pickle file, falls back to original method if available.
    """
    # Path to the pickled data file
    pickle_file = Path(settings.BASE_DIR) / 'competition2022_data.pkl'
    
    # Try pickle method first
    if pickle_file.exists():
        try:
            # Load the pickled data
            with open(pickle_file, 'rb') as f:
                context = pickle.load(f)
            
            # Convert dictionaries back to objects for template compatibility
            def dict_to_obj(d):
                if isinstance(d, dict):
                    obj = type('DictObj', (), {})()
                    for key, value in d.items():
                        setattr(obj, key, dict_to_obj(value))
                    return obj
                elif isinstance(d, list):
                    return [dict_to_obj(item) for item in d]
                else:
                    return d
            
            # Convert all the data back to objects
            for key in context:
                if key.startswith('benchmarks_') or key.startswith('models_') or key == 'stimuli_samples':
                    context[key] = dict_to_obj(context[key])
            
            # Fix stimuli sample paths - remove lab prefixes to match actual directory structure
            if 'stimuli_samples' in context:
                import os
                samples_dir = Path(settings.BASE_DIR) / 'static' / 'benchmarks' / 'img' / 'benchmark_samples'
                
                # Build mapping from actual directories to corrected paths
                available_dirs = set()
                if samples_dir.exists():
                    available_dirs = {d.name for d in samples_dir.iterdir() if d.is_dir()}
                
                for sample in context['stimuli_samples']:
                    if hasattr(sample, 'path'):
                        # Extract the path components
                        path_parts = sample.path.split('/')
                        if len(path_parts) >= 2:
                            dir_name = path_parts[0]
                            file_name = path_parts[1]
                            
                            # If the directory doesn't exist, try removing lab prefix
                            if dir_name not in available_dirs:
                                # Try removing lab prefix (e.g., "dicarlo.SanghaviMurty2020.V4-pls_v1" -> "SanghaviMurty2020.V4-pls_v1")
                                if '.' in dir_name:
                                    corrected_dir = '.'.join(dir_name.split('.')[1:])  # Remove first part before dot
                                    if corrected_dir in available_dirs:
                                        sample.path = f"{corrected_dir}/{file_name}"
            
            # Ensure required keys exist
            if 'leaderboard_keys' not in context:
                context['leaderboard_keys'] = ['average', 'V1', 'behavior']
            
            # Add success info
            context['data_source'] = f'Loaded from {pickle_file}'
            context['data_timestamp'] = os.path.getmtime(pickle_file)
            
            return render(request, 'benchmarks/competition2022.html', context)
            
        except Exception as e:
            # Pickle failed, try original method below
            print(f"Pickle loading failed: {e}")
    
    # Fallback to original method if get_context is available
    if get_context is not None:
        try:
            return view_original(request)
        except Exception as e:
            print(f"Original method failed: {e}")
    
    # Both methods failed, return error page
    context = {
        'leaderboard_keys': ['average', 'V1', 'behavior'],
        'error_message': 'Competition data unavailable',
        'instructions': [
            'To enable this page, either:',
            '1. Run: python export_competition_data.py (to create pickle file)',
            '2. Or ensure get_context function is available for original method',
        ],
        'benchmarks_average_vision': [],
        'models_average_vision': [],
        'benchmarks_V1': [],
        'models_V1': [],
        'benchmarks_behavior_vision': [],
        'models_behavior_vision': [],
        'stimuli_samples': [],
    }
    return render(request, 'benchmarks/competition2022.html', context)


def view_original(request):
    """Original competition2022 view implementation (fallback)."""
    context = {'leaderboard_keys': ['average', 'V1', 'behavior']}
    # specify exact set of benchmarks used in this competition (brain benchmarks only, ignore temporal benchmark)
    # A problem with this filter is that it only filters for the benchmark type, but not the *instance*.
    # I.e., if a benchmark is updated with a new version, this call will still use the newest version rather than
    # the version at the time of the competition.
    included_benchmarks = [
        'average_vision',
        'neural_vision',
        'V1',
        'FreemanZiemba2013.V1-pls',
        'Marques2020', 'V1-orientation', 'V1-spatial_frequency', 'V1-response_selectivity',
        'V1-receptive_field_size', 'V1-surround_modulation', 'V1-texture_modulation', 'V1-response_magnitude',
        'Marques2020_Ringach2002-circular_variance', 'Marques2020_Ringach2002-or_bandwidth',
        'Marques2020_Ringach2002-orth_pref_ratio', 'Marques2020_Ringach2002-or_selective',
        'Marques2020_Ringach2002-cv_bandwidth_ratio', 'Marques2020_Ringach2002-opr_cv_diff',
        'Marques2020_DeValois1982-pref_or', 'Marques2020_DeValois1982-peak_sf',
        'Marques2020_Schiller1976-sf_selective', 'Marques2020_Schiller1976-sf_bandwidth',
        'Marques2020_Cavanaugh2002-grating_summation_field',
        'Marques2020_Cavanaugh2002-surround_diameter',
        'Marques2020_Cavanaugh2002-surround_suppression_index',
        'Marques2020_FreemanZiemba2013-texture_modulation_index',
        'Marques2020_FreemanZiemba2013-abs_texture_modulation_index',
        'Marques2020_FreemanZiemba2013-texture_selectivity',
        'Marques2020_FreemanZiemba2013-texture_sparseness',
        'Marques2020_FreemanZiemba2013-texture_variance_ratio', 'Marques2020_Ringach2002-max_dc',
        'Marques2020_Ringach2002-modulation_ratio', 'Marques2020_FreemanZiemba2013-max_texture',
        'Marques2020_FreemanZiemba2013-max_noise',
        'V2',
        'FreemanZiemba2013.V2-pls',
        'V4',
        'MajajHong2015.V4-pls', 'Sanghavi2020.V4-pls', 'SanghaviJozwik2020.V4-pls',
        'SanghaviMurty2020.V4-pls',
        'IT',
        'MajajHong2015.IT-pls', 'Sanghavi2020.IT-pls', 'SanghaviJozwik2020.IT-pls',
        'SanghaviMurty2020.IT-pls',
        'behavior_vision',
        'Rajalingham2018-i2n',
    ]
    assert len(included_benchmarks) == 33 + len(
        ['average_vision', 'neural_vision', 'V1', 'V2', 'V4', 'IT', 'behavior_vision', 'Marques2020']) + \
           7  # (Marques 2nd level)
    base_filter = lambda benchmarks: benchmarks.filter(identifier__in=included_benchmarks)
    # further filter for each track
    for key, selection_filter in [
        ('V1', lambda benchmarks: benchmarks.exclude(identifier__in=['V2', 'V4', 'IT', 'behavior_vision'])),
        ('behavior_vision', lambda benchmarks: benchmarks.exclude(identifier__in=['neural_vision', 'V1', 'V2', 'V4', 'IT'])),
        ('average_vision', lambda benchmarks: benchmarks),  # average last to have full set of adjacent variables in context
    ]:
        benchmark_filter = lambda benchmarks: selection_filter(base_filter(benchmarks))
        key_context = get_context(benchmark_filter=benchmark_filter,
                                  model_filter=dict(model__competition='cosyne2022'), show_public=True)
        key_context['models'] = group_by_user(key_context['models'])
        key_context[f"benchmarks_{key}"] = key_context['benchmarks']
        key_context[f"models_{key}"] = key_context['models']
        del key_context['benchmarks'], key_context['models']
        context = {**context, **key_context}
    benchmark_instances = [benchmark for benchmark in context['benchmarks_average_vision'] if benchmark.id is not None
                           # ignore Marques2020 benchmarks for now since the sampled stimuli are only those from
                           # receptive-field-mapping
                           and not benchmark.benchmark_type_id.startswith('Marques2020')
                           ]
    context['stimuli_samples'] = create_stimuli_samples(benchmark_instances, num_samples=NUM_STIMULI_SAMPLES)
    return render(request, 'benchmarks/competition2022.html', context)


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
    import os
    StimulusSample = namedtuple('StimulusSample', field_names=['path', 'benchmark_identifier'])

    # Build a mapping from benchmark identifier to actual directory name
    samples_dir = 'static/benchmarks/img/benchmark_samples'
    benchmark_dir_mapping = {}
    
    if os.path.exists(samples_dir):
        for dir_name in os.listdir(samples_dir):
            dir_path = os.path.join(samples_dir, dir_name)
            if os.path.isdir(dir_path):
                # Extract benchmark name from full directory name (remove lab prefix)
                # e.g., "dicarlo.SanghaviJozwik2020.IT-pls_v1" -> "SanghaviJozwik2020.IT-pls"
                if '.' in dir_name:
                    parts = dir_name.split('.', 1)  # Split only on first dot
                    if len(parts) > 1:
                        benchmark_name = parts[1]  # Everything after first dot
                        # Remove version suffix (e.g., "_v1")
                        if '_v' in benchmark_name:
                            benchmark_name = benchmark_name.rsplit('_v', 1)[0]
                        benchmark_dir_mapping[benchmark_name] = dir_name

    samples = set()
    random = RandomState(42)
    while len(samples) < num_samples:
        benchmark = random.choice(benchmark_instances)
        sample_num = random.randint(low=0, high=available_sample_per_benchmark)
        
        # Try to find the actual directory name for this benchmark
        benchmark_identifier = benchmark.identifier
        # Remove version suffix if present
        if '_v' in benchmark_identifier:
            benchmark_identifier = benchmark_identifier.rsplit('_v', 1)[0]
            
        actual_dir = benchmark_dir_mapping.get(benchmark_identifier, benchmark_identifier)
        path = f"{actual_dir}/{sample_num}.png"
        sample = StimulusSample(path=path, benchmark_identifier=benchmark.identifier)
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
