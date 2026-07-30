# Leaderboard performance branch — plan

Branch: `kp/leaderboard-perf` (off `kp/leaderboard-js-collapse`). Local commits only.
Each item: implement -> verify in browser (Playwright + dev DB, DEBUG=True) -> commit.

Order = safest/highest-value first.

- [x] 1. Payload trim (was "metadata dedup"): dropped unused complete/layer_mapping and
      omit null wayback fields. 19.6MB -> 12.5MB (-36%). Data-identical, browser-verified.
- [~] 2. Bundle JS via django-compressor: DEFERRED. Blocked by systemic name collisions
      between ag-grid-leaderboard.js delegating stubs and the modular globals. Concatenation
      makes load order deterministic (ag-grid last) so each stub wins and recurses when the
      modular fn self-calls (updateFilteredScores -> fixed in item 3; buildHierarchyFromTree
      and ~others remain). Requires collapsing the stub layer (large/risky) for marginal gain
      (128KB bundle vs 12.5MB payload). Not worth it now.
- [x] 3. Filter double-render + latent recursion: renamed coordinator updateFilteredScores
      to computeFilteredScores; applyCombinedFilters sets the grid once. Browser-verified.
- [ ] 4. table_library_dependencies: declare the block or delete the dead overrides
      (AG-Grid CSS currently ships zero links).
- [ ] 5. Heavy-lib gating: move Plotly/d3/Chart.js/select2/jstat/countdown out of
      base.html unconditional load into a per-page block; leaderboard opts out.
      (Broad blast radius -> smoke every page type.)
- [ ] 6. Payload delivery: json_script (or lean JSON endpoint) instead of inline
      {{ ...|safe }} blobs; decide after dedup shrinks the payload.
- [ ] 7. Un-skip / de-flake the 10 skipped test_ag_grid.py value assertions.

## Verification harness
- Dev server: `DEBUG=True python manage.py runserver 127.0.0.1:8020 --noreload` (RDS dev DB).
- Playwright smoke: rows render, search filters, sort via grid API, no NEW console errors
  vs the known pre-existing `null textContent` pageerror.
- Baseline before each risky change; compare after.
