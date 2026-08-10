# Model metadata pipeline

This directory is a self-contained reference for converting curated workbook
records into version 2 model metadata and rendering them on Brain-Score model
pages. The production curator workbook is not committed, but a synthetic
workbook definition, workbook builder, golden YAML output, all 43 production
source records, and the derived web catalog are included.

No LLM is invoked by this pipeline. Both conversion stages are deterministic
Python programs.

```text
Brainscore Model Metadata.xlsx
    -> scripts/generate_model_metadata.py
    -> **/metadata.yml (schema version 2.0.0)
    -> scripts/build_model_metadata_catalog.py
    -> benchmarks/model_metadata/data/*.csv
    -> repository.py -> Django view -> templates and JavaScript
```

## Start from a fresh checkout

Install the repository dependencies first. `PyYAML` is pinned in both
`requirements.txt` and `environment.yml`; the workbook generator itself uses
only the Python standard library.

### Run the complete synthetic example

The example builder creates both a real `.xlsx` file and the minimal
vision-style model registry needed by the generator:

```shell
EXAMPLE_ROOT=/tmp/brain-score-model-metadata-example

python benchmarks/model_metadata/examples/create_example_workbook.py \
    "$EXAMPLE_ROOT/metadata.xlsx" \
    --repo-root "$EXAMPLE_ROOT/vision"

python scripts/generate_model_metadata.py \
    "$EXAMPLE_ROOT/metadata.xlsx" \
    --repo-root "$EXAMPLE_ROOT/vision"

diff \
    "$EXAMPLE_ROOT/vision/brainscore_vision/models/example_model/metadata.yml" \
    benchmarks/model_metadata/examples/synthetic/metadata.yml
```

An empty `diff` means the workbook-to-YAML pipeline reproduced the committed
golden file exactly. The example exercises typed values, lists, dataset
normalization, artifacts, provenance colors, schema validation, and output
placement.

The human-readable workbook inputs are in
`examples/synthetic_workbook.json`. `examples/create_example_workbook.py`
packages that definition as a standards-compatible `.xlsx` file.

### Rebuild the complete web catalog

All 43 production source YAML records are bundled under `source`. Rebuild the
six checked-in CSV files without any external repository:

```shell
python scripts/build_model_metadata_catalog.py
git diff --exit-code -- benchmarks/model_metadata/data
```

The catalog builder defaults to `benchmarks/model_metadata/source` and
`benchmarks/model_metadata/data`. Both paths can still be supplied explicitly
when building from a different metadata checkout.

### Run the focused tests

```shell
python -m unittest \
    benchmarks.tests.test_model_metadata_generator \
    benchmarks.tests.test_model_metadata_repository \
    benchmarks.tests.test_model_metadata_template
```

The tests run a real synthetic `.xlsx` through the generator CLI, compare the
result with the golden YAML, validate all 43 source records, reproduce every
catalog CSV byte for byte, and test repository and template rendering.

## Production workbook conversion

