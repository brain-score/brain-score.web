---
title: Behavioral Benchmarks
description: Creating benchmarks that compare model behavior to human psychophysical data
order: 4
category: benchmarks
---

# Behavioral Benchmarks

Behavioral benchmarks compare model behavioral responses to human psychophysical data from experiments measuring choices, reaction times, and other behavioral outputs.

---

## Overview

| Benchmark | Description | Task Type | Metric |
|-----------|-------------|-----------|--------|
| `Rajalingham2018` | Human vs model object recognition patterns | Probabilities | I2N |
| `Ferguson2024` | Visual search asymmetry tasks | Probabilities | Value Delta |
| `Hebart2023` | Odd-one-out similarity judgments | Odd-one-out | Accuracy |
| `Geirhos2021` | Shape vs texture bias measurements | Label | Bias comparison |

**Key Characteristics**:
- Use `BehavioralAssembly` data structures
- Employ behavioral metrics (accuracy, similarity, consistency)
- Focus on choice patterns and response distributions
- **No `BehavioralBenchmark` helper class** — inherit `BenchmarkBase` directly

---

## Inheritance Structure

Unlike neural benchmarks, behavioral benchmarks **do not** have a helper class. You inherit directly from `BenchmarkBase`:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Benchmark (ABC)                                                             │
│  └── BenchmarkBase(Benchmark)                                                │
│      └── Your behavioral benchmark (implements __call__ directly)            │
│                                                                              │
│  Note: No BehavioralBenchmark helper class exists!                           │
│  You must implement __call__, start_task, place_on_screen, look_at yourself  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Example 1: Rajalingham2018 (I2N Metric)

This benchmark compares model and human object recognition patterns at the image level:

```python
# Located: brainscore_vision/benchmarks/rajalingham2018/benchmarks/benchmark.py

class _DicarloRajalingham2018(BenchmarkBase):
    def __init__(self, metric, metric_identifier):
        # The metric (I2N) compares image-by-image behavioral patterns
        self._metric = metric
        
        # Fitting stimuli: separate training data for the model's readout
        # This ensures fair comparison — model learns from different images
        self._fitting_stimuli = load_stimulus_set('objectome.public')
        
        # Human behavioral data (lazy-loaded to save memory)
        self._assembly = LazyLoad(lambda: load_assembly('private'))
        
        # Experimental parameters
        self._visual_degrees = 8    # Stimuli shown at 8° visual angle
        self._number_of_trials = 2  # 2 trials per stimulus
        
        super().__init__(
            identifier='Rajalingham2018-' + metric_identifier,
            version=2,
            # Ceiling: how well can humans predict other humans?
            ceiling_func=lambda: self._metric.ceiling(self._assembly),
            parent='behavior',
            bibtex=BIBTEX
        )

    def __call__(self, candidate: BrainModel) -> Score:
        # 1. Scale FITTING stimuli to model's visual field
        fitting_stimuli = place_on_screen(
            self._fitting_stimuli,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        
        # 2. Set up task: model learns to output probabilities over object classes
        #    fitting_stimuli provides training data for the readout
        candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
        
        # 3. Scale TEST stimuli to model's visual field
        stimulus_set = place_on_screen(
            self._assembly.stimulus_set,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        
        # 4. Present test stimuli and get model's probability outputs
        probabilities = candidate.look_at(stimulus_set, number_of_trials=self._number_of_trials)
        
        # 5. Compare model probabilities to human choices using I2N metric
        #    I2N = image-level consistency, measuring per-image agreement
        score = self._metric(probabilities, self._assembly)
        
        # 6. Normalize by ceiling
        ceiling = self.ceiling
        score = self.ceil_score(score, ceiling)
        
        return score
```

**Key patterns in Rajalingham2018:**
- **Fitting stimuli**: Separate training data (`objectome.public`) from test data
- **Probabilities task**: Model outputs probability distributions over classes
- **I2N metric**: Measures image-by-image behavioral consistency
- **Custom ceiling**: Uses the metric's `ceiling()` method (split-half reliability)

---

## Example 2: Ferguson2024 (Value Delta Metric)

This benchmark measures visual search asymmetry — how model performance patterns match humans across different conditions:

