import logging
import os

from brainio.assemblies import NeuroidAssembly
from brainio.stimuli import StimulusSet
from brainscore_vision import load_model, BrainModel, load_dataset, load_stimulus_set
from brainscore_vision.benchmark_helpers.neural_common import average_repetition
from brainscore_vision.metrics.regression_correlation import ridge_regression
from django import forms
from django.core.files.uploadhandler import TemporaryFileUploadHandler
from django.http import HttpResponse
from django.shortcuts import render
from django.template.defaulttags import register
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

_logger = logging.getLogger(__name__)


class UploadPlaceHolder(forms.Form):
    stimulus_files = forms.FileField(help_text='Required')


class UploadStimuliForm(forms.Form):
    stimulus_files = forms.FileField(label="", help_text='Required', widget=forms.ClearableFileInput(attrs={
        "name": "stimulus_files",
        "type": "File",
        "class": "form-control",
        "multiple": "True",
    }))

    class Meta:
        model = UploadPlaceHolder
        fields = ('stimulus_files',)


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


@method_decorator(csrf_exempt, name="dispatch")
class Inference(View):
    domain = None

    def setup(self, request, *args, **kwargs):  # force uploaded files to be written to disk
        super().setup(request, *args, **kwargs)
        request.upload_handlers = [TemporaryFileUploadHandler(request=request)]
        return request

    def get(self, request):
        assert self.domain is not None
        form = UploadStimuliForm()
        return render(request, 'benchmarks/inference_select.html',
                      {'form': form, 'domain': self.domain, 'formatted': self.domain.capitalize()})

    def post(self, request):
        assert self.domain is not None
        form = UploadStimuliForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponse("Form is invalid", status=400)

        stimuli = form.files.getlist('stimulus_files')
        stimulus_ids = list(range(len(stimuli)))
        stimulus_set = StimulusSet({'stimulus_id': stimulus_ids})
        stimulus_set.stimulus_paths = {stimulus_id: stimulus.temporary_file_path()
                                       for stimulus_id, stimulus in zip(stimulus_ids, stimuli)}
        stimulus_set.identifier = 'model_inference_stimuli'

        model_identifier = 'alexnet'
        mapping = 'MajajHong2015.public'
        neural_predictions = _run_model(model_identifier=model_identifier,
                                        stimuli=stimulus_set, mapping_data_identifier=mapping)
        neural_predictions = _normalize(neural_predictions)

        # context
        model = Struct(identifier=model_identifier, layer='IT.output')
        region = 'IT'
        mapping = Struct(identifier='MajajHong2015.IT-pls', num_neural_sites=len(neural_predictions['neuroid']),
                         region='IT', regression='ridge')
        context = {
            'model': model,
            'region': region,
            'mapping': mapping,
            'stimuli': stimulus_set,
            'neural_activity': neural_predictions,
            'domain': self.domain,
        }

        return render(request, 'benchmarks/inference_result.html', context)


def _run_model(model_identifier: str, stimuli: StimulusSet, mapping_data_identifier: str):
    os.environ['RESULTCACHING_DISABLE'] = \
        'brainscore_vision.model_helpers.activations.core.ActivationsExtractorHelper._from_paths_stored'
    model = load_model(model_identifier)
    model.layer_model.region_layer_map['IT'] = 'features.12'
    model.start_recording(recording_target=BrainModel.RecordingTarget.IT, time_bins=[(70, 170)])

    # mapping
    mapping_data = load_dataset(mapping_data_identifier)
    mapping_data = mapping_data.sel(region='IT')
    mapping_data = mapping_data.squeeze('time_bin')
    mapping_data = average_repetition(mapping_data)
    mapping_stimuli = load_stimulus_set(mapping_data.attrs['stimulus_set_identifier'])
    mapping_predictions = model.look_at(mapping_stimuli)
    regression = ridge_regression()
    regression.fit(mapping_predictions, mapping_data)

    # requested stimuli
    model_activity = model.look_at(stimuli)
    predictions = regression.predict(model_activity)
    return predictions


def _normalize(predictions: NeuroidAssembly, target_max=256) -> NeuroidAssembly:
    min, max = predictions.values.min(), predictions.values.max()
    return 0 + (predictions - min) * (target_max - 0) / (max - min)


@register.filter
def get_stimulus(data_row: NeuroidAssembly, stimuli: StimulusSet) -> str:
    return stimuli.get_stimulus(0)  # todo: return proper stimuli
