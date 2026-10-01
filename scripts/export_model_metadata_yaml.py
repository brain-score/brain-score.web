"""Prepare reviewed CSV metadata as v2 plugin files without changing repositories.

The output directory mirrors plugin paths. Review and submit those files through
normal repository PRs; this command does not publish metadata or create PRs.
"""

import argparse
import ast
import json
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.metadata_test_settings")
import django

django.setup()
from benchmarks.model_metadata.catalog import read_catalog
from brainscore_core.metadata.contract import read_yaml, dump, validate
from brainscore_core.metadata.storage import from_tables, from_legacy


def registered_destinations(root):
    """Read literal registry assignments without importing or executing plugins."""
    locations = {}
    for path in sorted(root.glob('*/__init__.py')):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not (isinstance(target, ast.Subscript) and
                        isinstance(target.value, ast.Name) and target.value.id == 'model_registry'):
                    continue
                key = target.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    locations.setdefault(key.value.lower(), set()).add((key.value, path.parent))
    return locations


def export(catalog, domain, checkout, output, include_registered=False):
    document = from_tables(read_catalog(catalog), domain)
    root = checkout / f"brainscore_{domain}" / "models"
    destinations = {}
    for path in sorted(root.glob("*/metadata.y*ml")):
        data = read_yaml(path.read_text())
        for identifier in data.get("models", {}):
            key = identifier.lower()
            if key in destinations:
                raise ValueError(f"Ambiguous metadata location: {identifier}")
            destinations[key] = (path, data)
    registrations = registered_destinations(root) if include_registered else {}
    files = {}
    unmatched = []
    for identifier, entry in document["models"].items():
        destination = destinations.get(identifier.lower())
        if not destination and identifier.lower() in registrations:
            matches = registrations[identifier.lower()]
            if len(matches) != 1:
                raise ValueError(f"Ambiguous registered model: {identifier}")
            registered, folder = next(iter(matches))
            existing = list(folder.glob('metadata.y*ml'))
            if len(existing) > 1:
                raise ValueError(f"Ambiguous metadata files in {folder}")
            path = existing[0] if existing else folder / 'metadata.yaml'
            legacy = read_yaml(path.read_text()) if existing else {"models": {}}
            if legacy.get('schema_version') == '2.0':
                raise ValueError(f"{path} already uses v2; reconcile it instead of overwriting")
            # An absent legacy entry has nothing to preserve from this file.
            legacy['models'].setdefault(registered, {})
            destination = (path, legacy)
        if not destination:
            unmatched.append(identifier)
            continue
        path, legacy = destination
        key = next(key for key in legacy["models"] if key.lower() == identifier.lower())
        relative = path.relative_to(checkout)
        if legacy.get("schema_version") == "2.0":
            raise ValueError(
                f"{relative} already uses v2; reconcile it instead of overwriting"
            )
        if relative not in files:
            # Preserve every sibling model even when the CSV catalog only covers one.
            files[relative] = {
                "schema_version": "2.0",
                "domain": domain,
                "models": {
                    key: from_legacy(value, domain)
                    for key, value in legacy["models"].items()
                },
            }
        entry["legacy"] = legacy["models"][key]
        files[relative]["models"][key] = entry
    output.mkdir(parents=True, exist_ok=True)
    for relative, value in files.items():
        validate(value, domain)
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump(value))
    report = {"files": len(files), "unmatched": unmatched}
    (output / "conversion-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--catalog",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks/model_metadata/data",
    )
    p.add_argument("--domain", required=True)
    p.add_argument("--checkout", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument('--include-registered', action='store_true',
                   help='Also resolve exact literal model_registry assignments without importing plugins')
    args = p.parse_args()
    print(
        json.dumps(
            export(args.catalog, args.domain, args.checkout, args.output,
                   include_registered=args.include_registered), indent=2
        )
    )
