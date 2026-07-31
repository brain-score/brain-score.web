# Leaderboard performance branch — plan

Branch: `kp/leaderboard-perf` (off `kp/leaderboard-js-collapse`). Local commits only.
Each item: implement -> verify in browser (Playwright + dev DB, DEBUG=True) -> commit.

Order = safest/highest-value first.

- [x] 1. Payload trim (was "metadata dedup"): dropped unused complete/layer_mapping and
      omit null wayback fields. 19.6MB -> 12.5MB (-36%). Data-identical, browser-verified.
- [x] 2. Bundle JS via django-compressor: DONE. Removed the ~18 ag-grid delegating stubs
      (the modular files already own those globals) to eliminate the concatenation recursion,
      then wrapped the 14 module scripts in {% compress js %} -> one ~123KB bundle. Verified in
      the offline bundle (DEBUG=False): grid renders, expand 7->11, filter/search work, no
      recursion; dev pass-through unaffected.
- [x] 3. Filter double-render + latent recursion: renamed coordinator updateFilteredScores
      to computeFilteredScores; applyCombinedFilters sets the grid once. Browser-verified.
- [x] 4. table_library_dependencies: deleted the dead override blocks (AG-Grid CSS was
      never shipping; grid uses v33 JS theming). Rendered output unchanged.
- [x] 5. Heavy-lib gating: DONE via opt-out. Wrapped Plotly/d3/d3-tip/Chart.js/jstat in a
      third_party_viz_libs block (default-loaded so other pages are unchanged); leaderboard
      shell overrides it empty. Leaderboard now skips ~480KB gz of unused JS (Plotly ~350KB gz
      the bulk). select2 + jquery.countdown kept ungated (shared scripts invoke them everywhere,
      else the leaderboard threw .select2/.countdown errors). Verified: leaderboard skips the
      libs + grid works + no new errors; model/compare/competition still load them.
- [x] 6a. Security: escaped < > & in the inline DJANGO_DATA blobs (script-context injection
      via user-influenced model/submitter names). Done + verified.
- [x] 6b. json_script parse-perf: DONE for row_data (the ~12MB, ~96% of payload). Shipped as
      a <script type=application/json> island + JSON.parse; progressive-loader skips data
      islands. Small blobs left inline (negligible remaining gain). Browser-verified.
- [x] 7. Un-skip / de-flake 10 test_ag_grid.py assertions: DONE. Replaced hardcoded top-5
      snapshots with behavioural invariants, read column values via the grid API (the DOM-order
      read was the real flakiness), and drive sort via applyColumnState. Full suite: 31 passed.

## Done this branch (all browser-verified against dev DB)
1 payload trim (-36%), 3 filter recursion/double-render, 4 dead CSS blocks, 6a script escaping.
Deferred: 2 bundling (systemic stub recursion), 5 heavy-lib gating (site-wide), 6b json_script, 7 E2E.

## Verification harness
- Dev server: `DEBUG=True python manage.py runserver 127.0.0.1:8020 --noreload` (RDS dev DB).
- Playwright smoke: rows render, search filters, sort via grid API, no NEW console errors
  vs the known pre-existing `null textContent` pageerror.
- Baseline before each risky change; compare after.
