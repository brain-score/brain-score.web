"""Tests for the Compare Representations panel.

The panel is additive to an existing page, so the property that matters most is
that it cannot take the compare page down with it.
"""
import json
from unittest import mock

from django.test import RequestFactory, TestCase
from django.urls import reverse

from benchmarks.views import compare_representations as cr


class TestRepresentationsData(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _get(self, **params):
        request = self.rf.get('/vision/compare/representations/data/', params)
        return json.loads(cr.data(request, domain='vision').content)

    def test_returns_the_comparison_table(self):
        payload = self._get()
        assert payload['domain'] == 'vision'
        assert payload['comparisons'], "fixture should ship at least one comparison"
        for row in payload['comparisons']:
            assert 'stimulus_set' in row and 'cka' in row

    def test_embeddings_are_withheld_until_asked_for(self):
        """They dominate the payload; the table alone is what the tab first needs."""
        assert 'embeddings' not in self._get()

    def test_embeddings_returned_for_a_selected_set(self):
        first = self._get()['comparisons'][0]['stimulus_set']
        payload = self._get(stimulus_set=first)
        assert payload['selected'] == first
        assert payload['embeddings'], "expected per-model coordinates"
        for coords in payload['embeddings'].values():
            assert all(len(p) == 2 for p in coords), "embeddings must be 2D"

    def test_unknown_stimulus_set_is_empty_not_an_error(self):
        payload = self._get(stimulus_set='does-not-exist')
        assert payload['embeddings'] == {}

    def test_readout_only_entries_are_flagged(self):
        """A readout-only comparison is classifier agreement, not representational
        similarity. The distinction has to survive into the payload or the UI
        cannot label it, and an unlabelled number here is a misleading one."""
        for row in self._get()['comparisons']:
            assert isinstance(row.get('readout_only'), bool)


class TestDegradesRatherThanBreaking(TestCase):
    """The compare page must render even with no artifacts at all."""

    def test_missing_fixture_yields_empty_payload(self):
        with mock.patch.object(cr, '_FIXTURE', '/nonexistent/path.json'):
            request = RequestFactory().get('/vision/compare/representations/data/')
            payload = json.loads(cr.data(request, domain='vision').content)
        assert payload['comparisons'] == []
        assert payload['models'] == []

    def test_malformed_fixture_yields_empty_payload(self, ):
        with mock.patch('builtins.open', mock.mock_open(read_data='{not json')):
            request = RequestFactory().get('/vision/compare/representations/data/')
            payload = json.loads(cr.data(request, domain='vision').content)
        assert payload['comparisons'] == []


class TestRouting(TestCase):
    def test_route_exists_for_each_domain(self):
        for domain in ('vision', 'language'):
            url = reverse(f'{domain}-compare-representations-data')
            assert url == f'/{domain}/compare/representations/data/'
