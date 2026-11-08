from pathlib import Path

from django.template.loader import get_template
from django.test import SimpleTestCase

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates"


class TemplateCompileTests(SimpleTestCase):
    def test_every_template_compiles(self):
        # Catches merge damage such as a block defined twice, without a database.
        for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
            name = path.relative_to(TEMPLATE_ROOT).as_posix()
            with self.subTest(template=name):
                get_template(name)
