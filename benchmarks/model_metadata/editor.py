"""Forms change repository documents only; no metadata database writes."""

from copy import deepcopy
import hashlib
from django import forms
from django.forms import formset_factory


SECTION_LABELS = {
    "model": "Model details",
    "training": "Training",
    "data": "Training data",
    "eval": "Evaluation data",
    "io": "Inputs and outputs",
    "provenance": "Weights and provenance",
    "legal": "License",
    "people": "Creators and organizations",
    "use": "Uses and limitations",
    "lineage": "Model lineage",
}


def field_label(path):
    return (
        path.strip("/")
        .split("/", 1)[-1]
        .replace("/", " ")
        .replace("_", " ")
        .capitalize()
    )


def editor_sections(form, groups):
    """Present editable fields first without changing validation or submitted names."""
    sections = {}
    locked_fields, locked_groups = [], []
    for name, field in form.fields.items():
        path = getattr(field, "metadata_path", None)
        if not path:
            continue
        if field.disabled:
            locked_fields.append(form[name])
            continue
        section = path.split("/")[1]
        sections.setdefault(section, {"fields": [], "groups": []})["fields"].append(
            form[name]
        )
    for group in groups:
        if not group["editable"]:
            locked_groups.append(group)
            continue
        section = group["path"].split("/")[1]
        sections.setdefault(section, {"fields": [], "groups": []})["groups"].append(
            group
        )
    result = []
    for key, label in SECTION_LABELS.items():
        if key not in sections:
            continue
        section = dict(sections[key], label=label)
        section["count"] = len(section["fields"]) + len(section["groups"])
        section["has_errors"] = (
            any(field.errors for field in section["fields"])
            or any(
                any(group["formset"].errors) or group["formset"].non_form_errors()
                for group in section["groups"]
            )
            if form.is_bound
            else False
        )
        result.append(section)
    return {
        "sections": result,
        "locked_fields": locked_fields,
        "locked_groups": locked_groups,
        "locked_count": len(locked_fields) + len(locked_groups),
    }


def describe_changes(before, after, paths):
    from brainscore_core.metadata.contract import get_path
    import yaml

    def display(value):
        if value is None or value == "" or value == []:
            return "Not documented"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (list, dict)):
            return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).strip()
        return str(value)

    return [
        {
            "label": field_label(path),
            "section": SECTION_LABELS[path.split("/")[1]],
            "before": display(get_path(before, path)),
            "after": display(get_path(after, path)),
        }
        for path in paths
    ]


