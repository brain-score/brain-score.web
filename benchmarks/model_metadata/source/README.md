# Bundled model metadata source

This directory contains the 43 version 2 `metadata.yml` records used to build
the checked-in web catalog. The directory structure below this file preserves
the corresponding model-plugin layout from `brain-score/vision`.

The snapshot was copied from `brain-score/vision` commit `5349f13b` on branch
`kp/model-metadata-v2`. The only snapshot-wide change is `schema_url`, which
points at the schema published by web PR #539. The typed metadata and
field-level provenance assertions are otherwise unchanged.

From the root of `brain-score.web`, rebuild the derived catalog with:

```shell
python scripts/build_model_metadata_catalog.py
```

The command reads this directory by default and rewrites
`benchmarks/model_metadata/data`. A clean rebuild should leave that directory
unchanged.

For new production curation, update the workbook and generate source YAML in
`brain-score/vision` first. After review, synchronize the version 2 YAML files
into this snapshot and rebuild the web catalog. Do not edit the derived CSVs
directly.
