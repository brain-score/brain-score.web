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
- the number of siblings hidden from the initial view.

Only models with validated metadata participate. The repository does not infer
relationships from similar model names. It stops ancestry traversal when a
base is external, missing, or would create a cycle.

## Presentation

The sidebar uses the existing `model-sidebar-card` container and title style.
It renders the ancestor chain first, highlights the current model, and then
shows three related sibling or child variants initially with concise
relationship labels. Model names link to the matching public Brain-Score model
card. The page resolves these IDs from the existing model context at render
time, without adding IDs to metadata or changing the database.

When more variants exist, a `+N more metadata-covered variants` button reveals
up to three more per activation. The count updates until all variants are
visible, at which point the control becomes `Show fewer variants` and collapses
the list back to three.

The entire card is omitted when no ancestor or sibling relationship is
available. Models without lineage metadata retain the current page layout with
no empty placeholder.

## Testing

Tests cover:

- AlexNet training-seed siblings;
- the `alexnet -> AlexNet_SIN -> AlexNet_SIN_fov12` chain;
- ConvNeXt-Tiny variants with an external base label;
- missing and cyclic relationships;
- sibling ordering and progressive disclosure;
- model-card link attachment without mutating the cached catalog;
- complete omission of the sidebar card when no relationship exists.

No database schema or database contents are changed.
