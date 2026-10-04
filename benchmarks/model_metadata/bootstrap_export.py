"""Prepare repository proposals from unpublished database metadata as data."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from django.db.models.functions import Lower
from brainscore_core.metadata.contract import FIELD_SPECS, LIST_PATHS, dump, get_path, read_yaml, validate
from brainscore_core.metadata.policy import evidence
from brainscore_core.metadata.storage import from_legacy

from benchmarks.models import Model, ModelMetadataPublication, ModelMetadataRecord
from .bootstrap import proposal_baseline, read_bootstrap_entries, require_complete_bootstrap
from .github import ProposalError
from .proposal_source import registered_identifiers


def export_bootstrap(domain, checkout, output):
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    root = checkout / ('brainscore_' + domain) / 'models'
    if not root.is_dir() or output == checkout or checkout in output.parents:
        raise ProposalError('Use a domain checkout and a separate proposal output directory.')
    if output.exists() and any(output.iterdir()):
        raise ProposalError('Use an empty proposal output directory.')
    published = set(ModelMetadataPublication.objects.filter(domain__iexact=domain)
                    .annotate(name=Lower('identifier')).values_list('name', flat=True))
    names = list(ModelMetadataRecord.objects.filter(domain__iexact=domain)
                 .annotate(name=Lower('identifier')).exclude(name__in=published)
                 .order_by('identifier').values_list('identifier', flat=True))
    entries = read_bootstrap_entries(domain, names)
    registered = set(Model.objects.filter(domain__iexact=domain)
                     .annotate(metadata_name=Lower('name')).values_list('metadata_name', flat=True))
    locations, registrations, headers, invalid = defaultdict(list), defaultdict(list), {}, {}
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        code = folder / '__init__.py'
        if code.exists():
            try:
                for identifier in registered_identifiers(code.read_text()):
                    registrations[identifier.lower()].append((identifier, folder))
            except (ProposalError, UnicodeError):
                pass
        paths = sorted(set(folder.glob('metadata.yaml')) | set(folder.glob('metadata.yml')))
        if len(paths) > 1:
            invalid[folder] = 'Duplicate metadata.yaml/metadata.yml files'
            continue
        for path in paths:
            try:
                content = path.read_text()
                header = read_yaml(content)
                if not isinstance(header, dict) or not isinstance(header.get('models'), dict):
                    raise ProposalError('Existing metadata is not a model mapping')
                headers[path] = (header, content)
                for identifier in header['models']:
                    locations[identifier.lower()].append((identifier, path))
            except (ValueError, UnicodeError):
                invalid[folder] = 'Existing metadata cannot be read safely'
    planned, blocked = defaultdict(list), []
    for identifier in names:
        key = identifier.lower()
        destination = locations[key]
        if len(destination) > 1:
            blocked.append({'identifier': identifier, 'reason': 'Ambiguous metadata files'})
            continue
        if destination:
            exact, path = destination[0]
            if registrations[key] and any(folder != path.parent for _, folder in registrations[key]):
                blocked.append({'identifier': identifier, 'reason': 'Metadata and registration folders disagree'})
                continue
        elif len(registrations[key]) == 1:
            exact, folder = registrations[key][0]
            if folder in invalid:
                blocked.append({'identifier': identifier, 'reason': invalid[folder]})
                continue
            path = next((p for p in headers if p.parent == folder), folder / 'metadata.yaml')
        else:
            blocked.append({'identifier': identifier, 'reason': 'No unique static registration or metadata identity'})
            continue
        planned[path].append((identifier, exact))
    proposals, covered = {}, []
    for path, matches in sorted(planned.items()):
        header, content = headers.get(path, ({'models': {}}, ''))
        try:
            if header.get('schema_version') == '2.0':
                raise ProposalError('Existing v2 metadata is authoritative; reconcile it separately')
            if set(header) != {'models'}:
                raise ProposalError('Legacy metadata has unsupported top-level fields')
            models = {identifier: from_legacy(value, domain) for identifier, value in header['models'].items()}
            for _, exact in matches:
                models.setdefault(exact, {})
            if any(identifier.lower() not in registered for identifier in models):
                raise ProposalError('A sibling identifier is not registered in the database')
            document = proposal_baseline(validate({'schema_version': '2.0', 'domain': domain,
                                                   'models': models}, domain), content)
            require_complete_bootstrap(document)
            for original, exact in matches:
                before, after = entries[original.lower()], document['models'][exact]
                for field in (*FIELD_SPECS, *LIST_PATHS):
                    value = get_path(before, field)
                    if value not in (None, '', []):
                        if value != get_path(after, field) or evidence(before, field) != evidence(after, field):
                            raise ProposalError('Existing value or evidence changed at ' + field)
            relative = path.relative_to(checkout)
            text = dump(document)
            proposals[relative] = text
            covered.extend(original for original, _ in matches)
        except (ValueError, KeyError, TypeError) as exc:
            blocked.extend({'identifier': original, 'reason': str(exc)} for original, _ in matches)
    output.mkdir(parents=True, exist_ok=True)
    for relative, text in proposals.items():
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text)
    report = {'domain': domain, 'input_models': len(names), 'covered_models': len(covered),
              'identifiers': sorted(covered), 'blocked': sorted(blocked, key=lambda item: item['identifier']),
              'files': {str(path): hashlib.sha256(text.encode()).hexdigest()
                        for path, text in proposals.items()},
              'research_performed': False, 'existing_values_and_evidence_preserved': True,
              'meaning': 'Database bootstrap migration proposals; merge and publication are still required'}
    (output / 'conversion-report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
