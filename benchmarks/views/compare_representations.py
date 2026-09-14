"""Representational-similarity panel for the compare page.

Model activations are cached in S3 during scoring, which makes a comparison
cheap that used to require re-running both models: how similarly do two models
*represent* the same stimuli, independent of how they score.

This view never reads the activation cache. Cache entries reach 5 GB, the cache
is a 365-day rolling window, and its keys carry plugin SHAs -- so a plugin
revision would silently change them and the page would 404 on its own data.
Instead a precompute step writes small derived artifacts and this view serves
those. See ``tasks/activations-compare-spec.md``.

Artifacts are read from a bundled JSON fixture for now. Whether they should
live in S3 or a database table is deliberately still open; keeping the reader
behind :func:`_load_artifacts` means that choice can change without touching
the view, the route, or the template.
"""
import json
from pathlib import Path

from django.http import JsonResponse
from django.views.decorators.http import require_GET

# Bundled artifact fixture. Small by construction: the browser-facing artifacts
# are 2D coordinates and scalars, never the Gram matrices they derive from.
_FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'representation_artifacts.json'


def _load_artifacts() -> dict:
    """Derived representation artifacts, or an empty payload if unavailable.

    Returns empty rather than raising: the panel is additive, and a missing
    artifact file should degrade to "no data yet" rather than 500 the compare
    page that everything else on it still works.
    """
    try:
        with open(_FIXTURE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'generated': None, 'models': [], 'comparisons': [], 'embeddings': {}}


@require_GET
def data(request, domain: str):
    """JSON for the Compare Representations panel.

    Optional ``stimulus_set`` query parameter selects one entry's embeddings;
    without it only the comparison table is returned, which keeps the initial
    payload small since embeddings dominate it.
    """
    artifacts = _load_artifacts()
    selected = request.GET.get('stimulus_set')

    payload = {
        'generated': artifacts.get('generated'),
        'models': artifacts.get('models', []),
        'comparisons': artifacts.get('comparisons', []),
        'domain': domain,
    }
    if selected:
        payload['embeddings'] = artifacts.get('embeddings', {}).get(selected, {})
        payload['selected'] = selected
    return JsonResponse(payload, json_dumps_params={'separators': (',', ':')})
