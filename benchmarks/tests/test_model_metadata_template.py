from pathlib import Path
from unittest import TestCase

from django.conf import settings
from django.template import Context, Engine

from benchmarks.model_metadata import get_model_metadata, with_model_card_ids


TEMPLATE_DIR = Path(__file__).parents[1] / "templates"

if not settings.configured:
    settings.configure(USE_L10N=False)


class TestModelMetadataTemplate(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = Engine(dirs=[TEMPLATE_DIR]).get_template(
            "benchmarks/_model_metadata.html"
        )

    def test_renders_model_card_sections(self):
        metadata = get_model_metadata(
            "vision", "convnext_xxlarge:clip_laion2b_soup_ft_in1k"
        )

        html = self.template.render(Context({"model_metadata": metadata}))

        self.assertIn("data-model-metadata", html)
        self.assertIn("At-a-glance", html)
        self.assertIn("845.5M", html)
        self.assertIn("LAION-2B", html)
        self.assertIn("Recommended applications", html)

    def test_renders_nothing_without_metadata(self):
        html = self.template.render(Context({"model_metadata": None}))

        self.assertEqual(html.strip(), "")

    def test_hides_empty_metadata_card(self):
        metadata = get_model_metadata("vision", "AlexNet_SIN_fov12")

        html = self.template.render(Context({"model_metadata": metadata}))

        self.assertEqual(html.strip(), "")

    def test_renders_provenance_counts(self):
        template = Engine(dirs=[TEMPLATE_DIR]).get_template(
            "benchmarks/_model_metadata_provenance.html"
        )
        metadata = get_model_metadata(
            "vision", "convnext_xxlarge:clip_laion2b_soup_ft_in1k"
        )

        html = template.render(Context({"model_metadata": metadata}))

        self.assertIn("19</strong> verified", html)
        self.assertIn("7</strong> inferred", html)
        self.assertIn("7</strong> undocumented", html)
        self.assertIn("model-sidebar-card", html)

    def test_renders_lineage_chain_and_related_variants(self):
        template = Engine(dirs=[TEMPLATE_DIR]).get_template(
            "benchmarks/_model_metadata_lineage.html"
        )
        metadata = get_model_metadata("vision", "AlexNet_SIN_fov12")
        metadata = with_model_card_ids(
            metadata,
            {"alexnet": 982, "AlexNet_SIN": 2168},
        )

        html = template.render(Context({"model_metadata": metadata}))

        self.assertIn("data-model-lineage", html)
        self.assertIn("AlexNet", html)
        self.assertIn("AlexNet SIN", html)
        self.assertIn("AlexNet_SIN_fov12", html)
        self.assertIn('href="/model/vision/982"', html)
        self.assertIn('href="/model/vision/2168"', html)

    def test_links_and_progressively_hides_related_variants(self):
        template = Engine(dirs=[TEMPLATE_DIR]).get_template(
            "benchmarks/_model_metadata_lineage.html"
        )
        metadata = get_model_metadata("vision", "alexnet")
        first_related = metadata["lineage"]["related_models"][0]
        metadata = with_model_card_ids(metadata, {first_related["identifier"]: 2342})

        html = template.render(Context({"model_metadata": metadata}))

        self.assertIn('href="/model/vision/2342"', html)
        self.assertEqual(html.count("data-related-variant"), 8)
        self.assertEqual(html.count("data-related-variant hidden"), 5)
        self.assertIn("data-lineage-toggle", html)
        self.assertIn("+5 more metadata-covered variants", html)

    def test_hides_lineage_card_without_relationships(self):
        template = Engine(dirs=[TEMPLATE_DIR]).get_template(
            "benchmarks/_model_metadata_lineage.html"
        )
        metadata = get_model_metadata("vision", "pixels")

        html = template.render(Context({"model_metadata": metadata}))

        self.assertEqual(html.strip(), "")

    def test_model_page_uses_scoped_card_containers(self):
        model_template = (TEMPLATE_DIR / "benchmarks" / "model.html").read_text()
        trend_template = (
            TEMPLATE_DIR / "benchmarks" / "_model_trend_panel.html"
        ).read_text()

        for class_name in ("model-sidebar-card", "model-page-card", "model-section-title"):
            self.assertIn(class_name, model_template)
        self.assertIn("model-page-card", trend_template)
        self.assertIn("model-section-title", trend_template)
