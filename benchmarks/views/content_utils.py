"""
Helper functions to provide meta information to the website.

To execute, run server and visit site .../content_utils/sample_benchmark_images/.
Necessary to run via Django so that we can access the database.

requirements: brainscore-vision fire Pillow
"""
import logging
import re
from pathlib import Path
from typing import List, Optional

import numpy as np
from django.http import HttpResponse
from numpy.random import RandomState
from tqdm import tqdm

from benchmarks.models import BenchmarkInstance, BenchmarkType

_logger = logging.getLogger(__name__)
static_directory = Path(__file__).parent.parent.parent / 'static' / 'benchmarks' / 'img'


def _find_benchmark_plugin_dir(benchmarks_dir: Path, benchmark_identifier: str) -> Optional[Path]:
    """
    Locate the plugin directory for a benchmark identifier by scanning __init__.py files
    for benchmark_registry entries. Mirrors ImportPlugin.locate_plugin logic.
    """
    for plugin_dir in benchmarks_dir.iterdir():
        if not plugin_dir.is_dir() or plugin_dir.name.startswith(('.', '_')):
            continue
        init_file = plugin_dir / "__init__.py"
        if not init_file.is_file():
            continue
        with open(init_file, encoding='utf-8') as f:
            for line in f:
                normalized = line.replace('"', "'")
                if f"benchmark_registry['{benchmark_identifier}']" in normalized:
                    return plugin_dir
    return None


def _extract_stimulus_set_identifiers(plugin_dir: Path, data_dir: Path) -> List[str]:
    """
    Parse Python source files in a benchmark plugin directory to extract
    stimulus set identifiers from load_stimulus_set() calls.
    Only extracts static string literals (not f-strings or variables).

    Falls back to scanning the corresponding data plugin directory for
    stimulus_set_registry entries when the benchmark uses dynamic identifiers.
    """
    load_pattern = re.compile(r"""load_stimulus_set\(\s*['"]([^'"]+)['"]\s*\)""")
    identifiers = []
    for py_file in plugin_dir.glob("*.py"):
        with open(py_file, encoding='utf-8') as f:
            for line in f:
                for match in load_pattern.finditer(line):
                    identifier = match.group(1)
                    if identifier not in identifiers:
                        identifiers.append(identifier)

    if identifiers:
        return identifiers

    # fallback: check data plugin directory with same name for stimulus_set_registry entries
    data_plugin_dir = data_dir / plugin_dir.name
    if not data_plugin_dir.is_dir():
        return identifiers
    init_file = data_plugin_dir / "__init__.py"
    if not init_file.is_file():
        return identifiers
    registry_pattern = re.compile(r"""stimulus_set_registry\[\s*['"]([^'"]+)['"]\s*\]""")
    with open(init_file, encoding='utf-8') as f:
        for line in f:
            for match in registry_pattern.finditer(line):
                identifier = match.group(1)
                if identifier not in identifiers:
                    identifiers.append(identifier)
    return identifiers