def make_editor(entry, data=None):
    from brainscore_core.metadata.contract import FIELD_SPECS, LIST_PATHS, get_path, put_path
    from brainscore_core.metadata.policy import editability, evidence

    def normalized(value):
        if isinstance(value, str):
            return value.replace("\r\n", "\n").replace("\r", "\n")
        if isinstance(value, list):
            return [normalized(item) for item in value]
        if isinstance(value, dict):
            return {
                key: normalized(item)
                for key, item in value.items()
                if item not in (None, "")
            }
        return value

    class MetadataText(forms.CharField):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, strip=False, **kwargs)

        def to_python(self, value):
            return normalized(super().to_python(value))

    class ProposalForm(forms.Form):
        reason = forms.CharField(
            label="Why are you proposing this change?",
            max_length=2000,
            widget=forms.Textarea(attrs={"rows": 3}),
        )
        source_url = forms.URLField(
            label="Supporting source",
            max_length=2000,
            help_text="An HTTPS link supporting your changes.",
        )
        source_kind = forms.ChoiceField(
            label="Source type",
            choices=[
                ("other", "Other source"),
                ("paper", "Paper"),
                ("huggingface", "Hugging Face"),
            ],
        )

        def clean_source_url(self):
            value = self.cleaned_data["source_url"]
            if not value.startswith("https://"):
                raise forms.ValidationError("Use an HTTPS link.")
            return value

    form = ProposalForm(data)
    paths = {}
    for index, (path, (_, kind, maximum)) in enumerate(FIELD_SPECS.items()):
        key = f"field_{index}"
        editable, help_text = editability(entry, path)
        kwargs = {
            "label": path.strip("/").replace("/", " / ").replace("_", " ").capitalize(),
            "required": False,
            "disabled": not editable,
            "initial": get_path(entry, path),
            "help_text": help_text,
        }
        if kind == str:
            compact = (maximum is not None and maximum <= 1000) or path in {
                "/training/learning_rate",
                "/training/batch_size",
            }
            field = MetadataText(
                max_length=maximum or 10000,
                widget=forms.TextInput()
                if compact
                else forms.Textarea(attrs={"rows": 2}),
                **kwargs,
            )
        elif kind == bool:
            field = forms.NullBooleanField(**kwargs)
        elif kind == int:
            field = forms.IntegerField(
                min_value=0,
                max_value=2147483647
                if path.endswith(("/width", "/height", "/channels"))
                else 9223372036854775807,
                **kwargs,
            )
        else:
            field = forms.FloatField(min_value=0, **kwargs)
        field.metadata_sources = list(evidence(entry, path)[1].values())
        field.metadata_path = path
        field.metadata_label = field_label(path)
        form.fields[key] = field
        paths[key] = path
    sets = []
    for index, path in enumerate(LIST_PATHS):
        editable, help_text = editability(entry, path)
        initial = get_path(entry, path) or []
        if path.startswith(("/people/", "/use/")):
            key = f"list_{index}"
            form.fields[key] = MetadataText(
                label=path.strip("/")
                .replace("/", " / ")
                .replace("_", " ")
                .capitalize(),
                required=False,
                disabled=not editable,
                initial="\n".join(initial),
                max_length=10000,
                widget=forms.Textarea(attrs={"rows": 3}),
                help_text=help_text + " One entry per line.",
            )
            paths[key] = path
            form.fields[key].metadata_path = path
            form.fields[key].metadata_label = field_label(path)
            form.fields[key].metadata_lines = True
            continue
        fields = {
            "identifier": MetadataText(required=False, max_length=200),
            "name": MetadataText(
                max_length=200 if path.startswith("/lineage") else 10000
            ),
        }
        if path.startswith("/lineage"):
            fields["relationship"] = forms.ChoiceField(
                initial="variant_of",
                choices=[
                    ("variant_of", "Variant of"),
                    ("fine_tuned_from", "Fine-tuned from"),
                    ("derived_from", "Derived from"),
                ],
            )
        else:
            fields["description"] = MetadataText(
                required=False,
                max_length=10000,
                widget=forms.Textarea(attrs={"rows": 2}),
            )
            if path.startswith("/data"):
                fields["role"] = forms.ChoiceField(
                    initial="training",
                    choices=[
                        ("training", "Training"),
                        ("pretraining", "Pretraining"),
                        ("fine_tuning", "Fine-tuning"),
                    ],
                )
        Row = type("MetadataRow", (forms.Form,), fields)
        Factory = formset_factory(
            Row,
            extra=1 if editable else 0,
            can_delete=editable,
            max_num=500,
            validate_max=True,
            absolute_max=500,
        )
        formset = Factory(data, initial=initial, prefix=f"rows_{index}")
        if not editable:
            for row in formset:
                for field in row.fields.values():
                    field.disabled = True
        sets.append(
            {
                "path": path,
                "label": path.strip("/")
                .replace("/", " / ")
                .replace("_", " ")
                .capitalize(),
                "help": help_text,
                "editable": editable,
                "sources": list(evidence(entry, path)[1].values()),
                "formset": formset,
            }
        )

    def document_changes():
        if not form.is_valid() or not all(
            group["formset"].is_valid() for group in sets
        ):
            return None
        updated = deepcopy(entry)
        changed = []
        for key, path in paths.items():
            if form.fields[key].disabled:
                continue
            value = form.cleaned_data[key]
            if key.startswith("list_"):
                value = [line for line in value.splitlines() if line.strip()]
            elif value == "":
                value = None
            if normalized(get_path(entry, path)) != normalized(value) and not (
                get_path(entry, path) is None and value == []
            ):
                put_path(updated, path, value)
                changed.append(path)
        for group in sets:
            if not group["editable"]:
                continue
            values = []
            for row in group["formset"].cleaned_data:
                if not row or row.get("DELETE"):
                    continue
                values.append(
                    {
                        key: (value or None)
                        for key, value in row.items()
                        if key != "DELETE"
                    }
                )
            if normalized(get_path(entry, group["path"]) or []) != normalized(values):
                put_path(updated, group["path"], values)
                changed.append(group["path"])
        if not changed:
            form.add_error(None, "No metadata values have changed.")
            return None
        source = {
            "kind": form.cleaned_data["source_kind"],
            "url": form.cleaned_data["source_url"],
        }
        source_id = (
            "proposal_" + hashlib.sha256(source["url"].encode()).hexdigest()[:16]
        )
        # A URL reused with a different kind must not rewrite earlier evidence.
        source_id += "_" + source["kind"]
        while (
            source_id in updated.get("sources", {})
            and updated["sources"][source_id] != source
        ):
            source_id += "_new"
        updated.setdefault("sources", {})[source_id] = source
        assertions = updated.setdefault("assertions", [])
        for path in changed:
            assertions[:] = [a for a in assertions if a["path"] != path]
            assertions.append(
                {"path": path, "status": "probable", "sources": [source_id]}
            )
        return updated, changed

    return form, sets, document_changes
