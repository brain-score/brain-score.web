# Leaderboard performance branch — plan

Branch: `kp/leaderboard-perf` (off `kp/leaderboard-js-collapse`). Local commits only.
Each item: implement -> verify in browser (Playwright + dev DB, DEBUG=True) -> commit.

Order = safest/highest-value first.

- [ ] 1. Metadata dedup + drop `historical_versions` from default cells
      Trace consumers (template-initialization.js, csv-export.js), pick one canonical
      per-model and per-benchmark map, drop the duplicates from the payload.
- [ ] 2. Bundle + minify the AJAX-loaded leaderboard JS via django-compressor
      Wrap the content template's script block in {% compress js %}.
- [ ] 3. Filter double-render: stop setting rowData twice + redundant redrawRows
      (updateFilteredScores vs applyCombinedFilters in filter-coordinator.js).
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
