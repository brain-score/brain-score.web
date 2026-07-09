# Browser QA checklist — leaderboard JS collapse

Branch: `kp/leaderboard-js-collapse` (off `kp/leaderboard-audit-fixes`).
Commit: `refactor(leaderboard): remove shadowed duplicate grid init and renderers`.

## What changed and why it should be safe
The legacy `ag-grid-leaderboard.js` loads last, so its `initializeGrid`,
`setInitialColumnState` and cell renderers won by load order; the duplicate
copies in `grid-initialization.js` and `cell-renderers.js` never executed.
This commit deletes only those dead shadowed copies and keeps the live-only
pieces (`resizeGridToViewport` + `initTopScrollbar` in grid-initialization.js;
`PublicToggleCellRenderer` in cell-renderers.js). The code that actually runs
is unchanged, so this is expected to be a no-op at runtime.

## Automated verification already done (headless Chromium, dev DB)
- Grid renders (521 public vision models; 36 windowed rows), 7 initial headers.
- Model search filters (36 -> 18 for "resnet").
- Sort works via grid API (neural desc vs asc yield different top models).
- Globals resolve: `initializeGrid`, `resizeGridToViewport`,
  `LeaderboardRenderers.PublicToggleCellRenderer`, `_topScrollbarSyncWidths`.
- No new console errors vs baseline (one pre-existing `null textContent`
  pageerror exists on master too — see "Known pre-existing" below).
- Every measured value is identical to the pre-change baseline (confirmed by
  stashing the change and re-running the same checks).

## Manual checks to run before merge (things the headless harness can't click reliably)
Load `/vision/leaderboard/` and `/language/leaderboard/`:

1. [ ] Expand a top-level category header (Neural / Behavioral / Engineering) ->
       its child columns appear; collapse -> they hide again.
2. [ ] Expand down two levels (category -> region -> leaf benchmark).
3. [ ] Sort a leaf score column asc/desc/none (3-state) and the Rank column.
4. [ ] Score cells are colored (pill background), not all grey.
5. [ ] Model group-status dot renders (curated vs community) in the status column.
6. [ ] Horizontal top scrollbar appears when columns overflow and stays synced
       with the grid's own scroll; still synced after expanding columns.
7. [ ] Advanced Filters: toggle an architecture/dataset filter and a range slider;
       rows/columns update; Reset restores.
8. [ ] "+N NEW" badges show on updated benchmarks; `?new=<slug>` auto-expands them.
9. [ ] Sidebar toggle resizes the grid to fill the viewport.
10. [ ] Profile view (`/vision/leaderboard/content/?user_view=true`, logged in):
        the public/private toggle column renders and the toggle POSTs.
11. [ ] CSV export and citation/bibtex export still work.

## Known pre-existing (NOT introduced by this change)
- `Uncaught TypeError: Cannot read properties of null (reading 'textContent')`
  fires once on load on master too. Worth a separate look; unrelated to this commit.

## Findings surfaced during this work (for a follow-up, not done here)
- The two `initializeGrid` implementations had DIVERGED: the live legacy one has
  `expandNewBenchmarkColumns` (the `?new=` auto-expand) and inline search wiring;
  the shadowed modular one had the scrollbar/resize wiring instead. "Promoting the
  modular tree" would have silently dropped the `?new=` feature -- which is why the
  collapse kept the legacy implementation as the single owner.
- The top scrollbar initializes lazily: legacy `initializeGrid` does not call
  `initTopScrollbar`; it runs via `resizeGridToViewport`'s fallback path.
- `constants.js` values for renderers (`GROUP_STATUS`, `DEFAULT_CELL_BG`,
  `CELL_ALPHA`, `COLUMN_WIDTHS.GROUP_STATUS`) were only read by the now-removed
  shadowed renderers; the live renderers hardcode equivalents. constants.js is
  still used by range-filters / header-components / template-initialization.
- Full modularization (moving the renderers + `initializeGrid` OUT of
  ag-grid-leaderboard.js into the modular tree and deleting the legacy file) was
  NOT done -- it changes behavior and needs the manual QA above. This commit only
  removed the dead duplication.
