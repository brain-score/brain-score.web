"""Contributor-facing YAML template for the proposed metadata format."""
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def schema_yaml():
    path = Path(__file__).resolve().parents[2] / 'static/benchmarks/schemas/metadata-v2.0.yaml'
    return path.read_text(encoding='utf-8')
