# Model metadata

Model pages read the six metadata tables in PostgreSQL. CSV files are reviewed
import inputs, not a runtime fallback. Models without a curated record use their
submission metadata, clearly labeled and marked probable. Database errors are
not hidden by silently switching to CSV files.

## Import and rollout

Use the target environment's normal database configuration. Confirm the connected
host and database name before making changes; the disposable local preview is
not the shared development database. Back up the target database and verify that
the backup can be restored. Inspect the pending migration plan before applying it:

```sh
python manage.py showmigrations benchmarks
python manage.py migrate --plan
```

If metadata tables already exist, check for duplicate lowercased `(domain,
identifier)` pairs before migration 0029. Resolve conflicting records explicitly;
do not discard or merge checkpoint variants automatically. The plan may include
0027's materialized-view refresh as well as the metadata migrations; schedule it
for an acceptable maintenance window on a populated database.

Apply migrations before starting application workers with the database reader:

```sh
python manage.py migrate
python manage.py import_model_metadata --dry-run --check-public
python manage.py import_model_metadata
```

The default input directory is resolved relative to this package. To import a
reviewed catalog from another directory, supply its path as the positional
argument. `--dry-run` validates all files, reports new/updated/preserved model
counts, and makes no changes. `--check-public` reports identifiers without a
public, scored model page; it does not guess aliases or reject legitimate
records whose public page is not available yet.

Ordinary imports update the supplied model keys and replace their child rows
within one transaction, preserving model-record IDs and all unrelated records.
`--wipe` explicitly replaces the entire metadata catalog. Empty input is rejected
with or without that option. Any validation or database error aborts the import;
transaction failures roll back all changes.

Validation covers headers, missing keys, types, finite/nonnegative numbers,
field lengths, allowed categories/statuses/roles, duplicate keys, and orphan child
rows. Identifiers are compared without casing differences; punctuation and
checkpoint suffixes remain significant. The database also enforces uniqueness
on lowercased domain and identifier. Resolve any preexisting ambiguous duplicates
before applying migration 0029; do not merge distinct checkpoints to satisfy it.

The new migration extends the schema after the existing 0028 merge. Do not rename
either 0027 migration. It also converts old `inferred` and `low` confidence values
to `probable` and `uncertain`.

Run the migration/import sequence on dev, then staging, before production.
After import, verify all six table counts and representative field values against
the reviewed catalog. Check curated, fallback, and private model pages, lineage
links, and real leaderboard scores/rankings. The synthetic local preview cannot
validate real scores or migration duration on a populated database. Check the
migration plan again and confirm no unapplied migrations remain.
Take a metadata backup first. Roll back application code to the previous release
if necessary; leave the additive schema in place. Restore data from the backup
if an approved catalog import itself must be undone. No worker restart is needed
to observe metadata updates; the database reader has no permanent process cache.

The baseline catalog contains 78 models, 225 datasets, 520 intended-use rows,
138 contributors, 71 relationships, and 2,418 assertions. Counts supplement,
but do not replace, value-by-value parity checks.

## Confidence and references

The shared vocabulary is `verified`, `probable`, `uncertain`, and `undocumented`.
Workbook colors map to these statuses. A populated cell without an explicit
confidence annotation is probable; it is not automatically verified. Regenerating
an old workbook without its color annotations may therefore lower confidence.
Review that change rather than automatically promoting assertions.

The current catalog's assertions cite `curation_workbook`. This identifies a
curation source, not a field-level primary reference. The source column accepts
long references/URLs, and the UI preserves field-level confidence explanations. Add primary
references as curation progresses. Missing tokenizer information remains
undocumented rather than being assumed not applicable.

Coverage audit on 2026-09-29: 77 of 78 identifiers matched the public vision
leaderboard's 533 rows. `Resnext101_32x8d` had no match. Retain it until its identity
or publication status is established; `resnext101_32x8d_wsl` already has a separate
catalog record and must not be silently merged with it. Re-run `--check-public`
against staging/production because public coverage changes.

## Isolated tests

`web.metadata_test_settings` does not retrieve production credentials. Configure
`METADATA_TEST_HOST`, `METADATA_TEST_PORT`, `METADATA_TEST_USER`,
`METADATA_TEST_PASSWORD`, and `METADATA_TEST_DB` for a disposable PostgreSQL
instance. The default Django test runner creates and migrates a separate test
DB. For example:

```sh
python manage.py test benchmarks.tests.test_model_metadata benchmarks.tests.test_compare_dashboard benchmarks.tests.test_migrations --settings=web.metadata_test_settings --noinput
python manage.py makemigrations --check --dry-run --settings=web.metadata_test_settings
```

The metadata database tests intentionally skip the legacy
`ExistingDatabaseTestRunner`, which uses a shared prepopulated database. The
`Model metadata` GitHub Actions job runs them against disposable PostgreSQL 14
with Python 3.11 and Django 4.1. The legacy Jenkins page tests still require the
new migrations and catalog import to be applied to their test database before
serving this version; their runner does not perform migrations.

To check a running local/staging server with real page IDs:

```sh
python scripts/check_model_metadata_ui.py http://127.0.0.1:8000 \
  --curated-id CURATED_ID --fallback-id FALLBACK_ID --empty-id EMPTY_ID \
  --output /tmp/metadata-ui-results
```

Install a Playwright Chromium browser first, or pass `--browser` with a Chrome
executable path. Choose a curated model with more than three related variants
and a resolvable comparison link. The script checks desktop/tablet/mobile
widths, expansion and recollapse, keyboard confidence controls, source labels,
comparison navigation, HTTP success, JavaScript errors on the curated card,
and page overflow. It also saves screenshots for visual review.

## UI scope

The model page starts with Scores and How to use, followed by At-a-glance and
intended-use details. The sidebar shows layer commitment, visual angle, lineage,
and metadata provenance in that order. Contributor, reference, GitHub, and
Compare controls share one wrapping row; a compact icon strip summarizes metadata.
Keyboard-accessible disclosures and responsive layouts preserve the detailed cards.

Header tags use concise architecture/supervision categories. Licenses use
controlled SPDX identifiers in `licenses.py`, normalizing aliases such as
Apache 2.0 and GNU GPL v3+. Explicit code and weights licenses remain separate
when they differ. Historical/upstream and dataset-license references are not
promoted to checkpoint licenses; unresolved references are Unconfirmed.
The original wording remains in the details card.

The Schema v2.0 dialog displays a proposed annotated YAML template. Its download
control is hidden until the supporting infrastructure is ready. It is not yet
an accepted upload format or an executable validation schema. Before enabling
YAML submission, define and version the validation contract, implement a tested
YAML-to-database mapping, and decide how edits, sources, and revision history are
recorded. These are follow-up work, not prerequisites for the reviewed CSV import.