```python
# Located: brainscore_vision/benchmarks/ferguson2024/benchmark.py

class _Ferguson2024ValueDelta(BenchmarkBase):
    def __init__(self, experiment, precompute_ceiling=True):
        self._experiment = experiment  # e.g., 'tilted_line', 'color', 'gray_hard'
        
        # Value Delta metric: compares scalar values (integrals) between model and human
        self._metric = load_metric('value_delta', scale=0.75)
        
        # Fitting stimuli: training data specific to this experiment type
        self._fitting_stimuli = gather_fitting_stimuli(combine_all=False, experiment=self._experiment)
        
        # Human behavioral data for this specific experiment
        self._assembly = load_dataset(f'Ferguson2024_{self._experiment}')
        
        # Experimental parameters
        self._visual_degrees = 8
        self._number_of_trials = 3  # 3 trials per stimulus
        
        # Pre-computed ceiling (saves time, same result as computing each time)
        self._ceiling = calculate_ceiling(precompute_ceiling, self._experiment, 
                                          self._assembly, self._metric, num_loops=500)
        
        super().__init__(
            identifier=f"Ferguson2024{self._experiment}-value_delta",
            version=1,
            ceiling_func=self._ceiling,
            parent='behavior',
            bibtex=BIBTEX
        )

    def __call__(self, candidate: BrainModel) -> Score:
        # 1. Add truth labels to stimuli (oddball vs same)
        self._assembly.stimulus_set["image_label"] = np.where(
            self._assembly.stimulus_set["image_number"] % 2 == 0, "oddball", "same"
        )
        self._fitting_stimuli["image_label"] = np.where(
            self._fitting_stimuli["image_number"] % 2 == 0, "oddball", "same"
        )
        
        # 2. Scale fitting stimuli and set up binary classification task
        fitting_stimuli = place_on_screen(
            self._fitting_stimuli,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
        
        # 3. Scale test stimuli and get model predictions
        stimulus_set = place_on_screen(
            self._assembly.stimulus_set,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        model_labels_raw = candidate.look_at(stimulus_set, number_of_trials=self._number_of_trials)
        
        # 4. Process model outputs (softmax + threshold → binary choices)
        model_labels = process_model_choices(model_labels_raw)
        
        # 5. Compute "integral" metric (area under performance curve)
        human_integral = get_integral_data(self._assembly, self._experiment)['integral']
        model_integral = get_integral_data(model_labels, self._experiment)['integral']
        
        # 6. Compare integrals using Value Delta metric
        raw_score = self._metric(model_integral, human_integral)
        
        # 7. Normalize by ceiling (clamp to [0, 1])
        ceiling = self._ceiling
        score = Score(min(max(raw_score / ceiling, 0), 1))
        score.attrs['raw'] = raw_score
        score.attrs['ceiling'] = ceiling
        
        return score
```

**Key patterns in Ferguson2024:**
- **Multiple experiment variants**: Same benchmark structure, different stimulus types
- **Pre-computed ceilings**: Stored to avoid expensive recalculation
- **Custom post-processing**: Converts probabilities to discrete choices
- **Derived metric**: Computes "integral" from raw responses before comparison

---

## Behavioral Benchmark Call Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  INSIDE behavioral_benchmark.__call__(candidate)                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: Scale FITTING stimuli                                               │
│                                                                              │
│  fitting_stimuli = place_on_screen(self._fitting_stimuli, ...)               │
│      └──→ Training data for model's readout layer                            │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 2: Configure task with fitting stimuli                                 │
│                                                                              │
│  candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)        │
│      │                                                                       │
│      │  Model internally:                                                    │
│      │  1. Extracts features from fitting_stimuli                            │
│      │  2. Trains logistic regression: features → image_label                │
│      │  3. Stores classifier for later use                                   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 3: Scale TEST stimuli                                                  │
│                                                                              │
│  stimulus_set = place_on_screen(self._assembly.stimulus_set, ...)            │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4: Get model predictions                                               │
│                                                                              │
│  probabilities = candidate.look_at(stimulus_set, number_of_trials=N)         │
│      │                                                                       │
│      │  Model internally:                                                    │
│      │  1. Extracts features from test stimuli                               │
│      │  2. Applies trained classifier to get probabilities                   │
│      │  3. Returns BehavioralAssembly with shape (stimuli, classes)          │
│      │                                                                       │
│      └──→ Returns BehavioralAssembly: (presentations × choices)              │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 5: Compare to human data using behavioral metric                       │
│                                                                              │
│  raw_score = self._metric(probabilities, self._assembly)                     │
│      └──→ I2N: per-image consistency                                         │
│           Accuracy: proportion correct                                       │
│           Value Delta: scalar comparison                                     │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 6: Normalize by ceiling                                                │
│                                                                              │
│  score = raw_score / ceiling  (or custom normalization)                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Differences from Neural Benchmarks

