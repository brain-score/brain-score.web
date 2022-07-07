"""
Helper functions to provide meta information to the website.
"""
import logging
import sys
from pathlib import Path
from typing import Union, List, Tuple

import fire
import numpy as np
from PIL import Image
from brainio.assemblies import NeuroidAssembly
from brainio.stimuli import StimulusSet
from brainscore import benchmark_pool
from brainscore.benchmarks.screen import place_on_screen
from brainscore.model_interface import BrainModel
from numpy.random import RandomState
from tqdm import tqdm

_logger = logging.getLogger(__name__)
static_directory = Path(__file__).parent.parent / 'static' / 'benchmarks' / 'img'


class ImageStorerDummyModel(BrainModel):
    def __init__(self):
        self._time_bins = None
        self.stimuli = None

    @property
    def identifier(self) -> str:
        return 'imagestorer-dummymodel'

    def visual_degrees(self) -> int:
        return 8

    def look_at(self, stimuli: Union[StimulusSet, List[str]], number_of_trials=1):
        if len(stimuli) == 1:  # configuration stimuli, e.g. Kar2019 or Marques2020. Return to get to the real stimuli
            return NeuroidAssembly([[np.arange(len(self._time_bins))]], coords={
                **{'neuroid_id': ('neuroid', [123]), 'neuroid_num': ('neuroid', [123])},
                **{column: ('presentation', values) for column, values in stimuli.iteritems()},
                **{'time_bin_start': ('time_bin', [start for start, end in self._time_bins]),
                   'time_bin_end': ('time_bin', [end for start, end in self._time_bins])},
            }, dims=['presentation', 'neuroid', 'time_bin'])
        self.stimuli = stimuli
        raise StopIteration()

    def start_task(self, task: BrainModel.Task, fitting_stimuli=None):
        pass

    def start_recording(self, recording_target: BrainModel.RecordingTarget, time_bins=List[Tuple[int]]):
        self._time_bins = time_bins


def sample_benchmark_images(num_samples: int = 30, max_height: int = 90, replace=False):
    image_directory = (static_directory / 'benchmark_samples').resolve()
    _logger.debug(f"Saving to {image_directory}")

    image_storer = ImageStorerDummyModel()
    for benchmark_identifier, benchmark in tqdm(benchmark_pool.items(), desc='benchmarks'):
        versioned_benchmark_identifier = f"{benchmark_identifier}_v{benchmark.version}"
        _logger.debug(f"Benchmark {versioned_benchmark_identifier}")
        benchmark_directory = image_directory / versioned_benchmark_identifier
        if benchmark_directory.is_dir() and not replace:
            _logger.debug(f"Skipping {benchmark_directory} since it already exists and replace is {replace}")
            continue
        benchmark_directory.mkdir(exist_ok=True, parents=True)
        try:
            benchmark(image_storer)
        except StopIteration:
            pass
        stimuli = image_storer.stimuli
        random_state = RandomState(len(stimuli))  # seed with number of stimuli to pick different indices per benchmark
        sample_stimulus_ids = random_state.choice(stimuli['stimulus_id'],
                                               size=num_samples,
                                               replace=False if len(stimuli) >= num_samples else True)
        for sample_number, stimulus_id in enumerate(sample_stimulus_ids):
            source_path = Path(stimuli.get_stimulus(stimulus_id))
            image = Image.open(source_path)
            # resize to the desired height since the website's img height is restricted, so we save on network bandwidth
            resize_ratio = max_height / image.size[1]
            if resize_ratio < 1:  # current image bigger than necessary
                image = image.resize(np.ceil(np.array(image.size) * resize_ratio).astype(int), Image.ANTIALIAS)
            # # convert to png
            target_path = benchmark_directory / f"{sample_number}.png"
            image.save(target_path)


def visual_degree_samples(visual_degrees_samples=(8, 4, 12), base_degrees=8):
    base_image = Path(__file__).parent / 'base.png'
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


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    for shush_logger in ['PIL', 's3transfer', 'botocore', 'boto3', 'urllib3']:
        logging.getLogger(shush_logger).setLevel(logging.INFO)
    fire.Fire()