Production `metadata.yml` files belong beside their model implementations in
[`brain-score/vision`](https://github.com/brain-score/vision). From a
`brain-score.web` checkout, first preview the output:

```shell
python scripts/generate_model_metadata.py \
    "/path/to/Brainscore Model Metadata.xlsx" \
    --repo-root /path/to/vision \
    --dry-run
```

Remove `--dry-run` to write the validated files:

```shell
python scripts/generate_model_metadata.py \
    "/path/to/Brainscore Model Metadata.xlsx" \
    --repo-root /path/to/vision
```

The real curator workbook is maintained outside the source repositories.
Maintainers updating production facts need access to that workbook and a
checkout of `brain-score/vision`. The bundled synthetic workbook is the public
fixture for learning, development, and end-to-end testing.

## Workbook contract

The generator reads the first worksheet directly from the `.xlsx` archive:

- Column A contains exactly 33 curated field names.
- Model records begin in column E.
- `model_name` or `model_ID` makes a model column eligible.
- The optional row after the 33 fields contains a primary reference URL.
- Each eligible column must match exactly one `model_registry` identifier in
  the target vision checkout.

The complete ordered field list and representative values are visible in
`examples/synthetic_workbook.json`.

If a model occurs in multiple workbook columns, the rightmost column is the
latest record. Blank or explicitly unknown cells are backfilled from earlier
columns. Values including `N/A`, `unknown`, and `not documented` are omitted
from typed metadata instead of being stored literally.

The generator applies explicit parsing rules for architecture families,
parameter counts, resolutions, Booleans, datasets and training stages,
lineage, licenses, and semicolon-separated lists. A new value that cannot be
handled deterministically must be supported in the script or curated into a
recognized representation; there is no LLM fallback.

## Schema and provenance

Every generated record is validated against
`schema/model-metadata-v2.schema.json`. The generator uses that local file by
default; `--schema /path/to/schema.json` selects another compatible copy. The
schema's `$id` and every generated `schema_url` point to the live schema served
from GitHub's PR #539 ref.

Workbook fill colors become field-level provenance assertions:

| Workbook state | Assertion status |
| --- | --- |
| Green (`FF93C47D`) | `verified` |
| Yellow (`FFFFE599`) | `inferred` |
| Red (`FFFF0000`) | `undocumented` |
| Blank, unknown, or unclassified | `undocumented` |

Text containing `assumed`, `presumed`, `inferred`, or `unconfirmed` is also
classified as `inferred`. All 33 fields receive an assertion, including fields
without a typed value.

Before writing, the generator validates its invariants and the full JSON
schema. Output placement follows the target plugin registry:

- A plugin with one registered model gets
  `brainscore_vision/models/<plugin>/metadata.yml`.
- A plugin with multiple models gets
  `brainscore_vision/models/<plugin>/metadata/<identifier>/metadata.yml`.
  Identifiers are URL-encoded when necessary.

Schema validation proves structure and types, not factual correctness. All
curated claims still require human review against implementations and
authoritative sources.

## Bundled source snapshot

`source` contains the 43 version 2 records used by this branch. It preserves
the model-plugin layout from `brain-score/vision` commit `5349f13b` on branch
`kp/model-metadata-v2`. See `source/README.md` for synchronization rules.

The version 2 filename is `metadata.yml`. Legacy model-plugin files named
`metadata.yaml` use a different schema and are ignored by the catalog builder.

The catalog contains six deterministic tables:

| File | Content |
| --- | --- |
| `models.csv` | One row per model with scalar card fields |
| `model_datasets.csv` | Training datasets and roles |
| `intended_use.csv` | Applications, users, limitations, and biases |
| `contributors.csv` | Creators and organizations |
| `model_relationships.csv` | Direct base-model relationships |
| `assertions.csv` | Per-field provenance status and source |

The YAML snapshot is source; the CSV files are deployment artifacts. Do not
edit derived CSVs directly.

## Website rendering

The website does not import the catalog into the application database:

1. `repository.py` loads and joins the six CSVs on `(domain, identifier)`. The
   result is cached once per web process. It formats values, counts provenance
   statuses, and constructs model lineage.
2. `benchmarks/views/model.py` looks up metadata for a public model's exact
   domain and registry identifier. It resolves public model-card IDs for known
   ancestors and variants.
3. `benchmarks/templates/benchmarks/model.html` renders summary tags and
   includes the metadata, provenance, and lineage partials.
4. `static/benchmarks/js/model-lineage.js` reveals additional variants, with
   presentation styles in `static/benchmarks/css/model.sass`.

Models without a matching metadata record render normally without those
sections. Metadata is attached only to public model pages. If the model
database has no visual-degrees value, the view uses the catalog value.

## Production update checklist

1. Update and review the curator workbook.
2. Generate the vision YAML with `--dry-run`, then write it.
3. Review schema, provenance, and factual diffs in `brain-score/vision`.
4. Synchronize all version 2 YAML records into `source` and record the vision
   commit in `source/README.md`.
5. Run `python scripts/build_model_metadata_catalog.py`.
6. Review the derived CSV diff and run the focused tests above.
7. Commit source YAML changes in `brain-score/vision` and the synchronized
   source snapshot plus derived catalog in `brain-score.web`.