| Aspect | Neural Benchmark | Behavioral Benchmark |
|--------|------------------|---------------------|
| Helper class | `NeuralBenchmark` | None (use `BenchmarkBase`) |
| Model setup | `start_recording(region, time_bins)` | `start_task(task, fitting_stimuli)` |
| Output | `NeuroidAssembly` (activations) | `BehavioralAssembly` (choices) |
| Fitting data | Not needed | Usually required |
| Implement `__call__` | No (inherited) | **Yes (required)** |

---

## Behavioral Metrics

### I2N (Image-Level Consistency)

Measures whether model and humans make the same errors on the *same individual images*:

```
                          Model A        Model B        Humans
                          (90% acc)      (90% acc)      
Image 1 (dog vs cat)        ✓              ✗              ✓
Image 2 (car vs bus)        ✓              ✓              ✓
Image 3 (bird vs plane)     ✗              ✓              ✗    ← Model A matches human error!
Image 4 (dog vs wolf)       ✓              ✗              ✓
Image 5 (cat vs tiger)      ✗              ✗              ✗    ← Both match human error
...

I2N(Model A, Humans) = 0.85   ← High: same error patterns
I2N(Model B, Humans) = 0.45   ← Low: different error patterns

Using simple Accuracy would miss this distinction.
```

```python
# Located: brainscore_vision/metrics/i1i2/metric.py

class _I(_Behavior_Metric):
    """
    I2n: Image-level, object-level normalized behavioral similarity.
    """
    
    def __call__(self, source_probabilities, target) -> Score:
        return self._repeat(lambda random_state:
                            self._call_single(source_probabilities, target, random_state))

    def _call_single(self, source_probabilities, target, random_state):
        # 1. Build "response matrix" from model probabilities
        source_response_matrix = self.target_distractor_scores(source_probabilities)
        
        # 2. Convert to d-prime (sensitivity) scores
        source_response_matrix = self.dprimes(source_response_matrix)
        
        # 3. Build response matrix from human data
        target_half = self.generate_halves(target, random_state)[0]
        target_response_matrix = self.build_response_matrix_from_responses(target_half)
        target_response_matrix = self.dprimes(target_response_matrix)
        
        # 4. Correlate the two response matrices (per-image patterns)
        correlation = self.correlate(source_response_matrix, target_response_matrix)
        return correlation

    def ceiling(self, assembly):
        """How well do humans predict other humans? (split-half reliability)"""
        half1, half2 = self.generate_halves(assembly)
        rm1 = self.dprimes(self.build_response_matrix_from_responses(half1))
        rm2 = self.dprimes(self.build_response_matrix_from_responses(half2))
        return self.correlate(rm1, rm2)
```

---

### RDM/RSA (Representational Similarity Analysis)

Compares the *structure* of representations:

```python
# Located: brainscore_vision/metrics/rdm/metric.py

class RDMMetric(Metric):
    def __call__(self, assembly1: NeuroidAssembly, assembly2: NeuroidAssembly) -> Score:
        # 1. Build RDM for each assembly: (stimuli × neuroids) → (stimuli × stimuli)
        rdm1 = self._rdm(assembly1)
        rdm2 = self._rdm(assembly2)
        
        # 2. Compare the two RDMs using Spearman correlation
        similarity = self._similarity(rdm1, rdm2)
        return Score(similarity)
```

**Pipeline visualization**:

```
Model Activations              Human fMRI Activations
(stimuli × neurons)            (stimuli × voxels)
       │                              │
       ▼                              ▼
   ┌───────────┐                 ┌───────────┐
   │   RDM     │                 │   RDM     │
   │ stimuli × │                 │ stimuli × │
   │  stimuli  │                 │  stimuli  │
   └───────────┘                 └───────────┘
       │                              │
       └──────────┬───────────────────┘
                  ▼
         Spearman correlation
         (upper triangulars)
                  │
                  ▼
              Score: 0.65
```

---

### Value Delta (Scalar Comparison)

Compares two scalar values using a sigmoid-weighted distance:

```python
# Located: brainscore_vision/metrics/value_delta/metric.py

class ValueDelta(Metric):
    def __init__(self, scale: float = 1.00):
        self.scale = scale

    def __call__(self, source_value: float, target_value: float) -> Score:
        # Compute absolute difference
        abs_diff = float(np.abs(source_value - target_value))
        
        # Apply sigmoid: identical values → 1.0, large differences → 0.0
        center = 1 / (np.exp(self.scale * abs_diff))
        center = min(max(center, 0), 1)
        
        score = Score(center)
        score.attrs['error'] = np.nan
        score.attrs[Score.RAW_VALUES_KEY] = [source_value, target_value]
        return score
```

