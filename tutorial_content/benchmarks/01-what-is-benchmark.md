---
title: What is a Benchmark?
description: Understanding the fundamentals of Brain-Score benchmarks
order: 1
category: benchmarks
---

# What is a Benchmark?

A **benchmark** is a standardized scientific test that evaluates how well an artificial neural network model aligns with biological intelligence. At its core, a benchmark:

1. **Reproduces an experiment** on an artificial model using the same stimuli and protocol as the original biological experiment
2. **Compares model responses** to biological measurements using appropriate metrics
3. **Normalizes scores** using data ceilings to account for measurement noise and variability
4. **Returns a score** between 0 and 1, where 1 indicates ceiling-level performance

---

## The Brain-Score Philosophy

Brain-Score operates on the principle that AI systems should be evaluated not just on engineering metrics (accuracy, efficiency) but on their alignment with biological intelligence. This requires:

- **Biological grounding**: All benchmarks must be based on actual neuroscience or psychology experiments
- **Standardized protocols**: Consistent experimental procedures across models
- **Statistical rigor**: Proper controls, ceilings, and error estimation
- **Reproducibility**: Clear data provenance and versioning

---

## Components of a Benchmark

Every benchmark is built from four essential components:

```
┌──────────────────────────────────────────────────────────────────┐
│                         BENCHMARK                                │
├──────────────────────────────────────────────────────────────────┤
│  1. STIMULUS SET                                                 │
│     • Collection of experimental stimuli (images, text, etc.)    │
│     • Metadata about each stimulus                               │
|     • What is the model's input?                                 |
│                                                                  │
│  2. DATA ASSEMBLY                                                │
│     • Biological measurements (neural or behavioral)             │
│     • Experimental conditions and subject information            │
|     • What is the model comparing against?                       |
│                                                                  │
│  3. METRIC                                                       │
│     • Statistical comparison method                              │
│     • Defines how similarity is quantified                       │
|     • How are we comparing the model and the subject?            |
│                                                                  │
│  4. CEILING                                                      │
│     • Maximum expected performance given noise                   │
│     • Enables score normalization                                │
|     • How well could a model theoretically do?                   |
└──────────────────────────────────────────────────────────────────┘
```

---

## The Benchmark Interface

Every benchmark implements the `Benchmark` interface:

```python
# Located: core/brainscore_core/benchmarks/__init__.py

class Benchmark(ABC):
    def __call__(self, candidate: BrainModel) -> Score:
        """Evaluate a model and return normalized score"""
        
    @property
    def identifier(self) -> str:
        """Unique benchmark identifier: <data>-<metric>"""
        
    @property
    def ceiling(self) -> Score:
        """Data ceiling for score normalization"""
        
    @property
    def version(self) -> str:
        """Version number (increment when scores change)"""

    @property
    def parent(self) -> str:
        """Identifier for the parent of this benchmark"""
        
    @property
    def bibtex(self) -> str:
        """Citation information"""
```

---

## BenchmarkBase Helper Class

Most benchmarks inherit from `BenchmarkBase`, which provides:

- Automatic caching of ceiling calculations
- Standard score normalization via the `ceil_score` function
- Version and metadata management
- Bibtex handling

```python
# Located: core/brainscore_core/benchmarks/__init__.py (BenchmarkBase)
#          vision/brainscore_vision/benchmarks/__init__.py (imports and extends)

from brainscore_vision.benchmarks import BenchmarkBase

class MyBenchmark(BenchmarkBase):
    def __init__(self):
        super().__init__(
            identifier='MyExperiment2024-accuracy',
            version=1,
            ceiling_func=lambda: self._compute_ceiling(),
            parent='behavior',  # or 'neural', 'V1', 'IT', etc.
            bibtex=BIBTEX_STRING
        )
```

---

## Model Interface Integration

Benchmarks interact with models through the `BrainModel` interface, which abstracts model implementation details:

| Method | Purpose |
|--------|---------|
| `start_task()` | Defines what the model should do |
| `start_recording()` | Specifies neural recording locations/timing |
| `look_at()` | Presents stimuli and collects responses |
| `visual_degrees()` | Handles stimulus scaling |

