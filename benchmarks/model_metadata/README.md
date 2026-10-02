# Model metadata

Model pages read structured metadata from PostgreSQL. Models without a curated
record use their submission metadata. Database failures do not fall back to CSVs.

Contributions edit schema 2.0 YAML through PRs in the model's domain repository.
Only merged PRs can publish database changes. Publication validates schema,
registered identities, repository bindings and matching metadata blobs, without
requiring an approval or source-override label. Repository rules govern merges;
paper and Hugging Face fields remain locked in the website editor. New revision
rows record GitHub's merger; historical approval audit fields remain intact.
Editing and publication remain disabled until the deployment passes rehearsal.
The shared contract is `brainscore_core.metadata`; the website schema dialog
shows `static/benchmarks/schemas/metadata-v2.0.yaml`. Template download stays disabled.

## Code and documentation

- `repository.py` formats database records for model cards.
- `editor.py` and `github.py` prepare and submit contributor PRs.
- `publishing.py` validates publication; `writer.py` persists related tables.
- `catalog.py` validates the temporary CSV import format.

Architecture, deployment settings, migration records, and recovery procedures
live in [infrastructure/web/metadata](https://github.com/brain-score/infrastructure/tree/main/web/metadata).
That documentation is being reviewed in
[infrastructure PR #56](https://github.com/brain-score/infrastructure/pull/56).
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
python manage.py test benchmarks.tests.test_metadata_github_settings benchmarks.tests.test_metadata_edit benchmarks.tests.test_model_metadata --settings=web.metadata_test_settings --noinput
python manage.py makemigrations --check --dry-run --settings=web.metadata_test_settings
```

The `Model metadata` GitHub Actions workflow also rehearses both existing
migration histories. Shared `web_tests` deliberately skips tests requiring empty
catalog tables; those run against disposable PostgreSQL instead. The shared test
runner never applies migrations automatically.
