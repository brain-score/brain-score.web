"""Concise license labels from the catalog's explicit declarations.

Identifiers follow https://spdx.org/licenses/. These are display mappings, not
independent verification of the underlying licenses. Keep the original text in
storage and in the details card. Historical, dataset, and upstream references
must not be mistaken for the submitted checkpoint's license.
"""
import re

LICENSE_TYPES = {
    'MIT': 'MIT License',
    'Apache-2.0': 'Apache License 2.0',
    'BSD-2-Clause': 'BSD 2-Clause License',
    'BSD-3-Clause': 'BSD 3-Clause License',
    'GPL-3.0-only': 'GNU General Public License v3.0 only',
    'GPL-3.0-or-later': 'GNU General Public License v3.0 or later',
    'CC-BY-4.0': 'Creative Commons Attribution 4.0',
    'CC-BY-NC-4.0': 'Creative Commons Attribution Non Commercial 4.0',
    'CC-BY-NC-SA-4.0': 'Creative Commons Attribution Non Commercial Share Alike 4.0',
}
ALIASES = (
    ('GPL-3.0-or-later', r'(?:GNU\s+)?GPL\s*v?3(?:\.0)?\+'),
    ('CC-BY-NC-SA-4.0', r'Creative Commons Attribution-NonCommercial-ShareAlike 4\.0 International'),
    ('Apache-2.0', r'Apache\s+2\.0'),
    ('CC-BY-NC-SA-4.0', r'CC[- ]BY[- ]NC[- ]SA\s+4\.0'),
    ('CC-BY-NC-4.0', r'CC[- ]BY[- ]NC\s+4\.0'),
    ('CC-BY-4.0', r'CC[- ]BY\s+4\.0'),
)
UNCERTAIN = re.compile(r'\b(?:assumed|unconfirmed|uncertain|unverified)\b', re.I)


def _declaration(text, scope):
    text = text.strip()
    patterns = [(identifier, re.escape(identifier)) for identifier in LICENSE_TYPES] + list(ALIASES)
    for identifier, pattern in patterns:
        if re.match(r'(?:' + pattern + r')(?=$|[\s(;,/])', text, re.I):
            return {'identifier': identifier, 'label': identifier, 'scope': scope,
                    'uncertain': bool(UNCERTAIN.search(text))}
    return None


def license_labels(value):
    """Select declared licenses; never strip all names out of explanatory prose."""
    if not value or not value.strip():
        return []
    clauses = value.split(';')
    first = clauses[0].strip()
    if first.lower().startswith('submission code:'):
        code = _declaration(first.split(':', 1)[1], 'Code license')
        labels = [code] if code else []
        for clause in clauses[1:]:
            # Only a direct weights declaration establishes a weights license.
            match = re.match(r'\s*(?:timm|torchvision|HF)?\s*weights:\s*(.+)', clause, re.I)
            if match:
                weights = _declaration(match.group(1), 'Weights license')
                if weights:
                    if code and weights['identifier'] == code['identifier']:
                        code['scope'] = 'Code + weights license'
                        code['uncertain'] = code['uncertain'] or weights['uncertain']
                    else:
                        labels.append(weights)
        if labels:
            return labels
    else:
        # A leading declaration applies to this distribution. Subsequent mentions
        # may describe historical code, upstream projects, or training datasets.
        scope = 'Code license' if first.lower() == 'mit license (brain-score repo)' else 'License'
        declared = _declaration(first, scope)
        if declared:
            return [declared]
    return [{'identifier': None, 'label': 'Unconfirmed', 'scope': 'License', 'uncertain': False}]
