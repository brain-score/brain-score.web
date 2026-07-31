# Model Card UI Consistency

## Goal

Extend the curated metadata card's visual language across the model page without changing score calculations, navigation, chart behavior, or data loading.

## Approach

Use page-scoped classes rather than changing generic Bulma components. The metadata card remains the visual reference for outer containers: white surfaces, subtle blue-gray borders, a green top accent, restrained shadows, and consistent section titles.

The banner and its existing controls remain unchanged. Sidebar cards receive the shared container and title treatment while retaining their original tables, values, icons, and empty states.

The benchmark section, How to use, BERG, Historical Trend, and Benchmarks BibTeX receive the same outer card shell and title hierarchy. All content within those containers retains the original Brain-Score presentation, including score rows, rank badges, code blocks, links, tabs, and collapsible content.

## Responsive Behavior

Keep the existing sidebar breakpoint and benchmark hierarchy. On narrower layouts, actions and usage columns wrap naturally, while card padding is reduced. No new JavaScript or interaction pattern is introduced.

## Verification

Compile the Sass entrypoint, run the focused metadata/template tests, add template assertions for the new page-scoped hooks, and check the final diff for whitespace errors. Visual verification uses the same model and viewport as the supplied screenshots.
