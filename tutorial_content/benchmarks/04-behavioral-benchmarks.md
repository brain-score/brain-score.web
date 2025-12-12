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

> **Why no helper class?** As covered in [Data Packaging](/tutorials/benchmarks/data-packaging/), `BehavioralAssembly` has no enforced dimensions—behavioral data can be 1D (correct/incorrect), 2D (probability distributions), or other shapes. This flexibility means behavioral experiments are too diverse for a single abstraction like `NeuralBenchmark`.

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

<details>
<summary><strong>Click to expand: Behavioral benchmark execution flow</strong></summary>

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

</details>

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

Behavioral benchmarks use diverse metrics to capture different aspects of human-model alignment. Here's an overview of the most common ones:

### Metric Comparison Table

| Metric | Registry Key | What It Measures | When to Use |
|--------|-------------|------------------|-------------|
| **Accuracy** | `accuracy` | Proportion of correct responses | Simple classification tasks |
| **I2N** | `i2n` | Image-level error pattern consistency | Fine-grained behavioral similarity |
| **Error Consistency** | `error_consistency` | Cohen's Kappa for error agreement | When error patterns matter more than accuracy |
| **Accuracy Distance** | `accuracy_distance` | Relative distance between accuracies | Condition-wise performance matching |
| **Value Delta** | `value_delta` | Sigmoid-weighted scalar comparison | Comparing derived metrics (e.g., integrals) |
| **OST** | `ost` | Object Solution Time correlation | Temporal dynamics of recognition |

> **Note**: All paths below are relative to `brainscore_vision/metrics/` in the vision repository.

---

### Accuracy

The simplest metric — proportion of matching responses:

```python
# Located: metrics/accuracy/metric.py

class Accuracy(Metric):
    def __call__(self, source, target) -> Score:
        values = source == target
        center = np.mean(values)
        score = Score(center)
        score.attrs['error'] = np.std(values)
        return score
```

**When to use**: Basic classification accuracy when you just need "how often does the model get it right?"

---

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

Accuracy would miss this distinction — both models score 90%!
```

```python
# Located: metrics/i1i2/metric.py

class _I(_Behavior_Metric):
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
```

**When to use**: When you care about *which specific images* are hard, not just overall accuracy.

---

### Error Consistency (Cohen's Kappa)

Measures agreement in error patterns, accounting for chance:

```python
# Located: metrics/error_consistency/metric.py

class ErrorConsistency(Metric):
    """
    Implements Cohen's Kappa from Geirhos et al., 2020
    https://arxiv.org/abs/2006.16736
    """
    def compare_single_subject(self, source, target):
        correct_source = source.values == source['truth'].values
        correct_target = target.values == target['truth'].values
        
        # Expected consistency by chance
        accuracy_source = np.mean(correct_source)
        accuracy_target = np.mean(correct_target)
        expected = accuracy_source * accuracy_target + (1 - accuracy_source) * (1 - accuracy_target)
        
        # Observed consistency
        observed = (correct_source == correct_target).sum() / len(target)
        
        # Cohen's Kappa: adjust for chance
        kappa = (observed - expected) / (1.0 - expected)
        return Score(kappa)
```

**When to use**: When comparing error patterns across different conditions (e.g., shape vs. texture experiments).

---

### Accuracy Distance

Compares accuracy patterns across experimental conditions:

```python
# Located: metrics/accuracy_distance/metric.py

class AccuracyDistance(Metric):
    """
    Measures relative distance between source and target accuracies,
    adjusted for maximum possible difference.
    """
    def compare_single_subject(self, source, target):
        source_correct = source.values.flatten() == target['truth'].values
        target_correct = target.values == target['truth'].values
        
        source_mean = np.mean(source_correct)
        target_mean = np.mean(target_correct)
        
        # Normalize by maximum possible distance
        maximum_distance = max(1 - target_mean, target_mean)
        relative_distance = 1 - abs(source_mean - target_mean) / maximum_distance
        
        return Score(relative_distance)
