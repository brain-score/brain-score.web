# Model metadata

Model pages read structured metadata from PostgreSQL. Models without a curated
record use their submission metadata. Database failures do not fall back to CSVs.

Contributions edit schema 2.0 YAML through PRs in the model's domain repository.
Only merged PRs can publish database changes. Publication validates schema,
registered identities, repository bindings and matching metadata blobs, without
requiring an approval or source-override label. Repository rules govern merges;
only verified metadata fields remain locked in the website editor. New revision
rows record GitHub's merger; historical approval audit fields remain intact.
Five-minute EB synchronization invokes the existing publication command in the
deployed container. It is disabled by default; explicit enablement, a UTC start
time, expected database, and working shared Redis are required. Failed PRs retain
their checkpoint for retry. See the infrastructure synchronization runbook.
Canonical production hosts enable editing by default using the Contributions
App secret and `https://www.brain-score.org/metadata/github/callback/`.
The callback uses the canonical `www` host: the bare-domain redirect drops query
parameters required by GitHub authorization.
`MODEL_METADATA_EDIT_ENABLED=0` disables editing. Dev, staging and test settings
require explicit enablement. Apply the existing metadata migrations through 0033
before deploying to production; register the production callback in the GitHub
App settings. Manual publication imports merged PRs; automatic publication
remains disabled until its deployment is configured.
The shared contract is `brainscore_core.metadata`; the website schema dialog
shows `static/benchmarks/schemas/metadata-v2.0.yaml`. Template download stays disabled.

Empty model cards hide the header metadata strip and empty metadata sections,
and retain Add metadata and Schema v2.0 actions. Contributions require the
environment's GitHub App settings and a signed-in Brain-Score account.

First-time contributions resolve the repository model folder automatically,
with manual selection in the modal when lookup is unavailable or ambiguous.
The server verifies its literal `model_registry` assignment without executing
plugin code. A missing metadata file opens a blank form; existing v2 files open
their current values. Legacy files convert to v2 while preserving every sibling
and the original legacy values. Verification status determines field locks;
source type alone does not prevent editing. Verified values and their evidence
stay protected, including inherited verification. Other metadata fields can be
changed with a supporting source.
Computed registrations and model additions to existing v2 files require maintainer
curation. Submission rechecks the current file before creating the branch and PR;
neither the editor nor PR preview publishes database changes.

## Code and documentation

- `repository.py` formats database records for model cards.
- `editor.py` and `github.py` prepare and submit contributor PRs.
- `proposal_source.py` validates first-time destinations and preserves existing files.
- `publishing.py` validates publication; `writer.py` persists related tables.
- `catalog.py` validates the temporary CSV import format.

Architecture, deployment settings, migration records, and recovery procedures
live in [infrastructure/web/metadata](https://github.com/brain-score/infrastructure/tree/main/web/metadata).
The merge-based policy requires a coordinated core-pin update and migration 0033
before using this publisher. See the infrastructure deployment transition guide;
an older pinned core validator still enforces the previous approval policy.

## Temporary bootstrap data

`data/*.csv` is the reviewed 78-model snapshot used by `import_model_metadata`,
CSV-to-database parity tests, migration-history CI, and
`scripts/export_model_metadata_yaml.py`. It is not read when serving pages.
The YAML conversion and staging/production bootstrap are unfinished; retain this
snapshot until complete parity is verified and these consumers are migrated.
See the infrastructure bootstrap guide for the retirement checklist.

## Tests

Install the approved core revision through `requirements-metadata.txt`.
Use disposable PostgreSQL configured with `METADATA_TEST_HOST`,
`METADATA_TEST_PORT`, `METADATA_TEST_USER`, `METADATA_TEST_PASSWORD`, and
`METADATA_TEST_DB`. These settings do not retrieve production credentials.

```sh
python manage.py test benchmarks.tests.test_metadata_github_settings benchmarks.tests.test_metadata_bootstrap benchmarks.tests.test_metadata_edit benchmarks.tests.test_model_metadata --settings=web.metadata_test_settings --noinput
python manage.py makemigrations --check --dry-run --settings=web.metadata_test_settings
```

The `Model metadata` GitHub Actions workflow also rehearses both existing
migration histories. Shared `web_tests` deliberately skips tests requiring empty
catalog tables; those run against disposable PostgreSQL instead. The shared test
runner never applies migrations automatically.
