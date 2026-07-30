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
- [x] 4. table_library_dependencies: deleted the dead override blocks (AG-Grid CSS was
      never shipping; grid uses v33 JS theming). Rendered output unchanged.
- [~] 5. Heavy-lib gating: NOT DONE. Plotly/d3/Chart.js/select2/jstat/countdown are all
      used by some page, so gating means inverting base.html to opt-in and touching every
      page that needs them + smoking each page type. Broad, site-wide, not leaderboard-only;
      too risky to rush. Recommend a dedicated pass.
- [x] 6a. Security: escaped < > & in the inline DJANGO_DATA blobs (script-context injection
      via user-influenced model/submitter names). Done + verified.
- [~] 6b. json_script parse-perf: NOT DONE. Would move the 12MB inline JS-object-literal to
      <script type=application/json> + JSON.parse (faster parse). Requires the view to pass
      raw objects (not pre-dumped strings) and rework the DJANGO_DATA/domain-preservation flow.
      Moderate change; deferred to avoid a fragile end-of-session rewrite.
- [~] 7. Un-skip / de-flake 10 test_ag_grid.py assertions: NOT DONE. They hardcode
      data-dependent ranks and run against a live server; de-flaking = making them
      data-independent (separate test-refactor, no product-perf gain).

## Done this branch (all browser-verified against dev DB)
1 payload trim (-36%), 3 filter recursion/double-render, 4 dead CSS blocks, 6a script escaping.
Deferred: 2 bundling (systemic stub recursion), 5 heavy-lib gating (site-wide), 6b json_script, 7 E2E.

## Verification harness
- Dev server: `DEBUG=True python manage.py runserver 127.0.0.1:8020 --noreload` (RDS dev DB).
- Playwright smoke: rows render, search filters, sort via grid API, no NEW console errors
  vs the known pre-existing `null textContent` pageerror.
- Baseline before each risky change; compare after.
