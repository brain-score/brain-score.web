import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import TestCase

import yaml


REPO_ROOT = Path(__file__).parents[2]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_model_metadata.py"
CATALOG_BUILDER_PATH = REPO_ROOT / "scripts" / "build_model_metadata_catalog.py"
EXAMPLE_BUILDER_PATH = (
    REPO_ROOT
    / "benchmarks"
    / "model_metadata"
    / "examples"
    / "create_example_workbook.py"
)
EXAMPLE_GOLDEN_PATH = (
    REPO_ROOT
    / "benchmarks"
    / "model_metadata"
    / "examples"
    / "synthetic"
    / "metadata.yml"
)
SOURCE_ROOT = REPO_ROOT / "benchmarks" / "model_metadata" / "source"
DATA_DIR = REPO_ROOT / "benchmarks" / "model_metadata" / "data"

GENERATOR = runpy.run_path(GENERATOR_PATH)
CATALOG_BUILDER = runpy.run_path(CATALOG_BUILDER_PATH)
DEFAULT_SCHEMA_PATH = GENERATOR["DEFAULT_SCHEMA_PATH"]
model_columns = GENERATOR["model_columns"]
merge_model_columns = GENERATOR["merge_model_columns"]
parse_datasets = GENERATOR["parse_datasets"]
parse_curation_confidence = GENERATOR["parse_curation_confidence"]
parse_visual_degrees = GENERATOR["parse_visual_degrees"]
parse_base_model = GENERATOR["parse_base_model"]
validate_generated = GENERATOR["validate_generated"]
validate_json_schema = GENERATOR["validate_json_schema"]
build_catalog = CATALOG_BUILDER["build_catalog"]


def workbook_rows():
    rows = [[None] * 6 for _ in range(34)]
    rows[1][0] = "model_name"
    rows[2][0] = "base model"
    rows[4][0] = "model_ID"
    rows[5][0] = "architecture_family"
    return rows


class TestBundledAssets(TestCase):
    def test_default_schema_is_bundled_with_web_metadata(self):
        self.assertTrue(DEFAULT_SCHEMA_PATH.is_file())

    def test_all_source_records_match_bundled_schema(self):
        schema = json.loads(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
        metadata_paths = sorted(SOURCE_ROOT.rglob("metadata.yml"))

        self.assertEqual(len(metadata_paths), 43)
        for metadata_path in metadata_paths:
            metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
            validate_generated(metadata)
            validate_json_schema(metadata, schema, schema)

    def test_source_snapshot_rebuilds_committed_catalog(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "catalog"

            self.assertEqual(build_catalog(SOURCE_ROOT, output_dir), 43)
            for expected_path in sorted(DATA_DIR.glob("*.csv")):
                actual_path = output_dir / expected_path.name
                self.assertEqual(
                    actual_path.read_bytes(),
                    expected_path.read_bytes(),
                    expected_path.name,
                )

    def test_workbook_cli_matches_golden_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            workbook_path = temporary_root / "synthetic-metadata.xlsx"
            vision_root = temporary_root / "vision"
            plugin_root = (
                vision_root
                / "brainscore_vision"
                / "models"
                / "example_model"
            )

            subprocess.run(
                [
                    sys.executable,
                    str(EXAMPLE_BUILDER_PATH),
                    str(workbook_path),
                    "--repo-root",
                    str(vision_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR_PATH),
                    str(workbook_path),
                    "--repo-root",
                    str(vision_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            generated_path = plugin_root / "metadata.yml"
            self.assertEqual(
                generated_path.read_bytes(),
                EXAMPLE_GOLDEN_PATH.read_bytes(),
            )


class TestModelColumns(TestCase):
    def test_optional_blank_does_not_exclude_model(self):
        rows = workbook_rows()
        rows[1][4] = "AlexNet"

        self.assertEqual(list(model_columns(rows)), [4])

    def test_empty_column_is_ignored(self):
        rows = workbook_rows()

        self.assertEqual(list(model_columns(rows)), [])

    def test_duplicate_model_uses_latest_with_fallback(self):
        rows = workbook_rows()
        styles = [[0] * 6 for _ in range(34)]
        rows[1][4] = "Earlier"
        rows[2][4] = "Base model"
        rows[1][5] = "Latest"

        merged_rows, _ = merge_model_columns(rows, styles, [4, 5])

        self.assertEqual(merged_rows[1][1], "Latest")
        self.assertEqual(merged_rows[2][1], "Base model")


class TestDatasetRoles(TestCase):
    def test_uses_nearest_training_stage(self):
        datasets = parse_datasets("Stage1: WIT-400M; Stage2: ImageNet-1k")

        self.assertEqual(
            [dataset["role"] for dataset in datasets],
            ["pretraining", "fine_tuning"],
        )


class TestAdditionalWorkbookFields(TestCase):
    def test_parses_visual_degrees_with_description(self):
        self.assertEqual(
            parse_visual_degrees("8 degrees (VOneNet family default convention)"),
            8.0,
        )

    def test_normalizes_curation_confidence(self):
        self.assertEqual(parse_curation_confidence("Medium/High"), "medium_high")


class TestBaseModels(TestCase):
    def test_maps_registry_base_model(self):
        self.assertEqual(
            parse_base_model("AlexNet"),
            {
                "identifier": "alexnet",
                "name": "AlexNet",
                "relationship": "variant_of",
            },
        )

    def test_maps_direct_parent_from_lineage_description(self):
        self.assertEqual(
            parse_base_model("AlexNet, AlexNet-SIN")["identifier"],
            "AlexNet_SIN",
        )

    def test_preserves_unmapped_base_without_inferring_relationship(self):
        self.assertEqual(
            parse_base_model("Custom research model"),
            {"name": "Custom research model"},
        )