```

**When to use**: When you want to compare performance *patterns* across conditions, not just overall accuracy.

---

### Value Delta (Scalar Comparison)

Compares two scalar values using a sigmoid-weighted distance:

```python
# Located: metrics/value_delta/metric.py

class ValueDelta(Metric):
    def __init__(self, scale: float = 1.00):
        self.scale = scale

    def __call__(self, source_value: float, target_value: float) -> Score:
        # Compute absolute difference
        abs_diff = float(np.abs(source_value - target_value))
        
        # Apply sigmoid: identical values → 1.0, large differences → 0.0
        center = 1 / (np.exp(self.scale * abs_diff))
        
        return Score(min(max(center, 0), 1))
```

**When to use**: When comparing derived metrics like integrals, thresholds, or other scalar summaries.

---

### OST (Object Solution Times)

Measures whether models predict the *temporal dynamics* of human object recognition:

```python
# Located: metrics/ost/metric.py

class OSTCorrelation(Metric):
    """
    Object Solution Times metric from Kar et al., Nature Neuroscience 2019.
    Tests whether models predict WHEN object identity emerges.
    """
    def compute_osts(self, train_source, test_source, test_osts):
        # For each time bin, train classifier and check if threshold is reached
        for time_bin_start in sorted(set(train_source['time_bin_start'].values)):
            # Train classifier at this time point
            classifier.fit(time_train_source, time_train_source['image_label'])
            prediction_probabilities = classifier.predict_proba(time_test_source)
            
            # Check if model reaches human-like performance threshold
            source_i1 = self.i1(prediction_probabilities)
            # ... interpolate to find exact crossing time
        
        return predicted_osts
    
    def correlate(self, predicted_osts, target_osts):
        # Spearman correlation: do models predict which images are "hard"?
        correlation, p = spearmanr(predicted_osts, target_osts)
        return Score(correlation)
```

**When to use**: When testing recurrent/temporal models on time-resolved behavioral data.

---

### Choosing the Right Behavioral Metric

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Decision Guide: Which Behavioral Metric?                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Q: What aspect of behavior do you want to compare?                         │
│                                                                             │
│  ├── Overall correctness → Accuracy                                         │
│  │                                                                          │
│  ├── Which specific images are hard/easy → I2N                              │
│  │                                                                          │
│  ├── Error patterns (accounting for chance) → Error Consistency             │
│  │                                                                          │
│  ├── Performance across conditions → Accuracy Distance                      │
│  │                                                                          │
│  ├── Derived scalar values (integrals, thresholds) → Value Delta            │
│  │                                                                          │
│  └── When recognition happens (temporal) → OST                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
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

## Benchmark Hierarchy

The `parent` parameter determines where your benchmark appears in the leaderboard:

```python
super().__init__(
    identifier='Ferguson2024tilted_line-value_delta',
    parent='behavior',  # Groups under behavioral benchmarks
    ...
)
```

| Parent Value | Leaderboard Position |
|--------------|---------------------|
| `'behavior'` | Under behavioral benchmarks |
| `'V1'`, `'IT'`, etc. | Under brain region (for neural-behavioral hybrids) |

**Pre-defined categories** (`V1`, `V2`, `V4`, `IT`, `behavior`) are registered in the Brain-Score database. Your benchmark's `parent` links to one of these existing categories.

The website automatically aggregates scores from benchmarks sharing the same `parent`.

---

## Registration

```python
# __init__.py
from brainscore_vision import benchmark_registry
from .benchmark import MyBehavioralBenchmark

