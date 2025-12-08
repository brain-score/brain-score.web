---
title: Neural Benchmarks
description: Creating benchmarks that compare model activations to neural recordings
order: 3
category: benchmarks
---

# Neural Benchmarks

Neural benchmarks compare model neural representations to biological neural recordings from experiments measuring brain activity (fMRI, electrophysiology, EEG, etc.).

---

## Overview

| Benchmark | Description | Brain Region | Key Features |
|-----------|-------------|--------------|--------------|
| `MajajHong2015` | IT and V4 neural responses to object images | V4, IT | PLS metric, 8° visual degrees, 50 trials |
| `FreemanZiemba2013` | Neural responses to texture and natural images | V1, V2 | Early visual cortex, texture processing |
| `Kar2019` | IT responses with object solution times | IT | Temporal dynamics, recurrent processing |

**Key Characteristics**:
- Use `NeuroidAssembly` data structures
- Employ regression-based metrics (PLS, Ridge)
- Support temporal dynamics
- Compare across brain regions (V1, V2, V4, IT)

---

## Inheritance Structure

Neural benchmarks use the `NeuralBenchmark` helper class, which is part of a three-level hierarchy:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Benchmark (ABC)                                                     │
│  ├── Abstract interface defining required methods                   │
│  ├── __call__(candidate) → Score                                    │
│  ├── identifier, ceiling, version, bibtex properties                │
│  └── Located: brainscore_vision.benchmarks.Benchmark                │
├─────────────────────────────────────────────────────────────────────┤
│  BenchmarkBase(Benchmark)                                           │
│  ├── Helper class implementing standard functions                   │
│  ├── Automatic ceiling caching                                      │
│  ├── Version and metadata management                                │
│  └── Located: brainscore_vision.benchmarks.BenchmarkBase            │
├─────────────────────────────────────────────────────────────────────┤
│  NeuralBenchmark(BenchmarkBase)                                     │
│  ├── Specialized for neural recording comparisons                   │
│  ├── Handles: start_recording(), place_on_screen(), time bins       │
│  ├── Built-in explained_variance ceiling normalization              │
│  └── Located: brainscore_vision.benchmark_helpers.neural_common     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## What NeuralBenchmark Provides

When you use the `NeuralBenchmark` helper class, you get these features automatically:

- Calls `candidate.start_recording(region, time_bins)` to set up neural recording
- Scales stimuli to model's visual field via `place_on_screen()`
- Squeezes single time bins for static benchmarks
- Normalizes scores using `explained_variance(raw_score, ceiling)`

**Key insight**: You don't need to implement `__call__`, call `look_at`, or load a stimulus set—`NeuralBenchmark` handles all of that internally.

---

## Example: MajajHong2015

Here's the complete structure of a neural benchmark using `NeuralBenchmark`:

```python
from brainscore_vision.benchmark_helpers.neural_common import NeuralBenchmark
from brainscore_vision import load_metric, load_ceiling

def _DicarloMajajHong2015Region(region: str, access: str, identifier_metric_suffix: str,
                                similarity_metric: Metric, ceiler: Ceiling):
    # Load data WITH individual repetitions (for ceiling calculation)
    assembly_repetition = load_assembly(average_repetitions=False, region=region)
    # Load data with repetitions AVERAGED (for model comparison)
    assembly = load_assembly(average_repetitions=True, region=region)
    
    return NeuralBenchmark(
        # Unique identifier: <dataset>.<region>-<metric> (e.g., "MajajHong2015.IT-pls")
        identifier=f'MajajHong2015.{region}-{identifier_metric_suffix}',
        
        # Version number: increment when benchmark changes would affect scores
        version=3,
        
        # Neural data assembly: the biological recordings to compare against
        # Uses averaged repetitions for cleaner model-to-brain comparison
        assembly=assembly,
        
        # Metric for comparing model activations to neural recordings
        # Typically PLS regression for neural benchmarks
        similarity_metric=similarity_metric,
        
        # Size of stimuli in degrees of visual angle (as shown in original experiment)
        # Models must scale their input to match this visual field size
        visual_degrees=8,
        
        # Number of stimulus presentations per image in the original experiment
        # Supports stochastic models; deterministic models return same output each trial
        number_of_trials=50,
        
        # Function to compute the data ceiling (maximum achievable score)
        # Uses NON-averaged data to estimate noise/reliability via split-half
        ceiling_func=lambda: ceiler(assembly_repetition),
        
        # Parent category in benchmark hierarchy (V1, V2, V4, IT, or behavior)
        # Determines where this benchmark appears in the leaderboard tree
        parent=region,
        
        # BibTeX citation for the original neuroscience paper
        bibtex=BIBTEX
    )


# Factory function that creates the benchmark
def DicarloMajajHong2015ITPLS():
    ceiler = load_ceiling('internal_consistency')
    return _DicarloMajajHong2015Region(
        region='IT',
        access='public', 
        identifier_metric_suffix='pls',
        similarity_metric=load_metric('pls'),
        ceiler=ceiler
    )
```

