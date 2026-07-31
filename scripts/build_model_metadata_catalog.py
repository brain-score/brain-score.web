#!/usr/bin/env python3
"""Build the model-card CSV catalog from metadata.yml files."""

import argparse
import csv
from pathlib import Path

import yaml


MODEL_FIELDS = (
    "domain",
    "identifier",
    "display_name",
    "version",
    "architecture_family",
    "architecture_description",
    "parameter_count",
    "parameter_count_exact",
    "trainable_layers",
    "recurrent",
    "input_modality",
    "input_channels",
    "input_height",
    "input_width",
    "visual_degrees",
    "visual_degrees_description",
    "supervision_type",
    "supervision_description",
    "interface_description",
    "preprocessing_description",
    "training_process",
    "dataset_summary",
    "weights_provider",
    "checkpoint_identifier",
    "source_url",
    "license",
    "curation_confidence",
)

TABLE_FIELDS = {
    "models.csv": MODEL_FIELDS,
    "model_datasets.csv": (
        "domain",
        "identifier",
        "ordinal",
        "dataset_identifier",
        "dataset_name",
        "role",
        "description",
    ),
    "intended_use.csv": ("domain", "identifier", "category", "ordinal", "value"),
    "contributors.csv": ("domain", "identifier", "kind", "ordinal", "name"),
    "assertions.csv": ("domain", "identifier", "path", "status", "source"),
}


def first(items):
    return items[0] if items else {}


def scalar(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def model_row(document):
    model = document["model"]
    architecture = document.get("architecture", {})
    interface = document.get("interface", {})
    training = document.get("training", {})
    input_spec = first(interface.get("inputs", []))
    shape = input_spec.get("shape", {})
    parameter_count = architecture.get("parameter_count", {})
    trainable_layers = architecture.get("trainable_layers", {})
    supervision = training.get("supervision", {})
    weights = next(
        (item for item in document.get("artifacts", []) if item.get("role") == "weights"),
        {},
    )
    source = next(
        (item for item in document.get("artifacts", []) if item.get("role") == "source_code"),
        {},
    )
    license_data = first(document.get("licenses", []))

    return {
        "domain": model["domain"],
        "identifier": model["identifier"],
        "display_name": model["display_name"],
        "version": model.get("version"),
        "architecture_family": architecture.get("family"),
        "architecture_description": architecture.get("description"),
        "parameter_count": parameter_count.get("value"),
        "parameter_count_exact": parameter_count.get("exact"),
        "trainable_layers": trainable_layers.get("description"),
        "recurrent": architecture.get("recurrent"),
        "input_modality": input_spec.get("modality"),
        "input_channels": shape.get("channels"),
        "input_height": shape.get("height"),
        "input_width": shape.get("width"),
        "visual_degrees": interface.get("visual_degrees"),
        "visual_degrees_description": interface.get("visual_degrees_description"),
        "supervision_type": supervision.get("type"),
        "supervision_description": supervision.get("description"),
        "interface_description": interface.get("description"),
        "preprocessing_description": document.get("preprocessing", {}).get("description"),
        "training_process": training.get("process"),
        "dataset_summary": training.get("dataset_summary"),
        "weights_provider": weights.get("provider"),
        "checkpoint_identifier": weights.get("identifier"),
        "source_url": source.get("url"),
        "license": license_data.get("spdx") or license_data.get("name"),
        "curation_confidence": document.get("provenance", {}).get(
            "curation_confidence"
        ),
    }


def child_rows(document):
    model = document["model"]
    key = {"domain": model["domain"], "identifier": model["identifier"]}
    rows = {name: [] for name in TABLE_FIELDS if name != "models.csv"}

    for ordinal, dataset in enumerate(document.get("training", {}).get("datasets", [])):
        rows["model_datasets.csv"].append(
            {
                **key,
                "ordinal": ordinal,
                "dataset_identifier": dataset.get("identifier"),
                "dataset_name": dataset.get("name"),
                "role": dataset.get("role"),
                "description": dataset.get("description"),
            }
        )

    for category, values in document.get("intended_use", {}).items():
        for ordinal, value in enumerate(values):
            rows["intended_use.csv"].append(
                {**key, "category": category, "ordinal": ordinal, "value": value}
            )

    for kind, names in document.get("authorship", {}).items():
        for ordinal, name in enumerate(names):
            rows["contributors.csv"].append(
                {**key, "kind": kind, "ordinal": ordinal, "name": name}
            )

    for assertion in document.get("provenance", {}).get("assertions", []):
        rows["assertions.csv"].append({**key, **assertion})

    return rows


def write_table(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {field: scalar(row.get(field)) for field in fields}
            for row in rows
        )


def build_catalog(metadata_root, output_dir):
    documents = []
    for path in sorted(metadata_root.rglob("metadata.yml")):
        with path.open(encoding="utf-8") as stream:
            document = yaml.safe_load(stream)
        if document.get("schema_version") == "2.0.0":
            documents.append(document)

    documents.sort(key=lambda item: (item["model"]["domain"], item["model"]["identifier"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = {name: [] for name in TABLE_FIELDS}
    for document in documents:
        tables["models.csv"].append(model_row(document))
        for name, rows in child_rows(document).items():
            tables[name].extend(rows)

    for name, fields in TABLE_FIELDS.items():
        write_table(output_dir / name, fields, tables[name])

    return len(documents)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    count = build_catalog(args.metadata_root, args.output_dir)
    print(f"Generated metadata for {count} models")


if __name__ == "__main__":
    main()
