"""Resolve first-time proposals without executing repository plugin code."""

import ast
import hashlib
import json
import re
import time
from urllib.parse import quote, urlencode
from django.core.cache import cache
from .github import ProposalError, allowed_path


def optional_file(github, repository, path, ref):
    try:
        return github.file(repository, path, ref)
    except ProposalError as exc:
        if exc.status_code != 404:
            raise
        return "", None


def registered_identifiers(code):
    """Read literal registrations without importing or executing a plugin."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, RecursionError):
        raise ProposalError("The model registration could not be read.") from None
    registrations = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for assignment in node.targets:
            if not (isinstance(assignment, ast.Subscript)
                    and isinstance(assignment.value, ast.Name)
                    and assignment.value.id == "model_registry"):
                continue
            key = assignment.slice
            # Python 3.8 retains Index around subscript literals.
            if isinstance(key, ast.Index):
                key = key.value
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                registrations.add(key.value)
    return registrations


def discover_model_folder(github, config, identifier):
    """Use search as a hint, then verify every candidate at the target branch."""
    repository, branch = config["repository"], config["branch"]
    root = config["model_root"].strip("/")
    cache_key = "metadata-model-folder:" + hashlib.sha256(
        json.dumps([repository, branch, root, identifier]).encode()
    ).hexdigest()
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    fallback = (None, "The model folder could not be located automatically. Choose it below.")
    try:
        query = f"repo:{repository} path:{root} filename:__init__.py {json.dumps(identifier)}"
        result = github.cached_request("/search/code?" + urlencode({"q": query, "per_page": 100}))
        items, total = result.get("items"), result.get("total_count")
        if (result.get("incomplete_results") is not False
                or type(total) is not int or not isinstance(items, list)
                or total != len(items) or total > 100):
            fallback = (None, "The folder search was incomplete. Choose the model folder below.")
        elif items:
            head = github.cached_request(
                f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}"
            ).get("object", {}).get("sha", "")
            if not re.fullmatch(r"[0-9a-f]{40}", head):
                raise ProposalError("GitHub returned an invalid branch revision.")
            matches = set()
            candidates = set()
            for item in items:
                path = item.get("path", "")
                prefix = root + "/"
                if not path.startswith(prefix):
                    continue
                parts = path[len(prefix):].split("/")
                if (len(parts) != 2 or parts[1] != "__init__.py"
                        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", parts[0])
                        or item.get("repository", {}).get("full_name", repository) != repository):
                    continue
                candidates.add((parts[0], path))
            deadline = time.monotonic() + 20
            for folder, path in sorted(candidates):
                if time.monotonic() >= deadline:
                    raise ProposalError("The folder search timed out.")
                code, blob = optional_file(github, repository, path, head)
                if blob is not None and identifier in registered_identifiers(code):
                    matches.add(folder)
                    if len(matches) > 1:
                        break
            if len(matches) == 1:
                fallback = (matches.pop(), "")
            elif matches:
                fallback = (None, "More than one folder registers this model. Choose the correct folder below.")
    except ProposalError:
        fallback = (None, "Automatic folder lookup is temporarily unavailable. Choose the model folder below.")
    # Cache only repository data, never credentials. The editor rechecks the
    # registration and metadata at the current branch before accepting edits.
    cache.set(cache_key, fallback, 300 if fallback[0] else 30)
    return fallback


def proposal_document(github, config, domain, path, identifier):
    """Read a registered destination and preserve every existing sibling."""
    from brainscore_core.metadata import load, validate
    from brainscore_core.metadata.contract import read_yaml
    from brainscore_core.metadata.storage import from_legacy

    if not allowed_path(config, path):
        raise ProposalError("Select a model folder in the configured repository.")
    folder = path.rsplit("/", 1)[0]
    code, _ = github.file(config["repository"], folder + "/__init__.py", config["branch"])
    registrations = registered_identifiers(code)
    if identifier not in registrations:
        raise ProposalError(
            "This folder does not explicitly register the selected model. "
            "Choose its model folder; computed registrations need maintainer curation."
        )
    content, blob = optional_file(github, config["repository"], path, config["branch"])
    alternate = folder + ("/metadata.yml" if path.endswith(".yaml") else "/metadata.yaml")
    _, alternate_blob = optional_file(github, config["repository"], alternate, config["branch"])
    if alternate_blob is not None:
        raise ProposalError("Use the existing metadata file; duplicate YAML files are not allowed.")
    if blob is None:
        document = {"schema_version": "2.0", "domain": domain, "models": {identifier: {}}}
    else:
        header = read_yaml(content)
        if not isinstance(header, dict):
            raise ProposalError("The existing metadata needs maintainer curation.")
        if header.get("schema_version") == "2.0":
            document = load(content, domain)
            if identifier not in document["models"]:
                raise ProposalError("Adding a model to a v2 file requires a registration migration.")
        else:
            models = header.get("models")
            if (set(header) != {"models"} or not isinstance(models, dict)
                    or not all(isinstance(value, dict) for value in models.values())):
                raise ProposalError("The existing metadata needs maintainer curation.")
            document = {"schema_version": "2.0", "domain": domain,
                        "models": {key: from_legacy(value, domain) for key, value in models.items()}}
            document["models"].setdefault(identifier, {})
    return validate(document, domain), content, blob