---

## The Internal Consistency Ceiling

For neural benchmarks, the ceiling is typically computed using `internal_consistency`:

```python
from brainscore_vision import load_ceiling

ceiler = load_ceiling('internal_consistency')
benchmark = _DicarloMajajHong2015Region(
    region='IT',
    access='public', 
    identifier_metric_suffix='pls',
    similarity_metric=load_metric('pls'),
    ceiler=ceiler
)
```

The ceiling answers: "How well can we predict one half of the biological data from the other half?"

This sets the upper bound for any model—if the biological data only correlates 0.8 with itself across trials, a model scoring 0.8 is actually at ceiling.

---

## What Happens Under the Hood

When `NeuralBenchmark.__call__` is invoked:

```python
def __call__(self, candidate: BrainModel):
    # 1. Tell model to record from the target brain region
    candidate.start_recording(self.region, time_bins=self.timebins)
    
    # 2. Scale stimuli to match model's visual field
    stimulus_set = place_on_screen(
        self._assembly.stimulus_set,
        target_visual_degrees=candidate.visual_degrees(),
        source_visual_degrees=self._visual_degrees
    )
    
    # 3. Present stimuli and collect model's neural responses
    source_assembly = candidate.look_at(stimulus_set, number_of_trials=self._number_of_trials)
    
    # 4. Compare model responses to biological recordings using the metric
    raw_score = self._similarity_metric(source_assembly, self._assembly)
    
    # 5. Normalize by ceiling (explained variance)
    ceiled_score = explained_variance(raw_score, self.ceiling)
    
    return ceiled_score
```

---

## Benchmark Call Flow

Understanding how Brain-Score finds and executes benchmarks:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  USER CODE                                                                   │
│                                                                              │
│  score = brainscore_vision.score('alexnet', 'MajajHong2015.IT-pls')          │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: score() in brainscore_vision/__init__.py                            │
│                                                                              │
│  def score(model_identifier, benchmark_identifier):                          │
│      model = load_model(model_identifier)                                    │
│      benchmark = load_benchmark(benchmark_identifier)                        │
│      score = benchmark(model)                                                │
│      return score                                                            │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: load_benchmark() finds the plugin                                   │
│                                                                              │
│  1. Searches ALL __init__.py files in brainscore_vision/benchmarks/          │
│  2. Looks for: benchmark_registry['MajajHong2015.IT-pls']                    │
│  3. Finds match in: benchmarks/majajhong2015/__init__.py                     │
│  4. Imports the module and calls the factory function                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Plugin __init__.py executes                                         │
│                                                                              │
│  # benchmarks/majajhong2015/__init__.py                                      │
│  from brainscore_vision import benchmark_registry                            │
│  from .benchmark import DicarloMajajHong2015ITPLS                            │
│                                                                              │
│  benchmark_registry['MajajHong2015.IT-pls'] = DicarloMajajHong2015ITPLS      │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Benchmark instance created, __call__ executed                       │
│                                                                              │
│  benchmark = NeuralBenchmark(...)  # Instance created with all parameters    │
│  score = benchmark(model)          # __call__ runs the evaluation            │
│  return score                      # Ceiling-normalized Score returned       │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

