---
title: Vision vs Language
description: Key differences between vision and language benchmarks
order: 5
category: benchmarks
---

# Vision vs Language Benchmarks

This tutorial series primarily uses Brain-Score Vision examples. If you're creating a **language benchmark**, this page covers the key differences you need to know.

---

## Overview of Differences

| Aspect | Vision | Language |
|--------|--------|----------|
| Package | `brainscore_vision` | `brainscore_language` |
| Model Interface | `BrainModel` | `ArtificialSubject` |
| Stimulus Presentation | `candidate.look_at()` | `candidate.digest_text()` |
| Task Setup | `candidate.start_task()` | `candidate.start_behavioral_task()` |
| Stimulus Type | Images (file paths required) | Text (can be embedded in assembly) |
| Visual Field | `visual_degrees`, `place_on_screen()` | Not applicable |
| Brain Regions | V1, V2, V4, IT | Language network, specific ROIs |

---

## 1. Model Interface

### Vision

```python
from brainscore_vision.model_interface import BrainModel

candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
predictions = candidate.look_at(stimulus_set, number_of_trials=1)
```

### Language

```python
from brainscore_language.artificial_subject import ArtificialSubject

candidate.start_behavioral_task(ArtificialSubject.Task.reading_times)
predictions = candidate.digest_text(stimuli)['behavior']
```

---

## 2. Task Types

### Vision Tasks

| Task | Purpose |
|------|---------|
| `BrainModel.Task.passive` | Neural recording without behavioral output |
| `BrainModel.Task.label` | Discrete categorization |
| `BrainModel.Task.probabilities` | Probability distributions over classes |
| `BrainModel.Task.odd_one_out` | Triplet similarity judgments |

### Language Tasks

| Task | Purpose |
|------|---------|
| `ArtificialSubject.Task.reading_times` | Predict word-by-word reading times |
| `ArtificialSubject.Task.next_word` | Predict next word in sequence |
| `ArtificialSubject.Task.neural` | Neural response prediction |

---

## 3. Stimulus Handling

### Vision — Image Files

Stimuli are image files that must be mapped via `stimulus_paths`:

```python
stimulus_set = StimulusSet(stimuli_data)
stimulus_set.stimulus_paths = {
    'img_001': '/path/to/image1.jpg',
    'img_002': '/path/to/image2.jpg',
}
stimulus_set.name = 'MyVisionExperiment2024'
```

### Language — Embedded Text

Text stimuli can be embedded directly in the DataAssembly (no `StimulusSet` needed):

```python
assembly = BehavioralAssembly(
    reading_times,  # Response data
    coords={
        'stimulus_id': ('presentation', ['stim_001', 'stim_002', 'stim_003']),
        'word': ('presentation', ['The', 'cat', 'sat']),  # Stimulus embedded
        'sentence_id': ('presentation', [1, 1, 1]),
        'word_position': ('presentation', [0, 1, 2])
    },
    dims=['presentation']
)

# Extract stimuli directly from assembly
stimuli = assembly['word'].values  # ['The', 'cat', 'sat']
```

---

## 4. Visual Degrees (Vision Only)

### Vision

Requires scaling stimuli to match the model's visual field:

```python
from brainscore_vision.benchmark_helpers.screen import place_on_screen

stimulus_set = place_on_screen(
    self._stimulus_set,
    target_visual_degrees=candidate.visual_degrees(),
    source_visual_degrees=8  # Original experiment visual degrees
)
```

### Language

This concept does not apply. Text is passed directly:

```python
predictions = candidate.digest_text(text_stimuli)['behavior']
```

---

## 5. Brain Regions

### Vision Regions

- `V1` — Primary visual cortex
- `V2` — Secondary visual cortex
- `V4` — Visual area V4
- `IT` — Inferotemporal cortex

### Language Regions

- Language network
- Specific ROIs (e.g., inferior frontal gyrus, superior temporal gyrus)
- fMRI-defined language areas

---

## 6. Import Statements

### Vision

```python
from brainscore_vision import load_benchmark, load_model, load_dataset, load_stimulus_set
from brainscore_vision.benchmarks import BenchmarkBase
from brainscore_vision.model_interface import BrainModel
from brainscore_vision.benchmark_helpers.screen import place_on_screen
```

### Language

```python
from brainscore_language import load_benchmark, load_dataset, load_metric
from brainscore_language.benchmarks import BenchmarkBase
from brainscore_language.artificial_subject import ArtificialSubject
```

