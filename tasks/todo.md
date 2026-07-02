# Leaderboard audit — fix plan

Branch: `kp/leaderboard-audit-fixes` (off `master`). Local commits only, Conventional Commits, no push.

Legend: `[x]` done, `[~]` held for sign-off / needs runtime verification.

## Done (this branch)

### Logging hygiene
- [x] Remove per-request `DEBUG` `logger.warning` in `get_ag_grid_context` and `get_context`
- [x] Remove the debug-only `.count()` query over the model materialized view
- [x] Downgrade routine cache hit/miss/timing + Redis-availability logs from error/info to `debug`; de-emoji
- [x] Compute `estimate_size` once per cache miss (was pickling the full context twice)

### Delete dead code
- [x] `static/benchmarks/js/leaderboard-init.js` (0 refs)
- [x] `static/benchmarks/js/leaderboard/ui/ui-handlers.js` (0 refs)
- [x] `static/benchmarks/js/leaderboard/core/state-management.js` (0 refs)
- [x] Orphan template `benchmarks/templates/benchmarks/index.html`
- [x] Unrouted `index.view` + legacy templates `leaderboard.html`, `leaderboard-table.html`, `info-section.html`
- [x] Dead `index.py` helpers `build_model_benchmark_frames`, `_extract_score_value`, `_parse_end_timestamp`
- [x] Drop the unused `index` view import from `views/__init__.py` and `urls.py`

### Correctness
- [x] Cross-domain: parametrize `normalize_id` / average-benchmark filter by `domain` (fixes `/language/leaderboard/`)
- [x] Add `is_profile_view` to the user cache key (public key unchanged)

### Performance
- [x] `find_root_parent`: O(n^2) -> O(n) via an `{identifier: benchmark}` dict
- [x] Remove the dead whole-hierarchy rebuild in `updateColumnVisibility` (`header-components.js`)

Verified with `python manage.py check` (clean; only pre-existing warnings) + `py_compile` + `node --check`.

## Held for sign-off — architectural or not runtime-verifiable here

### JS grid (root-cause refactor)
- [~] Collapse legacy `ag-grid-leaderboard.js` into the modular `leaderboard/` tree. It still owns the live `initializeGrid` + cell renderers by load-order accident, shadowing the modular copies (dead `grid-initialization.js`, dead renderer half of `cell-renderers.js`, the no-fallback `getAllDescendantsFromHierarchy` stub, inert `constants.js`). High-value but high-risk; needs browser verification of sort/expand/collapse/filter.
- [~] Filter double-render: `updateFilteredScores` sets `rowData`, then `applyCombinedFilters` sets it again + `redrawRows()` (`filter-coordinator.js:322`). Real jank fix, needs browser verification.
- [~] JS domain hardcoding in the filter pipeline (`filter-coordinator.js`, `hierarchy-utils.js`) — couples to the collapse above; fix together.

### Payload / assets
- [~] Move the inline JSON matrix to a JSON endpoint / `json_script`; dedupe the 2x-4x metadata maps; drop `historical_versions` from default cells.
- [~] Stop computing/caching `comparison_data` + CSV on the leaderboard path (they are never rendered there; split out of the shared `get_context` or gate by caller).
- [~] Gate Plotly/d3/Chart.js/select2 behind the pages that use them instead of `base.html`.
- [~] Bundle + minify the 16 AJAX-loaded leaderboard JS files.
- [~] `table_library_dependencies`: declare the block in `base.html` (loads AG-Grid CSS) or delete the dead override blocks and rely on v33 theming (styling risk either way).

### Entangled / low-value (reclassified after investigation)
- [~] Cache-key filter collision (`competition2022` tracks): only that pickle-first, low-traffic page passes filters, and it also passes a dict `model_filter` that `TypeError`s on a cold cache. Fixing the key alone could flip it from stale-but-present to error page. Real fix = correct the dict `model_filter` to a callable AND encode filter identity in the key, verified on the competition page.
- [~] `table.html` `{{ domain }}` inside `{% if %}` string literals never interpolates (live via competition2022). Needs a precomputed `average_<domain>` context var in the rendering views; cosmetic, legacy pages.
- [~] `profile.html` duplicate jQuery/jszip: base loads jQuery `defer`, profile loads it non-deferred — not interchangeable. Dedup requires reconciling defer ordering + profile-page verification.
- [~] `table.html:9` malformed `<! ... >` comment: harmless (browsers treat as bogus comment); trivial cosmetic.

### Tests
- [~] Un-skip / de-flake the 10 skipped `test_ag_grid.py` value assertions; add hermetic unit tests for `get_ag_grid_context` (no coverage of the payload builder today).