---

## Implementing Your Own Behavioral Benchmark

```python
from brainscore_vision.benchmarks import BenchmarkBase
from brainscore_vision import load_stimulus_set, load_dataset, load_metric
from brainscore_vision.benchmark_helpers.screen import place_on_screen
from brainscore_vision.model_interface import BrainModel
from brainscore_core.metrics import Score

BIBTEX = """
@article{author2024,
  title={Your Paper Title},
  author={Author, A.},
  journal={Journal},
  year={2024}
}
"""

class MyBehavioralBenchmark(BenchmarkBase):
    def __init__(self):
        # Load data
        self._assembly = load_dataset('MyExperiment2024')
        self._fitting_stimuli = load_stimulus_set('MyExperiment2024_fitting')
        self._stimulus_set = load_stimulus_set('MyExperiment2024')
        
        # Set up metric
        self._metric = load_metric('accuracy')  # or 'i2n', etc.
        
        # Experimental parameters
        self._visual_degrees = 8
        self._number_of_trials = 1
        
        super().__init__(
            identifier='MyExperiment2024-accuracy',
            version=1,
            ceiling_func=lambda: self._compute_ceiling(),
            parent='behavior',
            bibtex=BIBTEX
        )
    
    def __call__(self, candidate: BrainModel) -> Score:
        # 1. Scale fitting stimuli
        fitting_stimuli = place_on_screen(
            self._fitting_stimuli,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        
        # 2. Set up task
        candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
        
        # 3. Scale test stimuli
        stimulus_set = place_on_screen(
            self._stimulus_set,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        
        # 4. Get model predictions
        predictions = candidate.look_at(stimulus_set, number_of_trials=self._number_of_trials)
        
        # 5. Compare to human data
        raw_score = self._metric(predictions, self._assembly)
        
        # 6. Normalize by ceiling
        ceiling = self.ceiling
        ceiled_score = raw_score / ceiling
        ceiled_score.attrs['raw'] = raw_score
        ceiled_score.attrs['ceiling'] = ceiling
        
        return ceiled_score
    
    def _compute_ceiling(self) -> Score:
        """Split-half reliability across subjects."""
        subjects = list(set(self._assembly.coords['subject'].values))
        scores = []
        
        for _ in range(100):  # Bootstrap
            np.random.shuffle(subjects)
            half1 = subjects[:len(subjects)//2]
            half2 = subjects[len(subjects)//2:]
            
            data1 = self._assembly.sel(presentation=self._assembly['subject'].isin(half1))
            data2 = self._assembly.sel(presentation=self._assembly['subject'].isin(half2))
            
            score = self._metric(data1.mean('subject'), data2.mean('subject'))
            scores.append(score.values)
        
        ceiling = Score(np.mean(scores))
        ceiling.attrs['error'] = np.std(scores)
        return ceiling
```

---

## Registration

```python
# __init__.py
from brainscore_vision import benchmark_registry
from .benchmark import MyBehavioralBenchmark

benchmark_registry['MyExperiment2024-accuracy'] = MyBehavioralBenchmark
```

---

## Behavioral Benchmark Checklist

Before submitting your behavioral benchmark:

- [ ] Inherits from `BenchmarkBase` directly (not a helper class)
- [ ] Implements `__call__` method
- [ ] Uses fitting stimuli separate from test stimuli
- [ ] Uses `start_task()` to configure behavioral task
- [ ] Implements ceiling calculation (split-half or cross-subject)
- [ ] Includes proper `bibtex` citation
- [ ] Tests verify expected scores for known models

---

## Behavioral Benchmark Patterns

- **Probabilities task**: Most common for fine-grained behavioral comparisons
- **Fitting stimuli**: Always provide separate training data for fair comparison
- **Chance correction**: Account for random performance baselines (e.g., 1/N for N-way choice)
- **Subject variability**: Handle individual differences appropriately in ceiling calculations

```python
# Chance-corrected scoring
chance_level = 1 / n_choices
raw_accuracy = compute_accuracy(model_choices, human_choices)
corrected_score = (raw_accuracy - chance_level) / (ceiling - chance_level)
```

---

## Next Steps

- **[Vision vs Language](/tutorials/benchmarks/vision-vs-language/)** — Differences between vision and language benchmarks