**What happens inside `benchmark(model)` — Step 6 in detail:**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  INSIDE NeuralBenchmark.__call__(candidate)                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4a: Configure the model for recording                                  │
│                                                                              │
│  candidate.start_recording('IT', time_bins=[(70, 170)])                      │
│      │                                                                       │
│      └──→ "record from IT-mapped layers, return 70-170ms bin"                │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4b: Scale stimuli to model's visual field                              │
│                                                                              │
│  stimulus_set = place_on_screen(                                             │
│      assembly.stimulus_set,           # Original images                      │
│      target_visual_degrees=model.visual_degrees(),  # e.g., 8°               │
│      source_visual_degrees=8          # Original experiment's visual degrees │
│  )                                                                           │
│      │                                                                       │
│      └──→ Images resized/padded so they are at the same visual angle         │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4c: Present stimuli and extract activations                            │
│                                                                              │
│  source_assembly = candidate.look_at(stimulus_set, number_of_trials=50)      │
│      │                                                                       │
│      │  ┌─────────────────────────────────────────────────────────────┐      │
│      │  │  INSIDE look_at() — for each image batch:                   │      │
│      │  │                                                             │      │
│      │  │  1. Load images from stimulus_paths                         │      │
│      │  │  2. Preprocess: resize, normalize, convert to tensor        │      │
│      │  │  3. Forward pass through neural network                     │      │
│      │  │  4. Hooks capture activations at target layer (e.g. layer4) │      │
│      │  │  5. Flatten: (batch, C, H, W) → (batch, C*H*W neuroids)     │      │
│      │  │  6. Store in NeuroidAssembly with stimulus_id coordinates   │      │
│      │  └─────────────────────────────────────────────────────────────┘      │
│      │                                                                       │
│      └──→ Returns NeuroidAssembly: (presentations × neuroids × time_bins)    │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4d: Compare model activations to biological recordings                 │
│                                                                              │
│  raw_score = similarity_metric(source_assembly, self._assembly)              │
│      │                                                                       │
│      │  ┌──────────────────────────────────────────────────────────────┐     │
│      │  │  INSIDE PLS metric:                                          │     │
│      │  │                                                              │     │
│      │  │  1. Align by stimulus_id (same presentation order)           │     │
│      │  │  2. Cross-validation split (stratify by object_name)         │     │
│      │  │  3. For each fold:                                           │     │
│      │  │     a. Fit PLS: model_activations → neural_data              │     │
│      │  │     b. Predict on held-out stimuli                           │     │
│      │  │     c. Pearson correlation per neuroid                       │     │
│      │  │  4. Average correlations across folds and neuroids           │     │
│      │  └──────────────────────────────────────────────────────────────┘     │
│      │                                                                       │
│      └──→ Returns Score (e.g., 0.65) with metadata                           │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4e: Normalize by ceiling (explained variance)                          │
│                                                                              ││
│  ceiled_score = explained_variance(raw_score, self.ceiling)                  │
│      │                                                                       │
│      │  Formula: ceiled_score = (raw_score / ceiling)²                       │
│      │                                                                       │
│      │  Example: raw_score=0.65, ceiling=0.82                                │
│      │           ceiled_score = (0.65 / 0.82)² ≈ 0.63                        │
│      │                                                                       │
│      └──→ Returns final Score between 0 and 1                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## The PLS Metric

The standard metric for neural benchmarks is **PLS (Partial Least Squares) regression**:

```python
from brainscore_vision.metrics.regression_correlation import CrossRegressedCorrelation

class CrossRegressedCorrelation(Metric):
    def __call__(self, source: DataAssembly, target: DataAssembly) -> Score:
        # Cross-validation handles train/test splits
        return self.cross_validation(source, target, apply=self.apply, aggregate=self.aggregate)

    def apply(self, source_train, target_train, source_test, target_test):
        # 1. Fit PLS: model_activations → neural_data (training set)
        self.regression.fit(source_train, target_train)
        
        # 2. Predict neural data from model activations (test set)
        prediction = self.regression.predict(source_test)
        
        # 3. Correlate predictions with actual neural data
        score = self.correlation(prediction, target_test)
        return score

    def aggregate(self, scores):
        # Median correlation across neuroids (robust to outliers)
        return scores.median(dim='neuroid')
```

**Pipeline visualization**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Cross-Validated PLS Regression                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  For each cross-validation fold:                                            │
│                                                                             │
│  TRAIN SET (90%):                                                           │
│  ┌────────────────────┐      ┌────────────────────┐                         │
│  │ Model Activations  │      │ Neural Recordings  │                         │
│  │ (stimuli × units)  │ ───→ │ (stimuli × neurons)│                         │
│  └────────────────────┘  PLS └────────────────────┘                         │
│                          fit                                                │
│                                                                             │
│  TEST SET (10%):                                                            │
│  ┌────────────────────┐      ┌────────────────────┐      ┌────────────┐     │
│  │ Model Activations  │ ───→ │ Predicted Neural   │ corr │   Score    │     │
│  │ (stimuli × units)  │  PLS │ (stimuli × neurons)│ ───→ │ per neuron │     │
│  └────────────────────┘ pred └────────────────────┘      └────────────┘     │
│                                                                             │
│  Final: Median correlation across neurons and folds                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Patterns

### Pattern 1: NeuralBenchmark (Recommended)

**When to use**: Standard neural predictivity with PLS/Ridge regression metrics.

```python
from brainscore_vision.benchmark_helpers.neural_common import NeuralBenchmark

def DicarloMajajHong2015ITPLS():
    assembly = load_assembly(average_repetitions=True, region='IT')
    assembly_repetition = load_assembly(average_repetitions=False, region='IT')
    
    return NeuralBenchmark(
        identifier='MajajHong2015.IT-pls',
        assembly=assembly,
        similarity_metric=load_metric('pls'),
        visual_degrees=8,
        number_of_trials=50,
        ceiling_func=lambda: ceiler(assembly_repetition),
        parent='IT',
        bibtex=BIBTEX
    )
```

