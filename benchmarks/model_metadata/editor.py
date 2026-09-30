"""Forms change repository documents only; no metadata database writes."""

from copy import deepcopy
import hashlib
from django import forms
from django.forms import formset_factory


def make_editor(entry, data=None):
    from brainscore_metadata.contract import FIELD_SPECS, LIST_PATHS, get_path, put_path
    from brainscore_metadata.policy import editability, related, evidence

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
            field = forms.CharField(
                max_length=maximum or 10000,
                widget=forms.Textarea(attrs={"rows": 2}),
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
        form.fields[key] = field
        paths[key] = path
    sets = []
    for index, path in enumerate(LIST_PATHS):
        editable, help_text = editability(entry, path)
        initial = get_path(entry, path) or []
        if path.startswith(("/people/", "/use/")):
            key = f"list_{index}"
            form.fields[key] = forms.CharField(
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
            continue
        fields = {
            "identifier": forms.CharField(required=False, max_length=200),
            "name": forms.CharField(
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
            fields["description"] = forms.CharField(
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
            value = form.cleaned_data[key]
            if key.startswith("list_"):
                value = [line.strip() for line in value.splitlines() if line.strip()]
            elif value == "":
                value = None
            if get_path(entry, path) != value and not (
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
            if (get_path(entry, group["path"]) or []) != values:
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
        updated.setdefault("sources", {})[source_id] = source
        assertions = updated.setdefault("assertions", [])
        for assertion in assertions:
            if any(related(assertion["path"], path) for path in changed):
                assertion["status"] = "probable"
        for path in changed:
            assertions[:] = [a for a in assertions if a["path"] != path]
            assertions.append(
                {"path": path, "status": "probable", "sources": [source_id]}
            )
        return updated, changed

    return form, sets, document_changes
