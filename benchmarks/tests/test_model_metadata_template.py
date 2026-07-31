from pathlib import Path
from unittest import TestCase

from django.conf import settings
from django.template import Context, Engine

from benchmarks.model_metadata import get_model_metadata


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
        self.assertIn("5</strong> undocumented", html)
        self.assertIn("model-sidebar-card", html)

    def test_model_page_uses_scoped_card_styles(self):
        model_template = (TEMPLATE_DIR / "benchmarks" / "model.html").read_text()
        trend_template = (
            TEMPLATE_DIR / "benchmarks" / "_model_trend_panel.html"
        ).read_text()

        for class_name in (
            "model-banner-actions",
            "model-sidebar-card",
            "model-scores-card",
            "model-usage-card",
            "model-berg-card",
            "model-bibtex-card",
        ):
            self.assertIn(class_name, model_template)
        self.assertIn("model-trend-card", trend_template)
