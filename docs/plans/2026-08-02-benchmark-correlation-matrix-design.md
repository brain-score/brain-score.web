# Benchmark Correlation Matrix Design

## Goal

Add an interactive benchmark tree and correlation matrix below Compare
Benchmarks. The matrix uses the same wayback date and eligible-model cohort as
the existing benchmark scatterplot.

## Tree states

Every benchmark has one explicit state:

- **Select** includes the benchmark in aggregation and displays it as a matrix
  row and column.
- **Hide** includes the benchmark in parent aggregation without displaying it.
- **Deselect** excludes the benchmark and its descendants from aggregation and
  display.

Deselecting a parent cascades through its subtree. Selecting or hiding a child
under a deselected parent restores its ancestors as hidden. Restoring a parent
whose entire subtree was deselected restores its descendants as hidden, which
makes the parent score computable without expanding the matrix.

The default selects Neural, V1, V2, V4, IT, and Behavioral; hides their other
ancestors and descendants; and deselects Engineering. This produces a compact
6 by 6 summary.
The matrix header also provides Select all, which selects every active
non-engineering parent and leaf. Reset tree restores the compact default.

The matrix is a responsive Plotly heatmap so large selections fit the available
panel and remain inspectable through hover, pan, and zoom. An Expand control
opens an in-page full-screen workspace and Escape closes it. Plotly's camera
control exports a high-resolution PNG with the Brain-Score logo embedded in the
plot.
The logo sits below the color bar so its placement is consistent on screen and
in exports. PNG export preserves the current chart dimensions, while compact
buttons below the figure provide SVG and long-form CSV downloads. The CSV
contains row and column benchmark labels, Pearson r, and paired-model counts.
The diverging color scale is normalized to the minimum and maximum finite
correlations in the current matrix.
Axis ticks are recalculated after every Plotly zoom or pan. The full matrix uses
a readable label subset, while smaller visible ranges progressively reveal more
labels and show every benchmark when the range fits within the tick limit.

## Aggregation and correlation

Parent values are recomputed recursively for each eligible model using active
selected or hidden children. Deselecting a child prunes it from the calculation.
Parent aggregation follows the comparison dashboard exactly: every active,
included immediate child remains in the denominator, missing child values
contribute zero when at least one child has a finite value, and a parent with no
finite children remains incomplete. This preserves the benchmark hierarchy and
keeps matching matrix cells consistent with the two-axis scatterplot.

Each matrix cell is a pairwise-complete Pearson correlation. It uses only
models with complete, finite values for both axes and requires at least eight
paired models. Zero is a valid finite score, matching the scatterplot.
Unavailable cells show the paired count rather than presenting an unstable
coefficient. Cells and tooltips report paired n, while the matrix summary
reports the full eligible cohort size.

## Interaction and verification

Tree state is local to the matrix and does not change the two-axis scatterplot
or the completedness denominator. Wayback and completedness changes update the
matrix because it subscribes to the shared comparison dashboard.

Pure JavaScript tests cover default states, subtree cascading, ancestor
restoration, hidden-child aggregation, deselected-child pruning, finite
pairwise correlation, overlap guards, downloads, dynamic ticks, and custom
neural-region configurations.
