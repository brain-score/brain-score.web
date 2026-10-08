from django.template.loader import render_to_string
from django.test import SimpleTestCase


class TestSpeciesFilterFlag(SimpleTestCase):
    def render(self, show):
        return render_to_string('benchmarks/leaderboard/ag-grid-leaderboard-content.html',
                                {'domain': 'vision', 'show_species_filter': show})

    def test_species_filter_hidden_by_default(self):
        self.assertNotIn('id="speciesFilter"', self.render(False))

    def test_species_filter_shown_when_enabled(self):
        self.assertIn('id="speciesFilter"', self.render(True))
