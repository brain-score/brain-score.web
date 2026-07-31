from unittest import TestCase

from benchmarks.model_metadata import get_model_metadata
from benchmarks.model_metadata.repository import _attach_lineage


class TestModelMetadataRepository(TestCase):
    def test_loads_completed_model(self):
        metadata = get_model_metadata(
            "vision", "convnext_xxlarge:clip_laion2b_soup_ft_in1k"
        )

        self.assertEqual(metadata["parameter_count"], 845_500_000)
        self.assertEqual(metadata["parameter_count_display"], "845.5M")
        self.assertEqual(metadata["input_resolution_display"], "256 × 256")
        self.assertEqual(metadata["architecture_family_display"], "Convolutional neural network")
        self.assertEqual(
            [dataset["role"] for dataset in metadata["datasets"]],
            ["pretraining", "fine_tuning"],
        )
        self.assertEqual(metadata["verification"]["total"], 33)

    def test_preserves_repeated_sections(self):
        metadata = get_model_metadata("vision", "voneresnet-50")

        self.assertIn("applications", metadata["intended_use"])
        self.assertIn("creators", metadata["contributors"])
        self.assertEqual(metadata["license"], "GNU GPL v3+")

    def test_distinguishes_pretraining_from_fine_tuning(self):
        metadata = get_model_metadata(
            "vision", "vit_large_patch14_clip_224:openai_ft_in1k"
        )

        self.assertEqual(
            [dataset["role"] for dataset in metadata["datasets"]],
            ["pretraining", "fine_tuning"],
        )

    def test_loads_model_with_blank_optional_fields(self):
        metadata = get_model_metadata("vision", "alexnet")

        self.assertEqual(metadata["parameter_count"], 61_100_840)
        self.assertIsNone(metadata["visual_degrees"])

    def test_loads_model_without_architecture(self):
        metadata = get_model_metadata("vision", "AT_efficientnet-b2")

        self.assertEqual(metadata["architecture_family"], "")
        self.assertEqual(metadata["architecture_description"], "")

    def test_loads_visual_degrees_and_curation_confidence(self):
        visual_metadata = get_model_metadata("vision", "voneresnet-50")
        confidence_metadata = get_model_metadata("vision", "AdvProp_efficientnet-b2")

        self.assertEqual(visual_metadata["visual_degrees"], 8.0)
        self.assertEqual(
            visual_metadata["visual_degrees_description"],
            "8 degrees (VOneNet family default convention)",
        )
        self.assertEqual(confidence_metadata["curation_confidence"], "medium_high")

    def test_builds_recursive_alexnet_lineage(self):
        metadata = get_model_metadata("vision", "AlexNet_SIN_fov12")

        self.assertEqual(
            [ancestor["identifier"] for ancestor in metadata["lineage"]["ancestors"]],
            ["alexnet", "AlexNet_SIN"],
        )
        self.assertTrue(metadata["lineage"]["has_relationships"])

    def test_limits_related_alexnet_variants(self):
        metadata = get_model_metadata("vision", "alexnet")

        self.assertEqual(len(metadata["lineage"]["related_models"]), 3)
        self.assertEqual(metadata["lineage"]["hidden_related_count"], 5)

    def test_keeps_external_convnext_base_unlinked(self):
        metadata = get_model_metadata("vision", "convnext_tiny:in12k_ft_in1k")

        self.assertEqual(
            metadata["lineage"]["ancestors"][0],
            {
                "identifier": "convnext-tiny",
                "display_name": "ConvNeXt-Tiny",
                "has_metadata": False,
            },
        )

    def test_hides_lineage_without_relationships(self):
        metadata = get_model_metadata("vision", "pixels")

        self.assertFalse(metadata["lineage"]["has_relationships"])

    def test_stops_recursive_lineage_at_cycle(self):
        models = {
            ("vision", "a"): {"identifier": "a", "display_name": "A"},
            ("vision", "b"): {"identifier": "b", "display_name": "B"},
        }
        relationships = {
            ("vision", "a"): {
                "base_identifier": "b",
                "base_name": "B",
                "relationship": "variant_of",
            },
            ("vision", "b"): {
                "base_identifier": "a",
                "base_name": "A",
                "relationship": "variant_of",
            },
        }

        _attach_lineage(models, relationships)

        self.assertEqual(len(models[("vision", "a")]["lineage"]["ancestors"]), 1)

    def test_missing_model_returns_none(self):
        self.assertIsNone(get_model_metadata("vision", "not-a-model"))
