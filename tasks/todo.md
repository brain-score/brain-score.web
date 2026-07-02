# Leaderboard audit — fix plan

Branch: `kp/leaderboard-audit-fixes` (off `master`). Local commits only, Conventional Commits, no push.

Legend: `[ ]` todo, `[x]` done, `[~]` held for sign-off.

## Fix now — safe, localized, within existing architecture

### Logging hygiene (pure noise removal)
- [ ] Remove `DEBUG` `logger.warning` block `leaderboard.py:187-191`
- [ ] Remove `DEBUG` `logger.warning` + the debug-only `.count()` in `index.py` (~L90, L112, L120, L122)
- [ ] Downgrade misused `logger.error` -> `debug` and drop emoji in `utils.py` (L144, L148, L214, L219); cache hit/miss/timing to `debug`

### Delete dead code
- [ ] Delete `static/benchmarks/js/leaderboard-init.js` (0 refs)
- [ ] Delete `static/benchmarks/js/leaderboard/ui/ui-handlers.js` (0 refs)
- [ ] Delete `static/benchmarks/js/leaderboard/core/state-management.js` (0 refs)
- [ ] Delete orphan template `benchmarks/templates/benchmarks/index.html`
- [ ] Remove unrouted `index.view` + dead legacy templates `leaderboard/leaderboard.html`, `leaderboard/leaderboard-table.html`, `leaderboard/info-section.html` (verify `views/__init__.py` + `urls.py` import chain first)
- [ ] Remove dead `index.py` helpers `build_model_benchmark_frames`, `_extract_score_value`, `_parse_end_timestamp`

### Correctness
- [ ] Cache-key collision: bypass cache in `cache_get_context` when an opaque `benchmark_filter`/`model_filter` is present (fixes competition2022 track collision); main leaderboard unaffected (passes no filters)
- [ ] Add `is_profile_view` to the cache key in `cache_get_context`
- [ ] Cross-domain: parametrize `normalize_id` / `average_vision_v0` filter by `domain` in `leaderboard.py` (L105, L680)
- [ ] Template: precompute `average_<domain>` var; fix `{{ domain }}`-in-`{% if %}` literals in `table.html` (L70, L76)
- [ ] Template: fix malformed HTML comments `<! ... >` in `table.html:9`, `leaderboard-table.html` (if kept)
- [ ] `profile.html`: drop duplicate jQuery / jszip re-includes (already in `base.html`)

### Backend performance (localized)
- [ ] `find_root_parent` + `build_benchmark_tree`: O(n^2) -> O(n) via a single `{identifier: benchmark}` / child->parent map
- [ ] `utils.py`: compute `estimate_size` once per cache-miss (remove the duplicate pickle at L224 vs L235)

### JS performance (localized, low risk)
- [ ] Remove the dead whole-hierarchy rebuild `header-components.js:94` (`buildHierarchyFromTree` result unused; body reads `window.cachedHierarchyMap`)

## Hold for sign-off — architectural / needs runtime verification

- [~] Collapse legacy `ag-grid-leaderboard.js` into the modular `leaderboard/` tree (removes shadowing root cause: dead `grid-initialization.js`, dead renderer half of `cell-renderers.js`, the `getAllDescendantsFromHierarchy` stub). High risk, needs browser verification.
- [~] Filter double-render: `updateFilteredScores` sets `rowData` then `applyCombinedFilters` sets it again + `redrawRows()` (`filter-coordinator.js:322`). Real jank fix but needs runtime verification of filtering.
- [~] Payload delivery: move the inline JSON matrix to a real JSON endpoint / `json_script`; dedupe the 2x-4x metadata maps; drop `historical_versions` from default cells.
- [~] Stop computing/caching `comparison_data` + CSV on the leaderboard path (split out of shared `get_context` or gate by caller).
- [~] Gate Plotly/d3/Chart.js/select2 behind the pages that use them instead of `base.html`.
- [~] Bundle + minify the 16 AJAX-loaded leaderboard JS files.
- [~] `table_library_dependencies`: either declare the block in `base.html` (loads AG-Grid CSS) or delete the dead override blocks and rely on v33 theming explicitly (styling risk either way).
- [~] Tests: un-skip / de-flake the 10 skipped `test_ag_grid.py` value assertions; add hermetic unit tests for `get_ag_grid_context`.
- [~] JS domain hardcoding in filter pipeline (`filter-coordinator.js`, `hierarchy-utils.js`) — couples to the collapse work above; fix together.

## Review notes
- Verify each backend change with `manage.py check` (web-2026 env) where feasible; no DB writes, no migrations.
- One logical change per commit.