---

## 7. Language Benchmark Call Flow

<details>
<summary><strong>Click to expand: Language benchmark execution flow</strong></summary>

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  INSIDE language_benchmark.__call__(candidate)                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 1: Configure the task                                                  │
│                                                                              │
│  # For behavioral benchmarks:                                                │
│  candidate.start_behavioral_task(ArtificialSubject.Task.reading_times)       │
│      │                                                                       │
│      └──→ Model prepares to output behavioral responses                      │
│                                                                              │
│  # For neural benchmarks:                                                    │
│  candidate.start_neural_recording(                                           │
│      recording_target=ArtificialSubject.RecordingTarget.language_system,     │
│      recording_type=ArtificialSubject.RecordingType.fMRI                     │
│  )                                                                           │
│      │                                                                       │
│      └──→ Model prepares to output neural activations                        │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 2: Extract text stimuli from assembly                                  │
│                                                                              │
│  stimuli = self._assembly['word'].values  # or 'stimulus' coordinate         │
│      │                                                                       │
│      └──→ Text embedded in assembly (no separate StimulusSet needed)         │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 3: Present text and get model responses                                │
│                                                                              │
│  predictions = candidate.digest_text(stimuli)                                │
│      │                                                                       │
│      │  ┌─────────────────────────────────────────────────────────────┐      │
│      │  │  INSIDE digest_text() — for each text:                      │      │
│      │  │                                                             │      │
│      │  │  1. Tokenize/preprocess text                                │      │
│      │  │  2. Forward pass through language model                     │      │
│      │  │  3. Extract activations (neural) or compute behavior        │      │
│      │  │     (reading times, next-word predictions, etc.)            │      │
│      │  │  4. Store in DataAssembly with stimulus coordinates         │      │
│      │  └─────────────────────────────────────────────────────────────┘      │
│      │                                                                       │
│      └──→ Returns dict: {'behavior': BehavioralAssembly} or                  │
│                        {'neural': NeuroidAssembly}                           │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 4: Align predictions with biological data                              │
│                                                                              │
│  # Attach presentation metadata for alignment                                │
│  attach_presentation_meta(predictions, self._assembly['presentation'])       │
│                                                                              │
│  # Filter/process as needed (e.g., exclude first words)                      │
│  predictions = predictions[predictions['word_within_sentence_id'] != 1]      │
│  targets = self._assembly[self._assembly['word_within_sentence_id'] != 1]    │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 5: Compare to biological data using metric                             │
│                                                                              │
│  raw_score = self._metric(predictions, targets)                              │
│      │                                                                       │
│      │  ┌──────────────────────────────────────────────────────────────┐     │
│      │  │  INSIDE metric (e.g., pearsonr):                             │     │
│      │  │                                                              │     │
│      │  │  1. Align by stimulus_id or word position                    │     │
│      │  │  2. Compute correlation (Pearson/Spearman)                   │     │
│      │  │     or regression (linear predictivity)                      │     │
│      │  │  3. Aggregate across subjects/neuroids                       │     │
│      │  └──────────────────────────────────────────────────────────────┘     │
│      │                                                                       │
│      └──→ Returns Score (e.g., 0.72) with metadata                           │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  STEP 6: Normalize by ceiling                                                │
│                                                                              │
│  score = ceiling_normalize(raw_score, self.ceiling)                          │
│      │                                                                       │
│      │  Formula: score = raw_score / ceiling                                 │
│      │                                                                       │
│      │  Example: raw_score=0.72, ceiling=0.85                                │
│      │           score = 0.72 / 0.85 ≈ 0.847                                 │
│      │                                                                       │
│      └──→ Returns final Score between 0 and 1                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

</details>

---

## 8. Real-World Language Benchmark Examples

### Example 1: Futrell2018 (Behavioral - Reading Times)

**Behavioral benchmark** comparing model reading times to human reading times:

```python
# Located: language/brainscore_language/benchmarks/futrell2018/benchmark.py

from brainscore_core.benchmarks import BenchmarkBase
from brainscore_core.metrics import Score, Metric
from brainscore_language import load_dataset, load_metric
from brainscore_language.artificial_subject import ArtificialSubject
from brainscore_language.utils import attach_presentation_meta
from brainscore_language.utils.ceiling import ceiling_normalize

class Futrell2018Pearsonr(BenchmarkBase):
    """
    Evaluate model ability to predict reading times on the natural stories corpus.
    Alignment of reading times between model and human subjects is evaluated via Pearson correlation.
    """
    
    def __init__(self):
        # Load behavioral data (reading times from human subjects)
        self.data = load_dataset('Futrell2018')
        
        # Use Pearson correlation metric
        self.metric = load_metric('pearsonr')
        
        # Compute ceiling using split-half consistency across subjects
        ceiler = SplitHalvesConsistency(
            num_splits=10, 
            split_coordinate='subject_id', 
            consistency_metric=self.metric
        )
        ceiling = ceiler(self.data)
        
        super(Futrell2018Pearsonr, self).__init__(
            identifier='Futrell2018-pearsonr',
            version=1,
            parent='behavior',
            ceiling=ceiling,
            bibtex=self.data.bibtex
        )
    
    def __call__(self, candidate: ArtificialSubject) -> Score:
        # STEP 1: Configure behavioral task
        candidate.start_behavioral_task(ArtificialSubject.Task.reading_times)
        
        # STEP 2: Extract text stimuli from assembly
        # Text is embedded in the data assembly (no separate StimulusSet)
        stimuli = self.data['word'].values
        
        # STEP 3: Get model predictions
        predictions = candidate.digest_text(stimuli)['behavior']
        
        # STEP 4: Align predictions with human data
        attach_presentation_meta(predictions, self.data['presentation'])
        
        # Exclude first words (often have different reading patterns)
        predictions = predictions[predictions['word_within_sentence_id'] != 1]
        targets = self.data[self.data['word_within_sentence_id'] != 1]
        targets = targets.mean('subject')  # Compare to average human
        
        # STEP 5: Compare using Pearson correlation
        raw_score = self.metric(predictions, targets)
        
        # STEP 6: Normalize by ceiling
        score = ceiling_normalize(raw_score, self.ceiling)
        return score
```

**Key features:**
- Uses `start_behavioral_task()` with `Task.reading_times`
- Text stimuli extracted directly from assembly (`self.data['word'].values`)
- No fitting stimuli needed (model must directly output reading times)
- Ceiling computed via split-half consistency across subjects
- Filters out first words for fair comparison

---

### Example 2: Pereira2018 (Neural - fMRI)

**Neural benchmark** comparing model activations to fMRI recordings from the language system:

```python
# Located: language/brainscore_language/benchmarks/pereira2018/benchmark.py

import xarray as xr
from brainio.assemblies import NeuroidAssembly
from brainscore_core.benchmarks import BenchmarkBase
from brainscore_core.metrics import Score
from brainscore_language import load_dataset, load_metric
from brainscore_language.artificial_subject import ArtificialSubject
from brainscore_language.utils.ceiling import ceiling_normalize

class _Pereira2018ExperimentLinear(BenchmarkBase):
    """
    Evaluate model ability to predict neural activity in the human language system
    in response to natural sentences, recorded by Pereira et al. 2018.
    Alignment evaluated via cross-validated linear predictivity.
    """
    
    def __init__(self, experiment: str, ceiling_s3_kwargs: dict):
        # Load neural data (fMRI recordings from language system)
        self.data = self._load_data(experiment)
        
        # Use linear predictivity metric (cross-validated regression)
        self.metric = load_metric('linear_pearsonr')
        
        # Load pre-computed ceiling from S3
        identifier = f'Pereira2018.{experiment}-linear'
        ceiling = self._load_ceiling(identifier=identifier, **ceiling_s3_kwargs)
        
        super(_Pereira2018ExperimentLinear, self).__init__(
            identifier=identifier,
            version=1,
            parent='Pereira2018-linear',
            ceiling=ceiling,
            bibtex=BIBTEX
        )
    
    def _load_data(self, experiment: str) -> NeuroidAssembly:
        # Load full dataset and filter by experiment
        data = load_dataset('Pereira2018.language')
        data = data.sel(experiment=experiment)  # Filter: '243sentences' or '384sentences'
        data = data.dropna('neuroid')  # Remove subjects who didn't complete this experiment
        data.attrs['identifier'] = f"{data.identifier}.{experiment}"
        return data
    
    def __call__(self, candidate: ArtificialSubject) -> Score:
        # STEP 1: Configure neural recording
        candidate.start_neural_recording(
            recording_target=ArtificialSubject.RecordingTarget.language_system,
            recording_type=ArtificialSubject.RecordingType.fMRI
        )
        
        # STEP 2: Extract text stimuli and organize by passage
        stimuli = self.data['stimulus']
        passages = self.data['passage_label'].values
        
        # STEP 3: Process passages separately (maintains model state within passages)
        predictions = []
        for passage in sorted(set(passages)):  # Sort for consistency
            # Get all stimuli for this passage
            passage_indexer = [stimulus_passage == passage for stimulus_passage in passages]
            passage_stimuli = stimuli[passage_indexer]
            
            # Get model neural activations for this passage
            passage_predictions = candidate.digest_text(passage_stimuli.values)['neural']
            
            # Preserve stimulus IDs for alignment
            passage_predictions['stimulus_id'] = 'presentation', passage_stimuli['stimulus_id'].values
            predictions.append(passage_predictions)
        
        # Concatenate all passages
        predictions = xr.concat(predictions, dim='presentation')
        
        # STEP 4: Compare using linear predictivity (cross-validated regression)
        raw_score = self.metric(predictions, self.data)
        
        # STEP 5: Normalize by ceiling
        score = ceiling_normalize(raw_score, self.ceiling)
        return score
```