def sample_benchmark_images(request):
    from PIL import Image
    from brainscore_vision import load_stimulus_set
    import brainscore_vision

    num_samples = 30
    max_height = 90
    replace = False

    brainscore_root = Path(brainscore_vision.__file__).parent
    benchmarks_dir = brainscore_root / 'benchmarks'
    data_dir = brainscore_root / 'data'

    benchmark_identifiers = BenchmarkType.objects \
        .filter(domain='vision', visible=True) \
        .order_by('identifier') \
        .values_list('identifier', flat=True)

    image_directory = (static_directory / 'benchmark_samples').resolve()
    _logger.debug(f"Saving to {image_directory}")
    benchmarks_success_skip_fail = [], [], []

    for benchmark_identifier in tqdm(benchmark_identifiers, desc='benchmarks'):
        print(benchmark_identifier)
        if benchmark_identifier.startswith('ImageNet-C'):
            benchmarks_success_skip_fail[1].append(benchmark_identifier)
            continue

        # get version from DB instead of loading the benchmark
        try:
            instance = BenchmarkInstance.objects.filter(
                benchmark_type__identifier=benchmark_identifier
            ).order_by('-version').first()
            if instance is None:
                _logger.warning(f"No BenchmarkInstance for {benchmark_identifier}. Skipping.")
                benchmarks_success_skip_fail[2].append(benchmark_identifier)
                continue
            version = instance.version
        except Exception:
            _logger.exception(f"Failed to get version for {benchmark_identifier}")
            benchmarks_success_skip_fail[2].append(benchmark_identifier)
            continue

        versioned_benchmark_identifier = f"{benchmark_identifier}_v{version}"
        _logger.debug(f"Benchmark {versioned_benchmark_identifier}")
        benchmark_directory = image_directory / versioned_benchmark_identifier
        if benchmark_directory.is_dir() and not replace:
            _logger.debug(f"Skipping {benchmark_directory} since it already exists and replace is {replace}")
            benchmarks_success_skip_fail[1].append(benchmark_identifier)
            continue

        # find the benchmark plugin directory and parse stimulus set identifiers from source
        plugin_dir = _find_benchmark_plugin_dir(benchmarks_dir, benchmark_identifier)
        if plugin_dir is None:
            _logger.warning(f"Cannot locate plugin directory for {benchmark_identifier}. Skipping.")
            benchmarks_success_skip_fail[2].append(benchmark_identifier)
            continue

        stimulus_set_ids = _extract_stimulus_set_identifiers(plugin_dir, data_dir)
        if not stimulus_set_ids:
            _logger.warning(f"No static load_stimulus_set() calls found for {benchmark_identifier} "
                            f"in {plugin_dir}. Skipping.")
            benchmarks_success_skip_fail[2].append(benchmark_identifier)
            continue

        # load the first stimulus set directly (no neural/behavioral data downloaded)
        stimulus_set_id = stimulus_set_ids[0]
        try:
            stimuli = load_stimulus_set(stimulus_set_id)
        except Exception:
            _logger.exception(f"Failed to load stimulus set '{stimulus_set_id}' for {benchmark_identifier}")
            benchmarks_success_skip_fail[2].append(benchmark_identifier)
            continue

        # sample and save images
        try:
            benchmark_directory.mkdir(exist_ok=True, parents=True)
            random_state = RandomState(len(stimuli))
            sample_stimulus_ids = random_state.choice(
                stimuli['stimulus_id'],
                size=num_samples,
                replace=len(stimuli) < num_samples,
            )
            for sample_number, stimulus_id in enumerate(sample_stimulus_ids):
                source_path = Path(stimuli.get_stimulus(stimulus_id))
                image = Image.open(source_path)
                resize_ratio = max_height / image.size[1]
                if resize_ratio < 1:
                    image = image.resize(
                        np.ceil(np.array(image.size) * resize_ratio).astype(int),
                        Image.LANCZOS,
                    )
                target_path = benchmark_directory / f"{sample_number}.png"
                image.save(target_path)
            benchmarks_success_skip_fail[0].append(benchmark_identifier)
        except Exception:
            _logger.exception(f"Failed to write stimuli for {benchmark_identifier}")
            benchmarks_success_skip_fail[2].append(benchmark_identifier)

    return HttpResponse(
        f"Samples written to {image_directory}. \n\n"
        f"Succeeded ({len(benchmarks_success_skip_fail[0])}): {benchmarks_success_skip_fail[0]}.\n\n"
        f"Skipped   ({len(benchmarks_success_skip_fail[1])}): {benchmarks_success_skip_fail[1]}.\n\n"
        f"Failed    ({len(benchmarks_success_skip_fail[2])}): {benchmarks_success_skip_fail[2]}.\n\n",
        content_type="text/plain",
    )


def visual_degree_samples(visual_degrees_samples=(8, 4, 12), base_degrees=8):
    from PIL import Image
    from brainio.stimuli import StimulusSet
    from brainscore_vision.benchmark_helpers.screen import place_on_screen

    base_image = static_directory / 'visual_degrees' / 'base.png'
    stimulus_set = StimulusSet([{'stimulus_id': 'base'}])
    stimulus_set.image_paths = {'base': base_image}
    stimulus_set.identifier = 'visual_degrees_base'
    for visual_degrees in visual_degrees_samples:
        converted_stimulus_set = place_on_screen(stimulus_set,
                                                 source_visual_degrees=visual_degrees,
                                                 target_visual_degrees=base_degrees)
        converted_path = converted_stimulus_set.get_stimulus('base')
        target_path = static_directory / 'visual_degrees' / f"benchmark{visual_degrees}_model{base_degrees}.png"
        converted_image = Image.open(converted_path)
        _logger.debug(f"Saving to {target_path}")
        converted_image.save(target_path)