benchmark_registry['MyExperiment2024-accuracy'] = MyBehavioralBenchmark
```

---

## Fitting Stimuli Requirements

Fitting stimuli are training data that the model uses to learn task-specific readouts. Whether you need them depends on the task type:

| Task Type | Fitting Stimuli Required? | Why | Example |
|-----------|---------------------------|-----|---------|
| `BrainModel.Task.probabilities` | **Yes** | Model needs labeled examples to train a classifier | Object categorization |
| `BrainModel.Task.label` | No | Uses model's pre-trained label outputs | ImageNet classification |
| `BrainModel.Task.odd_one_out` | No | Compares feature similarities directly | Triplet similarity |

**Important**: Fitting stimuli should be **separate** from test stimuli to ensure fair evaluation. The model learns from fitting stimuli, then is tested on unseen test stimuli.

```python
# Good: Separate fitting and test sets
self._fitting_stimuli = load_stimulus_set('MyExperiment2024_training')
self._test_stimuli = load_stimulus_set('MyExperiment2024_test')

# Bad: Using the same stimuli for both
self._fitting_stimuli = self._test_stimuli  # Don't do this!
```

---

## Testing Your Benchmark

Every benchmark should include tests to verify it loads and produces expected scores:

```python
# vision/brainscore_vision/benchmarks/myexperiment2024/test.py

import pytest
from brainscore_vision import load_benchmark, load_model

@pytest.mark.private_access
class TestMyBehavioralBenchmark:
    def test_benchmark_loads(self):
        """Test that benchmark can be loaded"""
        benchmark = load_benchmark('MyExperiment2024-accuracy')
        assert benchmark is not None
        assert benchmark.identifier == 'MyExperiment2024-accuracy'
    
    def test_ceiling_valid(self):
        """Test ceiling is computed and in valid range"""
        benchmark = load_benchmark('MyExperiment2024-accuracy')
        ceiling = benchmark.ceiling
        assert 0 < ceiling <= 1, f"Ceiling {ceiling} out of expected range"
    
    def test_benchmark_score(self):
        """Test benchmark produces expected score for a known model"""
        benchmark = load_benchmark('MyExperiment2024-accuracy')
        model = load_model('alexnet')
        
        score = benchmark(model)
        
        # Document expected score for regression testing
        assert 0 <= score <= 1
        assert hasattr(score, 'attrs')
        # Optional: assert abs(score - 0.35) < 0.05  # Expected ~0.35 for alexnet
```

---

## Common Issues and Solutions

#### Problem: "Model predictions have wrong shape"

The model output doesn't match expected dimensions for the task.

```python
# Solution: Verify task type matches expected output
# For probabilities task, output should be (presentations × choices)
candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
predictions = candidate.look_at(stimulus_set)
print(f"Shape: {predictions.shape}, Dims: {predictions.dims}")
```

#### Problem: "Fitting stimuli labels don't match test stimuli"

The `image_label` column values are inconsistent between fitting and test sets.

```python
# Solution: Ensure consistent labeling
fitting_labels = set(fitting_stimuli['image_label'].unique())
test_labels = set(test_stimuli['image_label'].unique())
assert fitting_labels == test_labels, f"Label mismatch: {fitting_labels} vs {test_labels}"
```

#### Problem: "Ceiling calculation takes too long"

Split-half bootstrapping with many iterations is slow.

```python
# Solution: Pre-compute ceiling and store the value
# Calculate once:
ceiling_value = self._compute_ceiling()
print(f"Pre-computed ceiling: {ceiling_value}")

# Then use the value directly:
ceiling_func=lambda: Score(0.85)  # Use pre-computed value
```

#### Problem: "Score exceeds 1.0 or is negative"

Ceiling normalization isn't clamping properly.

```python
# Solution: Clamp the final score
raw_score = self._metric(predictions, self._assembly)
ceiling = self.ceiling
ceiled_score = min(max(raw_score / ceiling, 0), 1)  # Clamp to [0, 1]
```

#### Problem: "start_task fails with unknown task"

Task type not recognized by the model.

```python
# Solution: Use standard task types
from brainscore_vision.model_interface import BrainModel

# Valid tasks:
BrainModel.Task.passive        # Neural recording only
BrainModel.Task.label          # Discrete labels
BrainModel.Task.probabilities  # Probability distributions
BrainModel.Task.odd_one_out    # Similarity-based choices
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


