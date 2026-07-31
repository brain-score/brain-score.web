import csv
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


DATA_DIR = Path(__file__).parent / "data"

ARCHITECTURE_LABELS = {
    "convolutional_neural_network": "Convolutional neural network",
    "vision_transformer": "Vision transformer",
    "recurrent_convolutional_neural_network": "Recurrent convolutional network",
    "hybrid_convolutional_transformer": "Hybrid convolutional transformer",
    "hybrid_biological_convolutional": "Biological front-end + CNN",
    "raw_pixels": "Raw pixels",
    "other": "Other",
}

RELATIONSHIP_LABELS = {
    "variant_of": "Variant",
    "fine_tuned_from": "Fine-tuned",
    "derived_from": "Derived",
}

INITIAL_RELATED_MODELS = 3


def _read_csv(name):
    with (DATA_DIR / name).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _optional_int(value):
    return int(value) if value else None


def _optional_float(value):
    return float(value) if value else None


def _optional_bool(value):
    if not value:
        return None
    if value not in {"true", "false"}:
        raise ValueError(f"Invalid Boolean value: {value}")
    return value == "true"


def _format_count(value):
    if value is None:
        return None
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}".rstrip("0").rstrip(".") + "B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(value)


def _model_key(row):
    return row["domain"], row["identifier"]


def _attach_lineage(models, relationships):
    related_by_base = defaultdict(list)
    for model_key, relationship in relationships.items():
        base_identifier = relationship["base_identifier"]
        if base_identifier:
            related_by_base[(model_key[0], base_identifier)].append(model_key)

    for model_key, model in models.items():
        domain, identifier = model_key
        ancestors = []
        visited = {model_key}
        ancestor_key = model_key
        while ancestor_key in relationships:
            relationship = relationships[ancestor_key]
            base_identifier = relationship["base_identifier"]
            base_key = (domain, base_identifier) if base_identifier else None
            if base_key in visited:
                break

            base_model = models.get(base_key) if base_key else None
            ancestors.append(
                {
                    "identifier": base_identifier,
                    "display_name": relationship["base_name"],
                    "has_metadata": base_model is not None,
                }
            )
            if not base_model:
                break
            visited.add(base_key)
            ancestor_key = base_key
        ancestors.reverse()

        related_keys = set(related_by_base.get((domain, identifier), []))
        direct_relationship = relationships.get(model_key)
        if direct_relationship and direct_relationship["base_identifier"]:
            related_keys.update(
                related_by_base[
                    (domain, direct_relationship["base_identifier"])
                ]
            )
        related_keys.discard(model_key)

        related = []
        for related_key in sorted(
            related_keys,
            key=lambda key: (
                models[key]["display_name"].casefold(),
                models[key]["identifier"],
            ),
        ):
            related_model = models[related_key]
            relationship = relationships[related_key]
            related.append(
                {
                    "identifier": related_model["identifier"],
                    "display_name": related_model["display_name"],
                    "relationship": relationship["relationship"],
                    "relationship_display": RELATIONSHIP_LABELS.get(
                        relationship["relationship"], "Related"
                    ),
                }
            )

        model["lineage"] = {
            "ancestors": ancestors,
            "current": {
                "identifier": identifier,
                "display_name": model["display_name"],
            },
            "related_models": related,
            "hidden_related_count": max(0, len(related) - INITIAL_RELATED_MODELS),
            "has_relationships": bool(ancestors or related),
        }


def with_model_card_ids(metadata, model_ids_by_identifier):
    if metadata is None:
        return None

    metadata = deepcopy(metadata)
    for related in metadata["lineage"]["related_models"]:
        related["model_card_id"] = model_ids_by_identifier.get(
            related["identifier"]
        )
    return metadata


@lru_cache(maxsize=1)
def _load_catalog():
    models = {}
    for row in _read_csv("models.csv"):
        key = _model_key(row)
        if key in models:
            raise ValueError(f"Duplicate model metadata: {key}")

        parameter_count = _optional_int(row["parameter_count"])
        input_height = _optional_int(row["input_height"])
        input_width = _optional_int(row["input_width"])
        row.update(
            {
                "parameter_count": parameter_count,
                "parameter_count_exact": _optional_bool(row["parameter_count_exact"]),
                "parameter_count_display": _format_count(parameter_count),
                "recurrent": _optional_bool(row["recurrent"]),
                "input_channels": _optional_int(row["input_channels"]),
                "input_height": input_height,
                "input_width": input_width,
                "input_resolution_display": (
                    f"{input_width} × {input_height}" if input_width and input_height else None
                ),
                "visual_degrees": _optional_float(row["visual_degrees"]),
                "architecture_family_display": ARCHITECTURE_LABELS.get(
                    row["architecture_family"], row["architecture_family"]
                ),
                "datasets": [],
                "intended_use": defaultdict(list),
                "contributors": defaultdict(list),
            }
        )
        models[key] = row

    for row in _read_csv("model_datasets.csv"):
        row["role_display"] = row["role"].replace("_", " ").title()
        models[_model_key(row)]["datasets"].append(row)

    for row in _read_csv("intended_use.csv"):
        models[_model_key(row)]["intended_use"][row["category"]].append(row["value"])

    for row in _read_csv("contributors.csv"):
        models[_model_key(row)]["contributors"][row["kind"]].append(row["name"])

    relationships = {}
    for row in _read_csv("model_relationships.csv"):
        key = _model_key(row)
        if key in relationships:
            raise ValueError(f"Multiple direct base models: {key}")
        relationships[key] = row

    assertions = defaultdict(Counter)
    for row in _read_csv("assertions.csv"):
        assertions[_model_key(row)][row["status"]] += 1

    for key, model in models.items():
        if model["parameter_count_display"] and model["parameter_count_exact"] is False:
            model["parameter_count_display"] = f"≈{model['parameter_count_display']}"
        model["recurrent_display"] = (
            "Yes" if model["recurrent"] else "No" if model["recurrent"] is False else None
        )
        counts = assertions[key]
        model["verification"] = {
            "verified": counts["verified"],
            "inferred": counts["inferred"],
            "undocumented": counts["undocumented"],
            "total": sum(counts.values()),
        }
        model["intended_use"] = dict(model["intended_use"])
        model["contributors"] = dict(model["contributors"])
        model["has_card_content"] = any(
            (
                model["architecture_description"],
                model["parameter_count_display"],
                model["input_resolution_display"],
                model["recurrent_display"],
                model["supervision_description"],
                model["weights_provider"],
                model["training_process"],
                model["datasets"],
                model["preprocessing_description"],
                model["contributors"],
                model["license"],
                model["intended_use"],
            )
        )

    _attach_lineage(models, relationships)

    return models


def get_model_metadata(domain, identifier):
    return _load_catalog().get((domain, identifier))
