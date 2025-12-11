---
title: Neural Benchmarks
description: Creating benchmarks that compare model activations to neural recordings
order: 3
category: benchmarks
---

# Neural Benchmarks

Neural benchmarks evaluate whether artificial neural networks develop internal representations similar to those found in biological brains. Rather than just matching behavioral outputs, these benchmarks ask the question: **does the model process information the way the brain does?**

By comparing model activations to neural recordings (fMRI, electrophysiology, EEG, etc.), we can assess whether a model has learned representations that are fundamentally "brain-like." Models that accurately predict neural activity across brain regions provide evidence that they may have discovered similar computational solutions to the ones evolution found.

---

## Table of Contents

| Section | Topics |
|---------|--------|
| [Overview](#overview) | Existing benchmarks, key characteristics |
| [Inheritance Structure](#inheritance-structure) | Benchmark → BenchmarkBase → NeuralBenchmark |
| [What NeuralBenchmark Provides](#what-neuralbenchmark-provides) | Automatic features, parameters reference |
| [Example: MajajHong2015](#example-majajhong2015) | Complete implementation walkthrough |
| [Design Decisions in Neural Benchmarks](#design-decisions-in-neural-benchmarks) | Repetitions, stratification, time bins, regions |
| [The Internal Consistency Ceiling](#the-internal-consistency-ceiling) | Ceiling calculation |
| [What Happens Under the Hood](#what-happens-under-the-hood) | Detailed call flow |
| [Common Neural Metrics](#common-neural-metrics) | PLS, Ridge, RidgeCV, Neuron-to-Neuron, RDM, CKA |
| [Implementation Patterns](#implementation-patterns) | NeuralBenchmark, PropertiesBenchmark, BenchmarkBase |
| [Building MyExperiment2024](#building-myexperiment2024-complete-example) | Complete benchmark implementation example |
| [Registration](#registration) | Plugin setup |
| [Testing Your Benchmark](#testing-your-benchmark) | Test file example |
| [Common Issues and Solutions](#common-issues-and-solutions) | Troubleshooting |
| [Neural Benchmark Checklist](#neural-benchmark-checklist) | Pre-submission verification |

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
│  Benchmark (ABC)                                                    │
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

**NeuralBenchmark Parameters**:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `identifier` | Yes | Unique name following `AuthorYear.region-metric` convention (e.g., `MajajHong2015.IT-pls`) |
| `version` | Yes | Integer version number; increment when changes affect scores |
| `assembly` | Yes | `NeuroidAssembly` with biological recordings (typically averaged repetitions) |
| `similarity_metric` | Yes | Metric for comparing model to brain (e.g., `pls`, `ridge`) |
| `visual_degrees` | Yes | Stimulus size in degrees of visual angle from original experiment |
| `number_of_trials` | Yes | Number of stimulus presentations per image |
| `ceiling_func` | Yes | Function returning maximum achievable `Score` (uses non-averaged data) |
| `parent` | Yes | Position in leaderboard hierarchy (`V1`, `V2`, `V4`, `IT`, or custom) |
| `bibtex` | Yes | Citation for the original neuroscience paper |
| `timebins` | No | Time windows for temporal analysis; defaults to `[(70, 170)]` ms |

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

## Design Decisions in Neural Benchmarks

Different benchmarks use coordinates strategically to ask specific scientific questions. Understanding these patterns helps you design benchmarks that capture what you want to measure.

#### Using Repetitions for Ceiling Computation

**The pattern**: Load data twice—once with repetitions averaged (for model comparison), once with repetitions kept (for ceiling).

```python
# From MajajHong2015
assembly = load_assembly(average_repetitions=True, region='IT')      # For metric
assembly_repetition = load_assembly(average_repetitions=False, region='IT')  # For ceiling

ceiling_func = lambda: ceiler(assembly_repetition)  # Split-half uses repetitions
```

**Why?** The ceiling measures how consistent the biological data is with itself. If a neuron responds differently across repetitions of the same stimulus, that variability sets an upper limit on predictability. You need the individual repetitions to compute this split-half reliability.

#### Using Coordinates for Stratified Cross-Validation

**The pattern**: Pass a `stratification_coord` to ensure balanced sampling across stimulus categories.

```python
# From FreemanZiemba2013
similarity_metric = load_metric('pls', crossvalidation_kwargs=dict(
    stratification_coord='texture_type'  # Balance texture vs. noise images
))
```

**Why?** If your dataset has distinct stimulus categories (textures vs. noise, objects vs. scenes, etc.), random splits might accidentally put all of one category in training. Stratification ensures each fold has balanced representation, giving more reliable score estimates.

| Benchmark | Stratification Coord | Purpose |
|-----------|---------------------|---------|
| FreemanZiemba2013 | `texture_type` | Balance texture and spectrally-matched noise images |
| MajajHong2015 | `object_name` | Balance across object categories |
| Custom | `image_category`, `difficulty`, etc. | Balance any relevant experimental condition |

#### Using Time Bins for Temporal Dynamics

**The pattern**: Define multiple time bins to capture how representations evolve over time.

```python
# From Kar2019 - Object Solution Times
TIME_BINS = [(time_bin_start, time_bin_start + 10) 
             for time_bin_start in range(70, 250, 10)]  # 70-250ms in 10ms steps

candidate.start_recording('IT', time_bins=TIME_BINS)
```

**Why?** Some scientific questions require temporal resolution:
- **Kar2019**: Tests whether models predict *when* object identity emerges (recurrent processing)
- **Static benchmarks**: Use single bin `[(70, 170)]` for overall response

```python
# Static benchmark (default)
TIME_BINS = [(70, 170)]  # Single 100ms window

# Temporal benchmark
TIME_BINS = [(t, t+10) for t in range(70, 250, 10)]  # 18 time bins × 10ms each
```

#### Using Region Coordinates to Slice Data

**The pattern**: Filter assembly by brain region to create region-specific benchmarks from a single dataset.

```python
# From MajajHong2015 - separate V4 and IT benchmarks
def load_assembly(region: str, average_repetitions: bool):
    assembly = load_dataset('MajajHong2015')
    assembly = assembly.sel(neuroid=assembly['region'] == region)  # Filter by region
    if average_repetitions:
        assembly = assembly.mean(dim='repetition')
    return assembly

# Creates separate benchmarks
benchmark_IT = NeuralBenchmark(identifier='MajajHong2015.IT-pls', ...)
benchmark_V4 = NeuralBenchmark(identifier='MajajHong2015.V4-pls', ...)
```

**Why?** Different brain regions have different computational roles. By slicing the same dataset, you can ask: "How well does the model predict V4 vs. IT?" without packaging separate datasets.

#### Using Stimulus Coordinates for Specialized Analyses

**The pattern**: Use stimulus metadata coordinates to compute neuronal properties or specialized metrics.

```python
# From FreemanZiemba2013 - Texture Modulation properties
def freemanziemba2013_properties(responses, baseline):
    # Uses 'type', 'family', 'sample' coordinates to organize responses
    responses = responses.sortby(['type', 'family', 'sample'])
    
    type = np.array(sorted(set(responses.type.values)))    # texture vs. noise
    family = np.array(sorted(set(responses.family.values)))  # texture family
    sample = np.array(sorted(set(responses.sample.values)))  # specific sample
    
    # Reshape using coordinate structure
    responses = responses.values.reshape(n_neuroids, len(type), len(family), len(sample))
    
    # Compute texture modulation index from structured data
    texture_modulation_index = calc_texture_modulation(responses[:, 1], responses[:, 0])
```

**Why?** Rich coordinate metadata enables complex analyses beyond simple predictivity. The FreemanZiemba2013 benchmark computes texture modulation indices by leveraging the experimental structure encoded in coordinates.

<br>

> **Key Insight**: The coordinates you include in your `NeuroidAssembly` during data packaging can determine what scientific questions your benchmark can answer. Plan your coordinates based on what you want to measure.

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

**The ceiling** answers: "How well can we predict one half of the biological data from the other half?" It represents the **limit of the true signal** inside the noisy date.

This sets the upper bound for any model—if the biological data is only **80% reliable** (80% signal, 20% noise), a model that explains **80%** of the variance is actually "perfect."

___

Since every dataset has a different amount of noise, we cannot compare raw correlations directly. We normalize the raw score by the ceiling so we can compare a model's performance across different datasets:

$$
\text{Normalized Ceiled Score} = \frac{\text{What the Model Explained (Raw Score)}}{\text{What was Theoretically Possible to Explain (Ceiling)}}
$$

---

## How Brain-Score Executes Benchmarks:

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


## Deeper Look Under The Hood

<details>
<summary><strong>Click to expand: High-level call flow (Steps 1-4)</strong></summary>

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

</details>
<br>
<details>
<summary><strong>Click to expand: What happens inside benchmark(model) — Step 4 in detail</strong></summary>

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
│                                                                              │
│  ceiled_score = explained_variance(raw_score, self.ceiling)                  │
│      │                                                                       │
│      │  Formula: ceiled_score = raw_score² / ceiling                         │
│      │                                                                       │
│      │  Example: raw_score=0.65, ceiling=0.82                                │
│      │           ceiled_score = 0.65² / 0.82 ≈ 0.515                         │
│      │                                                                       │
│      └──→ Returns final Score between 0 and 1                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```
</details>

<br> 

> ⚠️ **Critical**: There is a pervasive misconception in neural encoding that because Split-Half Consistency is calculated using a Pearson correlation (r), the resulting Reliability coefficient must also be treated as a raw unit (r) that requires squaring to become variance.
>However, Classical Test Theory defines Reliability (after Spearman-Brown correction) as the ratio of True Score Variance to Total Variance:
$$
\text{Reliability} = \frac{\text{Var(True)}}{\text{Var(Total)}}
$$
>Therefore, the Reliability coefficient *is already* a measure of explainable variance (r²). 
>As a result, the ceiled score calculation is r_model² / reliability

>Reference: See ["How Much Variance Does Your Model Explain? A Clarifying Note on the Use of Split-Half Reliability for Computing Noise Ceilings" (Van Bree, Styrnal & Hebart)](https://osf.io/preprints/psyarxiv/gjk45).

---

## Common Neural Metrics

Brain-Score provides several metrics for comparing model representations to neural data. Each has different strengths:

### Metric Comparison Table

| Metric | Registry Key | Implementation | When to Use |
|--------|-------------|----------------|-------------|
| **PLS Regression** | `pls` | `metrics/regression_correlation/metric.py` | **Default choice**. Handles high-dimensional data well |
| **Ridge Regression** | `ridge` | `metrics/regression_correlation/metric.py` | Explicit regularization control; interpretable |
| **RidgeCV** | `ridgecv_split` | `metrics/regression_correlation/metric.py` | Auto-tunes regularization strength |
| **Linear Regression** | `linear_predictivity` | `metrics/regression_correlation/metric.py` | Small datasets; risk of overfitting |
| **Neuron-to-Neuron** | `neuron_to_neuron` | `metrics/regression_correlation/metric.py` | Interpretable 1:1 unit correspondences |
| **CKA** | `cka` | `metrics/cka/metric.py` | Representational geometry comparison |
| **RDM** | `rdm` | `metrics/rdm/metric.py` | Classic RSA; stimulus similarity structures |

> **Note**: All paths are relative to `brainscore_vision/` in the vision repository.

### Regression-Based Metrics (Encoding Models)

The most common approach uses regression to learn a mapping from model activations to neural responses:

#### PLS Regression (Default)

**Partial Least Squares** is the standard metric for neural benchmarks:

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

**Why PLS?** PLS handles high-dimensional model activations (often thousands of units) mapping to neural responses. It finds latent components that maximize covariance between model and brain, providing robust predictions even when model dimensions >> stimuli.

#### Ridge Regression

**Ridge** adds L2 regularization to prevent overfitting:

```python
from brainscore_vision import load_metric

# Standard Ridge (fixed alpha=1)
metric = load_metric('ridge')

# RidgeCV (auto-tunes regularization)
metric = load_metric('ridgecv_split')  # For pre-split train/test data
```

**When to use Ridge over PLS:**
- When you want explicit control over regularization strength
- When interpretability of weights matters
- RidgeCV is ideal when you don't know the optimal regularization strength

#### Neuron-to-Neuron Matching

Finds the **best single model unit** for each biological neuron:

```python
metric = load_metric('neuron_to_neuron')
```

**When to use:** When you want interpretable 1:1 correspondences, or testing whether individual model units behave like individual neurons.

### Representational Similarity Metrics

These metrics compare the **geometry** of representations rather than predicting neural responses directly:

#### RDM (Representational Dissimilarity Matrix)

Classic **Representational Similarity Analysis (RSA)**:

```python
from brainscore_vision import load_metric

metric = load_metric('rdm')      # Single comparison
metric = load_metric('rdm_cv')   # Cross-validated
```

**How it works:**
1. Compute pairwise distances between stimulus responses (for both model and brain)
2. Compare the resulting distance matrices with Spearman correlation

**When to use:**
- Comparing representational structure independent of linear transforms
- When you care about which stimuli are represented similarly vs. differently
- Classic RSA paradigms

#### CKA (Centered Kernel Alignment)

Measures similarity of representational geometry:

```python
from brainscore_vision import load_metric

metric = load_metric('cka')      # Single comparison
metric = load_metric('cka_cv')   # Cross-validated
```

**When to use:**
- Comparing overall representational geometry
- Invariant to orthogonal transformations and isotropic scaling
- Good for comparing layers across different architectures

### Choosing the Right Metric

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Decision Guide: Which Metric Should I Use?                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Q: Do you want to predict neural responses from model activations?         │
│  ├── YES → Use regression-based metrics                                     │
│  │   ├── Default: PLS (handles high dimensions well)                        │
│  │   ├── Want regularization control? → Ridge                               │
│  │   └── Want 1:1 unit matching? → Neuron-to-Neuron                         │
│  │                                                                          │
│  └── NO → Use representational similarity metrics                           │
│      ├── Classic RSA paradigm? → RDM                                        │
│      └── Comparing representational geometry? → CKA                         │
│                                                                             │
│  Most Brain-Score neural benchmarks use: pls (default) or ridge             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cross-Validation vs. Fixed Split

Each metric comes in two variants:

| Suffix | Example | Use Case |
|--------|---------|----------|
| `_cv` | `pls_cv`, `ridge_cv` | **Default**. Cross-validates on a single dataset |
| `_split` | `pls_split`, `ridge_split` | Use with pre-defined train/test splits |

```python
# Cross-validation (most common): metric handles splitting
metric = load_metric('pls')  # Alias for 'pls_cv'

# Fixed split: you provide separate train and test data
metric = load_metric('pls_split')
score = metric(source_train, source_test, target_train, target_test)
```

### Temporal Metrics

For time-resolved neural data, use the `spantime_` prefix:

```python
metric = load_metric('spantime_pls')    # PLS across time bins
metric = load_metric('spantime_ridge')  # Ridge across time bins
```

These treat time as a sample dimension, pooling across time bins when fitting the regression.


> ⚠️ **Note**: Feel free to implement your own metric plugin.

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

## Building MyExperiment2024: Complete Example

This section builds a complete neural benchmark using the `MyExperiment2024` dataset that was packaged in the [Data Packaging Tutorial](02-data-packaging.md).

### Prerequisites

Ensure you have already:
1. Packaged your `StimulusSet` and `NeuroidAssembly` (see [Data Packaging](02-data-packaging.md))
2. Uploaded data to S3 and received version IDs
3. Registered the data plugin in `brainscore_vision/data/myexperiment2024/`

### Step 1: Create the Benchmark File

```python
# vision/brainscore_vision/benchmarks/myexperiment2024/benchmark.py

from brainscore_vision import load_dataset, load_metric
from brainscore_vision.benchmark_helpers.neural_common import NeuralBenchmark
from brainscore_vision.benchmark_helpers.screen import place_on_screen
from brainscore_vision.metrics.internal_consistency import InternalConsistency

# Bibtex for your publication (same as in data plugin)
BIBTEX = """@article{MyExperiment2024,
    title = {Neural correlates of visual object recognition in primates},
    volume = {42},
    doi = {10.1234/neuroscience.2024.00123},
    journal = {Journal of Neuroscience},
    author = {Pradeepan, Kartik S., and Ferguson, Mike.},
    year = {2024},
}"""

# Visual degrees used in the original experiment
VISUAL_DEGREES = 8

# Time bin for neural responses (in milliseconds)
TIME_BINS = [(70, 170)]

# Number of trials for model evaluation
NUMBER_OF_TRIALS = 50


def load_assembly(region: str, average_repetitions: bool = True):
    """
    Load the neural assembly for a specific brain region.
    
    Args:
        region: Brain region to filter ('V4' or 'IT')
        average_repetitions: If True, average across repeated presentations
    
    Returns:
        NeuroidAssembly filtered by region
    """
    assembly = load_dataset('MyExperiment2024')
    
    # Filter by region if the assembly contains multiple regions
    if 'region' in assembly.coords:
        assembly = assembly.sel(neuroid=assembly['region'] == region)
    
    # Average across repetitions for the main assembly
    if average_repetitions and 'repetition' in assembly.dims:
        assembly = assembly.mean(dim='repetition')
    
    return assembly


def MyExperiment2024ITPLS():
    """
    IT cortex benchmark using PLS regression.
    
    This is the main benchmark for comparing model representations
    to IT neural responses from MyExperiment2024.
    """
    # Load the averaged assembly for metric computation
    assembly = load_assembly(region='IT', average_repetitions=True)
    
    # Load the non-averaged assembly for ceiling computation
    # (needs repetitions to compute split-half reliability)
    assembly_repetition = load_assembly(region='IT', average_repetitions=False)
    
    # Create ceiling function using internal consistency
    ceiler = InternalConsistency()
    
    return NeuralBenchmark(
        identifier='MyExperiment2024.IT-pls',
        assembly=assembly,
        similarity_metric=load_metric('pls'),
        visual_degrees=VISUAL_DEGREES,
        number_of_trials=NUMBER_OF_TRIALS,
        ceiling_func=lambda: ceiler(assembly_repetition),
        parent='IT',
        bibtex=BIBTEX
    )


def MyExperiment2024V4PLS():
    """
    V4 cortex benchmark using PLS regression.
    """
    assembly = load_assembly(region='V4', average_repetitions=True)
    assembly_repetition = load_assembly(region='V4', average_repetitions=False)
    
    ceiler = InternalConsistency()
    
    return NeuralBenchmark(
        identifier='MyExperiment2024.V4-pls',
        assembly=assembly,
        similarity_metric=load_metric('pls'),
        visual_degrees=VISUAL_DEGREES,
        number_of_trials=NUMBER_OF_TRIALS,
        ceiling_func=lambda: ceiler(assembly_repetition),
        parent='V4',
        bibtex=BIBTEX
    )


def MyExperiment2024ITRidge():
    """
    IT cortex benchmark using Ridge regression.
    
    Alternative metric for users who prefer explicit regularization.
    """
    assembly = load_assembly(region='IT', average_repetitions=True)
    assembly_repetition = load_assembly(region='IT', average_repetitions=False)
    
    ceiler = InternalConsistency()
    
    return NeuralBenchmark(
        identifier='MyExperiment2024.IT-ridge',
        assembly=assembly,
        similarity_metric=load_metric('ridge'),
        visual_degrees=VISUAL_DEGREES,
        number_of_trials=NUMBER_OF_TRIALS,
        ceiling_func=lambda: ceiler(assembly_repetition),
        parent='IT',
        bibtex=BIBTEX
    )
```

### Step 2: Key Design Decisions Explained

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| **Helper class** | `NeuralBenchmark` | Standard neural predictivity; handles `look_at`, stimulus scaling, and ceiling normalization automatically |
| **Metric** | `pls` (primary), `ridge` (alternative) | PLS is the Brain-Score standard; Ridge offered as alternative |
| **Ceiling** | `InternalConsistency` | Measures split-half reliability to estimate noise ceiling |
| **Time bins** | `(70, 170)` ms | Standard window for object recognition responses |
| **Visual degrees** | `8°` | Must match the original experiment's stimulus size |
| **Separate functions** | One per region/metric | Clean registration, clear identifiers |

### Step 3: Understanding the Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MyExperiment2024ITPLS() is called                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. load_assembly('IT', average_repetitions=True)                       │
│     └──→ Fetches NeuroidAssembly from S3 (lazy loading)                 │
│     └──→ Filters to IT neurons only                                     │
│     └──→ Averages across repetitions                                    │
│                                                                         │
│  2. load_assembly('IT', average_repetitions=False)                      │
│     └──→ Same data, but keeps repetitions for ceiling                   │
│                                                                         │
│  3. NeuralBenchmark(...) creates benchmark instance                     │
│     └──→ Stores assembly, metric, visual_degrees, etc.                  │
│     └──→ ceiling_func is a lambda (computed lazily when needed)         │
│                                                                         │
│  4. When benchmark(model) is called later:                              │
│     └──→ NeuralBenchmark.__call__ handles everything                    │
│     └──→ Returns ceiling-normalized Score                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Registration

Register your benchmark in `__init__.py`:

```python
# vision/brainscore_vision/benchmarks/myexperiment2024/__init__.py

from brainscore_vision import benchmark_registry
from .benchmark import (
    MyExperiment2024ITPLS,
    MyExperiment2024V4PLS,
    MyExperiment2024ITRidge
)

# Register each benchmark variant
# The key is the identifier users will use to load the benchmark
benchmark_registry['MyExperiment2024.IT-pls'] = MyExperiment2024ITPLS
benchmark_registry['MyExperiment2024.V4-pls'] = MyExperiment2024V4PLS
benchmark_registry['MyExperiment2024.IT-ridge'] = MyExperiment2024ITRidge
```

> **Note**: Each factory function (e.g., `MyExperiment2024ITPLS`) is registered directly. Brain-Score will call the function when the benchmark is loaded, creating a fresh instance each time.

---

## Plugin Directory Structure

```
vision/brainscore_vision/benchmarks/myexperiment2024/
├── __init__.py          # Registration (imports from benchmark.py)
├── benchmark.py         # Benchmark implementation (factory functions)
├── test.py              # Unit tests
└── requirements.txt     # Dependencies (optional)
```

---

## Testing Your Benchmark

Every benchmark should include tests to verify it loads and produces expected scores:

```python
# vision/brainscore_vision/benchmarks/myexperiment2024/test.py

import pytest
from brainscore_vision import load_benchmark, load_model

@pytest.mark.private_access
class TestMyExperiment2024:
    """Tests for MyExperiment2024 neural benchmarks."""
    
    @pytest.mark.parametrize("identifier", [
        'MyExperiment2024.IT-pls',
        'MyExperiment2024.V4-pls',
        'MyExperiment2024.IT-ridge',
    ])
    def test_benchmark_loads(self, identifier):
        """Test that each benchmark variant can be loaded."""
        benchmark = load_benchmark(identifier)
        assert benchmark is not None
        assert benchmark.identifier == identifier
    
    def test_ceiling_valid(self):
        """Test ceiling is computed and in valid range."""
        benchmark = load_benchmark('MyExperiment2024.IT-pls')
        ceiling = benchmark.ceiling
        assert 0 < ceiling <= 1, f"Ceiling {ceiling} out of expected range"
        assert hasattr(ceiling, 'attrs')
    
    def test_benchmark_score(self):
        """Test benchmark produces expected score for a known model."""
        benchmark = load_benchmark('MyExperiment2024.IT-pls')
        model = load_model('alexnet')
        
        score = benchmark(model)
        
        # Verify score is valid
        assert 0 <= score <= 1
        assert hasattr(score, 'attrs')
        assert 'raw' in score.attrs or 'ceiling' in score.attrs
        
        # Optional: Document expected score for regression testing
        # assert abs(score - 0.45) < 0.05  # Expected ~0.45 for alexnet
```

---

## Common Issues and Solutions

#### Problem: "Ceiling is greater than 1"

The ceiling calculation may be returning raw correlation values instead of proper ceiling estimates.

```python
# Solution: Ensure ceiling_func uses non-averaged data with split-half
ceiling_func=lambda: ceiler(assembly_repetition)  # NOT assembly (averaged)
```

#### Problem: "Score is negative"

Negative scores usually indicate stimulus alignment issues between model and biological data.

```python
# Solution: Check stimulus_id alignment
model_ids = set(model_assembly['stimulus_id'].values)
bio_ids = set(biological_assembly['stimulus_id'].values)
assert model_ids == bio_ids, f"Mismatched IDs: {model_ids ^ bio_ids}"
```

#### Problem: "Model activations shape mismatch"

The model's layer output doesn't match expected dimensions.

```python
# Solution: Verify the region-to-layer mapping
# Check that model.start_recording() is using correct layer
candidate.start_recording('IT', time_bins=[(70, 170)])
# Ensure your model's layer map includes 'IT' → appropriate layer
```

#### Problem: "Time bins not found"

Assembly missing temporal dimension required by the benchmark.

```python
# Solution: Ensure assembly has time_bin dimension
assert 'time_bin' in assembly.dims or len(assembly.dims) == 2
# For static benchmarks, NeuralBenchmark squeezes single time bins automatically
```

#### Problem: "PLS regression fails to converge"

Too few samples or too many features for regression.

```python
# Solution: Check data dimensions
print(f"Samples: {len(assembly['presentation'])}, Features: {len(assembly['neuroid'])}")
# PLS needs samples > features; consider using Ridge for high-dimensional data
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

