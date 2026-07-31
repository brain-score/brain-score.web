import csv
from collections import Counter, defaultdict
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
        models[_model_key(row)]["datasets"].append(row)

    for row in _read_csv("intended_use.csv"):
        models[_model_key(row)]["intended_use"][row["category"]].append(row["value"])

    for row in _read_csv("contributors.csv"):
        models[_model_key(row)]["contributors"][row["kind"]].append(row["name"])

    assertions = defaultdict(Counter)
    for row in _read_csv("assertions.csv"):
        assertions[_model_key(row)][row["status"]] += 1

    for key, model in models.items():
        counts = assertions[key]
        model["verification"] = {
            "verified": counts["verified"],
            "inferred": counts["inferred"],
            "undocumented": counts["undocumented"],
            "total": sum(counts.values()),
        }
        model["intended_use"] = dict(model["intended_use"])
        model["contributors"] = dict(model["contributors"])

    return models


def get_model_metadata(domain, identifier):
    return _load_catalog().get((domain, identifier))
