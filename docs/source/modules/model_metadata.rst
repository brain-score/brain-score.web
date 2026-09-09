.. _model-metadata-pipeline:

Model metadata pipeline
=======================

Model cards are produced by a deterministic workbook-to-YAML-to-CSV pipeline.
The repository contains the conversion scripts, version 2 JSON schema, a
synthetic workbook fixture with golden output, all 43 source YAML records, and
the derived catalog used by Django.

The complete contributor runbook is maintained in
``benchmarks/model_metadata/README.md``. It covers:

* running the synthetic workbook example from a fresh checkout;
* converting the production curator workbook;
* workbook field and provenance-color conventions;
* validating version 2 ``metadata.yml`` files;
* rebuilding the six catalog CSVs; and
* tracing the catalog through the repository, view, templates, and JavaScript.

The focused reproducibility tests are run with:

.. code-block:: console

   python -m unittest \
       benchmarks.tests.test_model_metadata_generator \
       benchmarks.tests.test_model_metadata_repository \
       benchmarks.tests.test_model_metadata_template

The workbook generator does not call an LLM. All normalization and validation
rules are explicit in ``scripts/generate_model_metadata.py``.
