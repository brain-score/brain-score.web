# Model metadata pipeline

The model metadata shown on a Brain-Score model page is built in two stages:

```text
Brainscore Model Metadata.xlsx
    -> brain-score/vision metadata generator
    -> brainscore_vision/models/**/metadata.yml
    -> brain-score.web catalog builder
    -> benchmarks/model_metadata/data/*.csv
    -> Django view and templates
```

The initial metadata in this catalog was batch-generated from the curation
workbook. It was not entered through the website or copied into the CSV files
by hand.

## File naming

The version 2 source file is named `metadata.yml`. Some model plugins also have
an older `metadata.yaml`; that is a different format. The catalog builder only
reads files named `metadata.yml` whose `schema_version` is `2.0.0`.

## 1. Convert the workbook to `metadata.yml`

The source workbook and generator belong to the
[`brain-score/vision`](https://github.com/brain-score/vision) repository. The
relevant files are:

- `scripts/generate_model_metadata.py`
- `docs/model_metadata/model-metadata-v2.schema.json`
- `tests/test_model_metadata_generator.py`

From a checkout of `brain-score/vision`, preview the files that will be
generated:

```shell
python scripts/generate_model_metadata.py \
    "/path/to/Brainscore Model Metadata.xlsx" \
    --repo-root . \
    --dry-run
```

Remove `--dry-run` to write the files:

```shell
python scripts/generate_model_metadata.py \
    "/path/to/Brainscore Model Metadata.xlsx" \
    --repo-root .
```

The generator reads the first worksheet directly from the `.xlsx` archive. In
the workbook used for the initial import:

- column A contains the 33 curated field names;
- model records begin in column E;
- `model_name` or `model_ID` makes a column eligible for import; and
- the optional row after the curated fields contains a primary reference URL.

Each eligible workbook column must match exactly one identifier registered in
a model plugin's `model_registry`. This ensures that the output is attached to
an implemented Brain-Score model rather than only to a display name.

If a model occurs in more than one workbook column, the rightmost column is
treated as the latest record. Blank or explicitly unknown cells are backfilled
from earlier columns for that model.

The generator normalizes workbook values into typed version 2 fields. Examples
include parameter counts as integers, resolutions as channel/height/width
records, dataset names and training roles, lineage relationships, Boolean
values, licenses, and semicolon-separated lists. Values such as `N/A`,
`unknown`, and `not documented` are omitted from the typed section rather than
being stored as literal values.

Workbook fill colors are preserved as field-level provenance:

| Workbook state | Provenance status |
| --- | --- |
| Green (`FF93C47D`) | `verified` |
| Yellow (`FFFFE599`) | `inferred` |
| Red (`FFFF0000`) | `undocumented` |
| Blank, unknown, or unclassified | `undocumented` |

Text containing `assumed`, `presumed`, `inferred`, or `unconfirmed` is also
classified as `inferred`. Every curated field receives an assertion whose
source is `curation_workbook`, including fields that are undocumented.

Before writing a file, the generator checks its own invariants and validates
the result against `model-metadata-v2.schema.json`. Output location depends on
the plugin:

- A plugin with one registered model gets
  `brainscore_vision/models/<plugin>/metadata.yml`.
- A plugin with multiple registered models gets
  `brainscore_vision/models/<plugin>/metadata/<identifier>/metadata.yml`.
  The identifier is URL-encoded when necessary.

The generated YAML is the reviewed source of truth. Correcting factual
metadata should start in the workbook and be followed by regeneration and
review of the YAML diff. The schema can verify structure and types, but it
cannot establish that a claim about a model is factually correct.

## 2. Build the web catalog

After the version 2 YAML files are present in `brain-score/vision`, run the
catalog builder from the root of `brain-score.web`:

```shell
python scripts/build_model_metadata_catalog.py \
    /path/to/vision/brainscore_vision/models \
    benchmarks/model_metadata/data
```

The builder recursively discovers `metadata.yml`, keeps schema version
`2.0.0`, sorts records by `(domain, identifier)`, and rewrites six deterministic
CSV tables:

| File | Content |
| --- | --- |
| `models.csv` | One row per model with scalar card fields |
| `model_datasets.csv` | Training datasets and their roles |
| `intended_use.csv` | Applications, users, limitations, and biases |
| `contributors.csv` | Creators and organizations |
| `model_relationships.csv` | Direct base-model relationships |
| `assertions.csv` | Per-field provenance status and source |

These CSV files are a web deployment artifact. Do not edit them directly;
regenerate them from the reviewed `metadata.yml` files instead.

## 3. Render metadata on the website

The website does not import this catalog into the application database. It is
rendered from the checked-in CSV files at request time:

1. `benchmarks/model_metadata/repository.py` loads and joins the six tables on
   `(domain, identifier)`. The result is cached once per web process, and the
   loader also formats values, counts provenance statuses, and constructs
   lineage data.
2. `benchmarks/views/model.py` requests metadata with the public model's exact
   domain and registry identifier. It looks up public model-card IDs for known
   ancestors and related variants so their lineage labels can become links.
3. `benchmarks/templates/benchmarks/model.html` renders summary tags and
   includes the metadata, provenance, and lineage partials. Models without a
   matching catalog record continue to render without those sections.
4. `static/benchmarks/js/model-lineage.js` progressively reveals additional
   related variants. Presentation styles live in
   `static/benchmarks/css/model.sass`.

Metadata is only attached to public model pages. A model's registry identifier
must exactly match the `identifier` in `models.csv`; a display name or alias is
not used as a fallback. When the model database has no visual-degrees value,
the view uses the catalog value if one is available.

## Updating the catalog

For a routine metadata update:

1. Update and review the curation workbook.
2. Run the vision generator with `--dry-run`, then without it.
3. Review the generated `metadata.yml` diff and run:

   ```shell
   python -m unittest tests.test_model_metadata_generator
   ```

4. Run the web catalog builder and review all changed CSV rows.
5. Run the focused web tests:

   ```shell
   python -m unittest \
       benchmarks.tests.test_model_metadata_repository \
       benchmarks.tests.test_model_metadata_template
   ```

Commit the source YAML in `brain-score/vision` and the derived CSV catalog in
`brain-score.web` in their respective changes.
