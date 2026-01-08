---
title: Submitting Benchmarks
description: How to submit your benchmark to the Brain-Score platform
order: 6
category: benchmarks
---

# Submitting Benchmarks

Once you've created and tested your benchmark locally, the final step is submitting it to the Brain-Score platform. This tutorial walks you through the complete submission process—from packaging your data to creating a pull request.

> ⚠️ **Note**: All data uploaded to Brain-Score is set by default to be publicly accessible in the spirit of open science. If you would like to **ensure your data remains private**, please contact a member of the Brain-Score team by either joining our [Slack](https://www.brain-score.org/community) or making a [GitHub Issue](https://github.com/brain-score/vision/issues). 
> Additionally, all benchmark scores, regardless if the underlying data is public or private, is set to being publicly visible.

## Summary

The benchmark submission process follows these key steps:

```
1. Package Data     → Validate and format stimuli + assemblies
2. Create Benchmark → Implement benchmark class with ceiling
3. Test Locally     → Write and run unit tests
4. Upload Data      → Package and upload to S3
5. Submit PR        → Fork, commit, and create pull request
6. Review Process   → Address feedback and iterate
7. Merge & Deploy   → Benchmark goes live on Brain-Score
```

---

## Overview of Data Packaging

Before submitting a benchmark, your experimental data must be packaged in Brain-Score's standardized format. Here's a quick summary of the key steps (see [Data Packaging](/tutorials/benchmarks/data-packaging/) for details):

### Stimulus Set Preparation

```python
from brainscore_core.supported_data_standards.brainio.stimuli import StimulusSet

# 1. Create metadata DataFrame
stimuli_data = [
    {'stimulus_id': 'img_001', 'category': 'face', 'condition': 'A'},
    {'stimulus_id': 'img_002', 'category': 'object', 'condition': 'B'},
    # ... more stimuli
]

stimulus_set = StimulusSet(stimuli_data)

# 2. Map stimulus IDs to file paths
stimulus_set.stimulus_paths = {
    'img_001': '/path/to/image1.jpg',
    'img_002': '/path/to/image2.jpg',
}

# 3. Set unique identifier
stimulus_set.name = 'MyExperiment2024'
```

### Data Assembly Creation

```python
from brainscore_core.supported_data_standards.brainio.assemblies import BehavioralAssembly

assembly = BehavioralAssembly(
    response_data,
    coords={
        'stimulus_id': ('presentation', stimulus_ids),
        'subject': ('presentation', subject_ids),
        'condition': ('presentation', conditions),
    },
    dims=['presentation']
)
```

### Validation Checklist

Before packaging, verify:

| Check | Command |
|-------|---------|
| Unique stimulus IDs | `assert stimulus_set['stimulus_id'].nunique() == len(stimulus_set)` |
| All files exist | Verify all paths in `stimulus_paths` are valid |
| No NaN values | `assert not np.isnan(assembly.values).any()` |
| Aligned coordinates | Ensure `stimulus_id` matches between StimulusSet and Assembly |

---

## Overview of Creating a Benchmark

Your benchmark implementation should follow Brain-Score's plugin architecture. Here's the essential structure:

### Benchmark Class

```python
from brainscore_vision.benchmarks import BenchmarkBase
from brainscore_vision.model_interface import BrainModel
from brainscore_core.metrics import Score

BIBTEX = """
@article{author2024,
  title={Your Paper Title},
  author={Author, A. and Coauthor, B.},
  journal={Journal Name},
  year={2024}
}
"""

class MyExperiment2024Benchmark(BenchmarkBase):
    def __init__(self):
        self._assembly = load_dataset('MyExperiment2024')
        self._stimulus_set = load_stimulus_set('MyExperiment2024')
        self._metric = load_metric('accuracy')
        self._visual_degrees = 8
        
        super().__init__(
            identifier='MyExperiment2024-accuracy',
            version=1,
            ceiling_func=lambda: self._compute_ceiling(),
            parent='behavior',  # or 'V1', 'V4', 'IT', etc.
            bibtex=BIBTEX
        )
    
    def __call__(self, candidate: BrainModel) -> Score:
        # Implementation here
        pass
    
    def _compute_ceiling(self) -> Score:
        # Ceiling calculation here
        pass
```

### Registration

```python
# __init__.py
from brainscore_vision import benchmark_registry
from .benchmark import MyExperiment2024Benchmark

benchmark_registry['MyExperiment2024-accuracy'] = MyExperiment2024Benchmark
```

### Plugin Directory Structure

```
vision/brainscore_vision/benchmarks/myexperiment2024/
├── __init__.py          # Registration
├── benchmark.py         # Benchmark implementation
├── test.py              # Unit tests
└── requirements.txt     # Dependencies (optional)
```

---

## Testing Your Benchmark Locally

Before submitting, thoroughly test your benchmark to ensure it works correctly.

### 1. Install Development Dependencies

```bash
# Clone the vision repository
git clone https://github.com/brain-score/vision.git
cd vision

# Install in development mode
pip install -e ".[test]"
```

### 2. Create Unit Tests

Create a `test.py` file in your benchmark directory:

```python
# vision/brainscore_vision/benchmarks/myexperiment2024/test.py

import pytest
from brainscore_vision import load_benchmark

@pytest.mark.private_access
class TestMyExperiment2024:
    
    def test_benchmark_loads(self):
        """Verify benchmark can be loaded."""
        benchmark = load_benchmark('MyExperiment2024-accuracy')
        assert benchmark is not None
        assert benchmark.identifier == 'MyExperiment2024-accuracy'
    
    def test_ceiling_valid(self):
        """Verify ceiling is computed and valid."""
        benchmark = load_benchmark('MyExperiment2024-accuracy')
        ceiling = benchmark.ceiling
        assert 0 < ceiling <= 1
        assert hasattr(ceiling, 'attrs')
    
    def test_benchmark_runs(self):
        """Test benchmark with a simple model."""
        from brainscore_vision import load_model
        
        benchmark = load_benchmark('MyExperiment2024-accuracy')
        model = load_model('alexnet')  # or another simple model
        
        score = benchmark(model)
        
        assert score == 0.212 # Replace with actual expected score
        assert hasattr(score, 'attrs')
        assert 'raw' in score.attrs or 'ceiling' in score.attrs
```

### 3. Run Tests Locally

```bash
# Run your specific tests
pytest brainscore_vision/benchmarks/myexperiment2024/test.py -v
```

### 4. Manual Verification

```python
# Quick manual test
from brainscore_vision import load_benchmark, load_model

benchmark = load_benchmark('MyExperiment2024-accuracy')
model = load_model('alexnet')

score = benchmark(model)
print(f"Score: {score.values:.4f}")
print(f"Ceiling: {benchmark.ceiling.values:.4f}")
print(f"Raw attrs: {score.attrs}")
```

---

## Uploading Data to Brain-Score

Once your data is validated and your benchmark is tested locally, you need to upload the data to Brain-Score's S3 storage.

### 1. Package Your Data Locally

```python
# Located: core/brainscore_core/supported_data_standards/brainio/packaging.py

from brainscore_core.supported_data_standards.brainio.packaging import package_stimulus_set_locally
from brainscore_core.supported_data_standards.brainio import packaging

# Package stimulus set
package_stimulus_set_locally(
    proto_stimulus_set=stimulus_set,
    stimulus_set_identifier='MyExperiment2024',
)
'''
Output:
 {
  'identifier': 'MyExperiment2024',
  'csv_path': '~/Downloads/brainscore_packages/stimulus_MyExperiment2024.csv',
  'zip_path': '~/Downloads/brainscore_packages/stimulus_MyExperiment2024.zip',
  'csv_sha1': '1d47ea4a09ddd72cebabca95b985646650f21646',
  'zip_sha1': 'c96036d459f0a2ce4494ba73a2b18b8eec59f6b6'
}
'''

# Package data assembly
packaging.package_data_assembly_locally(
    proto_data_assembly=assembly,
    assembly_identifier='MyExperiment2024',
    stimulus_set_identifier='MyExperiment2024',
    assembly_class_name='NeuroidAssembly',  # or 'BehavioralAssembly'
)
'''
Output:
 {
  'identifier': 'MyExperiment2024',
  'path': '~/Downloads/brainscore_packages/assy_MyExperiment2024.nc',
  'sha1': '3c45d95e2e61616c885758df0d463fddbfc2b427',
  'cls': 'NeuroidAssembly'
}
'''
```

Save the SHA hashes — you'll need them for registration.

### 2. Upload to Brain-Score

Upload your packaged files (CSV, ZIP, and NC) to Brain-Score's S3 storage through the [Brain-Score website](https://www.brain-score.org). Navigate to the upload page through the Central Profile Page.

After uploading, you'll receive the S3 `bucket` path and `version_id` values needed for registration.

### 3. Register in Data Plugin

Create your data plugin's `__init__.py` with the upload metadata:

```python
# vision/brainscore_vision/data/myexperiment2024/__init__.py

from brainscore_vision import data_registry, stimulus_set_registry, load_stimulus_set
from brainscore_core.supported_data_standards.brainio.s3 import load_stimulus_set_from_s3, load_assembly_from_s3
from brainscore_core.supported_data_standards.brainio.assemblies import NeuroidAssembly

stimulus_set_registry['MyExperiment2024'] = lambda: load_stimulus_set_from_s3(
    identifier='MyExperiment2024',
    bucket='brainscore-storage/brainscore-vision/data/...',  # S3 path (from upload)
    csv_sha1='1d47ea4a09ddd72cebabca95b985646650f21646',      # From packaging
    zip_sha1='c96036d459f0a2ce4494ba73a2b18b8eec59f6b6',      # From packaging
    csv_version_id='U405jdh2ECWCzwoZauxh0VNDSAHAb.2s',        # From upload
    zip_version_id='cTVQxPGpom_seCpwN2ltG_LK7eYGbZid',        # From upload
    filename_prefix='stimulus_'
)

data_registry['MyExperiment2024'] = lambda: load_assembly_from_s3(
    identifier='MyExperiment2024',
    bucket='brainscore-storage/brainscore-vision/data/...',  # S3 path (from upload)
    sha1='3c45d95e2e61616c885758df0d463fddbfc2b427',          # From packaging
    version_id='yusgi5xpyrNzU10cjk69Z49G.CSyujXO',            # From upload
    cls=NeuroidAssembly,
    stimulus_set_loader=lambda: load_stimulus_set('MyExperiment2024')
)
```

For complete details on data packaging, see [Data Packaging](/tutorials/benchmarks/data-packaging/).

---

## Creating a GitHub PR

With your data uploaded and code tested, you're ready to submit a pull request.

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/vision.git
cd vision
git remote add upstream https://github.com/brain-score/vision.git
```

### 2. Create a Feature Branch

```bash
git checkout -b benchmark/myexperiment2024
```

### 3. Add Your Files

Your submission should include:

```
vision/
├── brainscore_vision/
│   ├── benchmarks/
│   │   └── myexperiment2024/
│   │       ├── __init__.py        # Benchmark registration
│   │       ├── benchmark.py       # Benchmark implementation
│   │       ├── test.py            # Unit tests
│   │       └── requirements.txt   # Extra dependencies (if any)
│   └── data/
│       └── myexperiment2024/
│           ├── __init__.py        # Data registration
│           └── test.py            # Data loading tests
```

### 4. Commit and Push

```bash
git add .
git commit -m "Add MyExperiment2024 benchmark

- Neural/behavioral benchmark comparing model X to human data
- Uses accuracy/PLS metric with split-half ceiling
- Based on Author et al. (2024) paper"

git push origin benchmark/myexperiment2024
```

### 5. Create Pull Request

1. Go to [github.com/brain-score/vision](https://github.com/brain-score/vision)
2. Click "New Pull Request"
3. Select your fork and branch
4. Fill out the PR template with:
   - **Description**: What the benchmark measures
   - **Data source**: Paper citation and data availability
   - **Testing**: Confirm tests pass locally
   - **Expected scores**: Document expected scores for at least one model

### PR Template Example

```markdown
## Benchmark: MyExperiment2024

### Description
This benchmark evaluates model alignment with human behavioral data from 
Author et al. (2024), measuring accuracy on a visual categorization task.

### Components
- **Stimulus Set**: 500 images across 10 categories
- **Data Assembly**: Behavioral responses from 50 human subjects
- **Metric**: Accuracy with split-half ceiling

### Testing
- [x] All unit tests pass locally
- [x] Benchmark loads correctly
- [x] Ceiling is valid (0.85 ± 0.02)
- [x] Tested with alexnet: score = 0.42

### Citation
@article{author2024, ...}
```

---

## What to Expect

After submitting your PR, here's the typical review process:


### 1. Code Review

A Brain-Score maintainer will review your submission for:

| Aspect | What They Check |
|--------|-----------------|
| **Code quality** | Clean, readable, follows conventions |
| **Scientific validity** | Benchmark correctly implements the paper's methodology |
| **Data integrity** | Data is properly packaged and accessible |
| **Ceiling implementation** | Ceiling is appropriate and correctly computed |
| **Testing coverage** | Tests adequately verify benchmark functionality |
| **Documentation** | Code is well-commented, bibtex is correct |

### 2. Timeline

| Stage | Typical Duration |
|-------|------------------|
| Initial review | 1-2 weeks |
| Revisions (if needed) | Varies |
| Final approval | 1-3 days |
| Merge and deployment | Same day |

### 3. After Merge

Once your PR is merged:

1. **Benchmark becomes available** on the Brain-Score platform
2. **Models are automatically scored** against your benchmark
3. **Leaderboard updates** to show model performance
4. **Your citation** is displayed with the benchmark

### 5. Common Review Feedback

Be prepared to address:

- **Ceiling concerns**: "Can you explain why the ceiling is computed this way?"
- **Test coverage**: "Please add a test for the edge case where..."
- **Documentation**: "The bibtex is missing"
- **Code style**: "Please use consistent naming conventions"

---

## Submission Checklist

Before submitting your PR, verify:

### Data
- [ ] Stimulus set has unique IDs and all files exist
- [ ] Data assembly has no NaN values
- [ ] Data is uploaded to S3 with correct SHA hashes
- [ ] Data registration includes proper loader functions

### Benchmark
- [ ] Inherits from `BenchmarkBase` (or appropriate helper)
- [ ] `identifier` follows naming convention: `AuthorYear-metric`
- [ ] `version` is set (start at 1)
- [ ] `ceiling_func` is implemented and returns valid Score
- [ ] `bibtex` includes complete citation
- [ ] `parent` is set correctly (V1, V4, IT, behavior, etc.)

### Testing
- [ ] Unit tests verify benchmark loads
- [ ] Unit tests verify ceiling is valid
- [ ] Unit tests verify benchmark runs with at least one model
- [ ] All tests pass locally

### Documentation
- [ ] Code is well-commented
- [ ] PR description is complete
- [ ] Expected scores documented for reference model

---

## Getting Help

If you encounter issues during submission:

- **GitHub Issues**: Open an issue on the [vision repository](https://github.com/brain-score/vision/issues)
- **Slack**: [Slack](https://www.brain-score.org/community)

---

## Summary

The benchmark submission process follows these key steps:

```
1. Package Data     → Validate and format stimuli + assemblies
2. Create Benchmark → Implement benchmark class with ceiling
3. Test Locally     → Write and run unit tests
4. Upload Data      → Package and upload to S3
5. Submit PR        → Fork, commit, and create pull request
6. Review Process   → Address feedback and iterate
7. Merge & Deploy   → Benchmark goes live on Brain-Score
```

Congratulations on contributing to Brain-Score! Your benchmark will help evaluate how well models align with biological intelligence.


