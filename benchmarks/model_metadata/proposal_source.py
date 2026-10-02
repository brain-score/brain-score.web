"""Resolve first-time proposals without executing repository plugin code."""

import ast
from .github import ProposalError, allowed_path


def optional_file(github, repository, path, ref):
    try:
        return github.file(repository, path, ref)
    except ProposalError as exc:
        if exc.status_code != 404:
            raise
        return "", None


def proposal_document(github, config, domain, path, identifier):
    """Read a registered destination and preserve every existing sibling."""
    from brainscore_core.metadata import load, validate
    from brainscore_core.metadata.contract import read_yaml
    from brainscore_core.metadata.storage import from_legacy

    if not allowed_path(config, path):
        raise ProposalError("Select a model folder in the configured repository.")
    folder = path.rsplit("/", 1)[0]
    code, _ = github.file(config["repository"], folder + "/__init__.py", config["branch"])
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
