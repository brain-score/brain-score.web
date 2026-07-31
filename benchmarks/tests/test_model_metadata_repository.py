from unittest import TestCase

from benchmarks.model_metadata import get_model_metadata


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
        self.assertEqual(metadata["verification"]["total"], 31)

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

    def test_missing_model_returns_none(self):
        self.assertIsNone(get_model_metadata("vision", "not-a-model"))
