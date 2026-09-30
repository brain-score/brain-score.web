# Metadata schema viewer

The Schema v2.0 button opens a native dialog with an annotated metadata.yaml
example. The template download control is hidden until the supporting YAML
infrastructure is ready. This replaces the database-table presentation:
contributors need to understand how to describe a model, not internal row IDs.

The downloadable static YAML file is also the dialog's source of truth. It
contains model, training, data, eval, io, provenance, legal, people, use, lineage,
and assertions sections, following the existing assertion-path vocabulary.
Comments describe types, required identifiers, enum values, and missing values.
The example is explicitly illustrative and the format proposed; YAML import is
not implemented by this change.

Mapping to storage: model.architecture and model.supervision map to their
family/type and description columns; model.input_resolution maps to input
channels/height/width. io.modality/interface map to input_modality and
interface_description. training objective/loss/process/preprocessing map to
training_objective/loss_function/training_process/preprocessing_description.
Data summary maps to dataset_summary. Provenance checkpoint maps to
checkpoint_identifier. Remaining scalar names match their metadata columns.
Dataset lists become dataset rows with training roles explicit and test/validation
roles implied by their list. People and use lists become categorized child rows.
Base-model name/identifier map to base_name/base_identifier. Assertions map to
path/status/source rows. List positions supply ordinal values; generated IDs and
foreign keys are not part of the contributor format.

Preserve native Close/Escape behavior, focus containment/restoration, and a
keyboard-scrollable YAML region on narrow screens. Verify YAML parsing and
that the dialog remains readable and no download control is exposed.