**Key features:**
- Uses `start_neural_recording()` with `RecordingTarget.language_system` and `RecordingType.fMRI`
- Processes passages separately to maintain model state/context
- Uses linear predictivity metric (cross-validated regression, similar to PLS in vision)
- Pre-computed ceiling loaded from S3 (computed via split-half consistency)
- Handles multiple experiments (243 vs 384 sentences) as separate benchmarks

---

## 9. Example Benchmark Comparison

### Vision Benchmark

```python
class MyVisionBenchmark(BenchmarkBase):
    def __call__(self, candidate: BrainModel) -> Score:
        # Set up task
        candidate.start_task(BrainModel.Task.probabilities, fitting_stimuli)
        
        # Scale stimuli for visual field
        stimulus_set = place_on_screen(
            self._stimulus_set,
            target_visual_degrees=candidate.visual_degrees(),
            source_visual_degrees=self._visual_degrees
        )
        
        # Present stimuli and get predictions
        predictions = candidate.look_at(stimulus_set, number_of_trials=1)
        
        # Compare to biological data
        raw_score = self._metric(predictions, self._assembly)
        return self.ceil_score(raw_score, self.ceiling)
```

### Language Benchmark

```python
class MyLanguageBenchmark(BenchmarkBase):
    def __call__(self, candidate: ArtificialSubject) -> Score:
        # Set up task
        candidate.start_behavioral_task(ArtificialSubject.Task.reading_times)
        
        # Extract text stimuli from assembly
        stimuli = self._assembly['word'].values
        
        # Present text and get predictions
        predictions = candidate.digest_text(stimuli)['behavior']
        
        # Compare to biological data
        raw_score = self._metric(predictions, self._assembly)
        return self.ceil_score(raw_score, self.ceiling)
```

---

## 10. What Remains the Same

These concepts apply equally to **both** vision and language benchmarks:

| Concept | Description |
|---------|-------------|
| `BenchmarkBase` | Both inherit from this class |
| `Score` objects | Same structure with `.values` and `.attrs` |
| Ceiling calculations | Same methods (split-half, cross-subject) |
| DataAssembly structure | Same xarray-based coordinate system |
| Metric interface | Same `__call__(assembly1, assembly2) -> Score` |
| Plugin registration | Same `benchmark_registry['identifier']` pattern |
| Testing patterns | Same pytest structure |
| Naming conventions | Same `AuthorYear-metric` format |
| Data packaging pipeline | Same validate → package → register flow |

---

## Quick Checklist: Adapting Vision to Language

If converting a vision benchmark pattern to language:

- [ ] Change imports from `brainscore_vision` to `brainscore_language`
- [ ] Replace `BrainModel` with `ArtificialSubject`
- [ ] Replace `look_at()` with `digest_text()`
- [ ] Replace `start_task()` with `start_behavioral_task()`
- [ ] Remove `place_on_screen()` and `visual_degrees` references
- [ ] Consider embedding text stimuli in DataAssembly instead of using StimulusSet
- [ ] Update brain region references if applicable
- [ ] Update task types to language-specific tasks

---

## Next Steps

- **[Submitting Benchmarks](/tutorials/benchmarks/submitting-benchmarks/)** — How to submit your benchmark to Brain-Score

---

## Resources

- [Brain-Score Website](https://brain-score.org)
- [Vision GitHub Repository](https://github.com/brain-score/vision)
- [Language GitHub Repository](https://github.com/brain-score/language)

