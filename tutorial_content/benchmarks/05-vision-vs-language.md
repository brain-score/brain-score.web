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

## 7. Example Benchmark Comparison

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

## 8. What Remains the Same

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

## Resources

- [Brain-Score Website](https://brain-score.org)
- [Vision GitHub Repository](https://github.com/brain-score/vision)
- [Language GitHub Repository](https://github.com/brain-score/language)