---

### Pattern 2: PropertiesBenchmark

**When to use**: Comparing neuronal properties like tuning curves, receptive field sizes, surround suppression.

```python
from brainscore_vision.benchmark_helpers.properties_common import PropertiesBenchmark

def MarquesCavanaugh2002V1SurroundSuppressionIndex():
    assembly = load_dataset('Cavanaugh2002a')
    similarity_metric = load_metric('ks_similarity', property_name='surround_suppression_index')
    
    return PropertiesBenchmark(
        identifier='Marques2020_Cavanaugh2002-surround_suppression_index',
        assembly=assembly,
        neuronal_property=cavanaugh2002_properties,
        similarity_metric=similarity_metric,
        timebins=[(70, 170)],
        ceiling_func=NeuronalPropertyCeiling(similarity_metric),
        parent='V1-surround_modulation',
        bibtex=BIBTEX
    )
```

---

### Pattern 3: BenchmarkBase (Custom Logic)

**When to use**: Custom preprocessing, RSA metrics, non-standard analysis.

```python
from brainscore_vision.benchmarks import BenchmarkBase

class _Bracci2019RSA(BenchmarkBase):
    def __init__(self, region):
        self._stimulus_set = load_stimulus_set('Bracci2019')
        self._human_assembly = load_dataset('Bracci2019')
        self._metric = load_metric('rdm')
        
        super().__init__(
            identifier=f'Bracci2019.{region}-rdm',
            version=1,
            ceiling_func=lambda: 1,
            parent='Bracci2019',
            bibtex=BIBTEX
        )
    
    def __call__(self, candidate: BrainModel):
        # 1. Start recording
        candidate.start_recording(self._region, [(70, 170)])
        
        # 2. Scale stimuli
        stimulus_set = place_on_screen(
            self._stimulus_set,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=8
        )
        
        # 3. Get model activations
        dnn_assembly = candidate.look_at(stimulus_set, number_of_trials=1)
        
        # 4. Custom preprocessing and comparison
        ceiling = self._get_human_ceiling(self._human_assembly)
        similarity = self._metric(dnn_assembly, self._human_assembly)
        
        score = Score(similarity / ceiling)
        score.attrs['raw'] = similarity
        score.attrs['ceiling'] = ceiling
        
        return score
```

---

## Pattern Comparison

| Aspect | NeuralBenchmark | PropertiesBenchmark | BenchmarkBase |
|--------|-----------------|---------------------|---------------|
| **Abstraction** | High | Medium | Low (full control) |
| **Implements `__call__`** | No (inherited) | No (inherited) | **Yes (required)** |
| **Calls `look_at`** | No (automatic) | No (automatic) | **Yes (explicit)** |
| **Custom preprocessing** | No | Limited | **Yes** |
| **Use case** | Standard neural | Neuronal properties | RSA, custom |
| **Examples** | MajajHong2015 | Marques2020 | Bracci2019 |

---

## Registration

Register your benchmark in `__init__.py`:

```python
# benchmarks/myexperiment/__init__.py
from brainscore_vision import benchmark_registry
from .benchmark import MyNeuralBenchmark

# Pattern 1: Direct function reference
benchmark_registry['MyExperiment.IT-pls'] = MyNeuralBenchmark

# Pattern 2: Lambda with parameters
benchmark_registry['MyExperiment.V4-pls'] = lambda: MyNeuralBenchmark(region='V4')
```

---

## Plugin Directory Structure

```
vision/brainscore_vision/benchmarks/myexperiment/
├── __init__.py          # Registration
├── benchmark.py         # Benchmark implementation
├── test.py              # Unit tests
└── requirements.txt     # Dependencies (optional)
```

---

## Neural Benchmark Checklist

Before submitting your neural benchmark:

- [ ] Uses `NeuroidAssembly` with correct dimensions (`presentation × neuroid × time_bin`)
- [ ] Loads data with `average_repetitions=True` for model comparison
- [ ] Loads data with `average_repetitions=False` for ceiling calculation
- [ ] Uses internal consistency ceiling (split-half reliability)
- [ ] Specifies correct `visual_degrees` from original experiment
- [ ] Uses PLS or Ridge metric for regression-based comparison
- [ ] Includes proper `bibtex` citation
- [ ] Tests verify expected scores for known models

---

## Next Steps

- **[Behavioral Benchmarks](/tutorials/benchmarks/behavioral-benchmarks/)** — Create benchmarks for behavioral data
- **[Vision vs Language](/tutorials/benchmarks/vision-vs-language/)** — Differences between vision and language benchmarks

