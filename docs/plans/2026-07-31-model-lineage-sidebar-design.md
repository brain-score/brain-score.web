# Model Lineage Sidebar Design

## Goal

Add a model-card sidebar section that explains explicit base-model ancestry and
shows related variants. Relationships must come from validated model metadata,
not identifier similarity or other name-based inference.

## Metadata contract

Each model may declare one direct base model with a normalized identifier,
display name, and relationship type. Supported relationship types are
`variant_of`, `fine_tuned_from`, and `derived_from`.

The direct-parent representation allows longer chains to be assembled from
other metadata documents. For example, `AlexNet_SIN_fov12` points to
`AlexNet_SIN`, and `AlexNet_SIN` points to `alexnet`. Architecture families
without a validated registry model use a stable external identifier and remain
unlinked in the UI.

## CSV projection and repository

The metadata build produces `model_relationships.csv` with the model key,
direct base identifier, base name, and relationship type. The repository joins
these rows to the model catalog to build:

- an ordered ancestor chain;
- whether each ancestor has validated metadata;
- sibling variants sharing the same direct base and direct child variants;
- the number of siblings omitted from the visible list.

Only models with validated metadata participate. The repository does not infer
relationships from similar model names. It stops ancestry traversal when a
base is external, missing, or would create a cycle.

## Presentation

The sidebar uses the existing `model-sidebar-card` container and title style.
It renders the ancestor chain first, highlights the current model, and then
shows up to three related sibling or child variants with concise relationship
labels. Additional variants are summarized as
`+N more metadata-covered variants`.

The entire card is omitted when no ancestor or sibling relationship is
available. Models without lineage metadata retain the current page layout with
no empty placeholder.

## Testing

Tests cover:

- AlexNet training-seed siblings;
- the `alexnet -> AlexNet_SIN -> AlexNet_SIN_fov12` chain;
- ConvNeXt-Tiny variants with an external base label;
- missing and cyclic relationships;
- sibling ordering and truncation;
- complete omission of the sidebar card when no relationship exists.

No database schema or database contents are changed.
