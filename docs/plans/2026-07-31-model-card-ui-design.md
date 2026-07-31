# Model Card UI Consistency

## Goal

Extend the curated metadata card's visual language across the model page without changing score calculations, navigation, chart behavior, or data loading.

## Approach

Use page-scoped classes rather than changing generic Bulma components. The metadata card remains the visual reference: white surfaces, subtle blue-gray borders, a green top accent, restrained shadows, dark navy headings, compact labels, and consistent spacing.

The banner keeps its existing gradient. Its reference, source, and contributor actions receive a shared compact treatment, while metadata tags remain secondary. The sidebar cards use one header style, padding scale, border treatment, table treatment, and empty-state language.

The benchmark section becomes a card-level region. Existing score colors, hierarchy, collapse controls, and bar calculations remain unchanged; only spacing, row separation, rank badges, and typography are refined. How to use, BERG, Historical Trend, and Benchmarks BibTeX use the same card shell and heading hierarchy. Usage links become compact action rows, and code blocks use a consistent inset surface.

## Responsive Behavior

Keep the existing sidebar breakpoint and benchmark hierarchy. On narrower layouts, actions and usage columns wrap naturally, while card padding is reduced. No new JavaScript or interaction pattern is introduced.

## Verification

Compile the Sass entrypoint, run the focused metadata/template tests, add template assertions for the new page-scoped hooks, and check the final diff for whitespace errors. Visual verification uses the same model and viewport as the supplied screenshots.