---

## How Brain-Score Executes Benchmarks

When a benchmark's `__call__` method is invoked:

```python
def __call__(self, candidate: BrainModel):
    # 1. Configure the model for the task
    #    Neural: candidate.start_recording(region, time_bins)
    #    Behavioral: candidate.start_task(task, fitting_stimuli)
    
    # 2. Scale stimuli to match model's visual field
    stimulus_set = place_on_screen(
        self._stimulus_set,
        target_visual_degrees=candidate.visual_degrees(),
        source_visual_degrees=self._visual_degrees
    )
    
    # 3. Present stimuli and collect model responses
    model_response = candidate.look_at(stimulus_set, number_of_trials=N)
    
    # 4. Compare model responses to biological data using the metric
    raw_score = self._metric(model_response, self._assembly)
    
    # 5. Normalize by ceiling
    ceiled_score = raw_score / self.ceiling
    
    return ceiled_score
```

For more details on the call flow during scoring, see [Neural Benchmark Call Flow](/tutorials/benchmarks/neural-benchmarks/#neural-benchmark-call-flow) and [Behavioral Benchmark Call Flow](/tutorials/benchmarks/behavioral-benchmarks/#behavioral-benchmark-call-flow).

---

## Task Types

Brain-Score supports several behavioral task types that enable models to perform cognitive tasks. These are defined in `vision/brainscore_vision/model_interface.py` and implemented in `vision/brainscore_vision/model_helpers/brain_transformation/behavior.py`.

### 1. Passive Task (`BrainModel.Task.passive`)
- **Purpose**: Passive fixation without explicit behavioral output
- **Use Case**: Neural recording benchmarks where only internal representations matter
- **Output**: None (used for neural analysis only)

### 2. Label Task (`BrainModel.Task.label`)
- **Purpose**: Discrete categorization—predict single labels for stimuli
- **Output**: `BehavioralAssembly` with predicted labels

```python
candidate.start_task(BrainModel.Task.label, ['dog', 'cat', 'car'])
predictions = candidate.look_at(stimulus_set)
```

### 3. Probabilities Task (`BrainModel.Task.probabilities`)
- **Purpose**: Multi-class probability estimation with learned readouts
- **Output**: `BehavioralAssembly` with probability distributions

```python
fitting_stimuli = load_stimulus_set('training_data')
candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
probabilities = candidate.look_at(test_stimuli)
```

### 4. Odd-One-Out Task (`BrainModel.Task.odd_one_out`)
- **Purpose**: Similarity-based judgments—identify the dissimilar item in triplets
- **Output**: `BehavioralAssembly` with choice indices (0, 1, or 2)

```python
candidate.start_task(BrainModel.Task.odd_one_out)
choices = candidate.look_at(triplet_stimuli)
```


---

## Metrics Overview

**Metrics** are the statistical heart of Brain-Score, defining *how* we compare artificial neural networks to biological intelligence.

### The Metric Interface

All Brain-Score metrics implement a simple interface:

```python
# Located: core/brainscore_core/metrics/__init__.py

from brainscore_core.metrics import Metric, Score

class Metric:
    def __call__(self, assembly1: DataAssembly, assembly2: DataAssembly) -> Score:
        """Compare two assemblies and return similarity score."""
        raise NotImplementedError()
```

### Categories of Metrics

| Category | Examples | When to Use |
|----------|----------|-------------|
| **Regression-Based** | PLS, Ridge | Neural data with high dimensionality |
| **Correlation** | Pearson, Spearman | Simple linear/monotonic relationships |
| **Behavioral** | Accuracy, I2N | Choice patterns and response distributions |
| **Specialized** | Threshold, Value Delta | Psychophysical experiments, scalar comparisons |

For detailed metric examples and selection guidance, see the [Neural Benchmarks](/tutorials/benchmarks/neural-benchmarks/) and [Behavioral Benchmarks](/tutorials/benchmarks/behavioral-benchmarks/) tutorials.

---

## Score Objects

`Score` objects extend simple numbers with rich metadata:

```python
# Located: core/brainscore_core/metrics/__init__.py

from brainscore_core.metrics import Score
import numpy as np

raw_values = np.array([0.8, 0.7, 0.9, 0.6])
score = Score(np.mean(raw_values))

# Add metadata
score.attrs['error'] = np.std(raw_values)
score.attrs['n_comparisons'] = len(raw_values)
score.attrs['raw'] = raw_values
score.attrs['method'] = 'pearson_correlation'

print(f"Score: {score.values:.3f} ± {score.attrs['error']:.3f}")
```

### Score Interpretation

| Score Range | Interpretation |
|-------------|----------------|
| 1.0 | Perfect (ceiling-level performance) |
| 0.8 - 0.99 | Very high similarity |
| 0.6 - 0.79 | Good similarity |
| 0.4 - 0.59 | Moderate similarity |
| 0.2 - 0.39 | Low similarity |
| 0.0 - 0.19 | Very low similarity |

### Score Structure

For benchmarks to correctly write both `score_raw` (unceiled) and `score_ceiled` to the database, the returned `Score` object must have specific attributes.

#### Required Attributes for Non-Engineering Benchmarks

```python
# The main score object contains the ceiled value
score = Score(ceiled_value)

# Required attributes (must be scalar Score objects)
score.attrs['ceiling'] = Score(ceiling_value)           # Triggers non-engineering benchmark handling
score.attrs[Score.RAW_VALUES_KEY] = Score(raw_value)    # The unceiled score
```

**Critical Requirements:**
- `'ceiling'` must be present in `score.attrs` for non-engineering benchmarks
- Both `ceiling` and `raw` must be `Score` objects containing **scalar values** (compatible with `.item()`)
- Arrays will cause database writes to fail with: `"can only convert an array of size 1 to a Python scalar"`

> ⚠️ **Note:** If `'ceiling'` is missing from `score.attrs`, the benchmark is treated as an engineering benchmark and only `score_raw` is written to the database (`score_ceiled` remains `NULL`).

---

## Understanding Ceilings

**Ceilings** represent the maximum expected performance given measurement noise and biological variability. **"How well should we expect the best possible model to score?"**

### Why Ceilings Are Critical

1. **Noise Control**: Biological measurements contain noise that limits perfect prediction
2. **Fair Comparison**: Models shouldn't be penalized for measurement limitations
3. **Interpretability**: Ceiling-normalized scores are interpretable (1.0 = perfect within noise limits)
4. **Statistical Validity**: Proper statistical inference requires noise estimates

> ⚠️ **Critical**: A benchmark without a ceiling is not interpretable. Always implement `ceiling_func`.

### Types of Ceilings

| Type | Method | Use Case |
|------|--------|----------|
| Internal Consistency | Split-half reliability | Repeated measurements of same stimuli |
| Cross-Validation | Leave-one-out across subjects | Comparing across individuals |
| Bootstrap | Resample data | Robust noise estimates with limited data |
| Temporal | Account for alignment uncertainty | Temporal benchmarks with timing variability |

### Example: Internal Consistency Ceiling

```python
def get_ceiling(assembly: NeuroidAssembly) -> Score:
    # Split data into halves
    half1 = assembly.isel(repetition=slice(0, len(assembly.repetition)//2))
    half2 = assembly.isel(repetition=slice(len(assembly.repetition)//2, None))
    
    # Calculate split-half reliability
    ceiling = pearson_correlation(half1.mean('repetition'), half2.mean('repetition'))
    return ceiling
```

---

## Next Steps

Now that you understand what a benchmark is, continue to:

1. **[Data Packaging](/tutorials/benchmarks/data-packaging/)** — Learn how to package your experimental data
2. **[Neural Benchmarks](/tutorials/benchmarks/neural-benchmarks/)** — Create benchmarks comparing model activations to neural recordings
3. **[Behavioral Benchmarks](/tutorials/benchmarks/behavioral-benchmarks/)** — Create benchmarks comparing model behavior to human behavior


