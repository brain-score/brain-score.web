// Grid layout helpers: viewport sizing and the synced top scrollbar.
// The grid itself is created by initializeGrid in ag-grid-leaderboard.js;
// these helpers are invoked from there and from template-initialization.js.

// Sync a top scrollbar div with AG Grid's internal horizontal scroll.
// AG Grid uses a fake scrollbar (.ag-body-horizontal-scroll-viewport) for
// horizontal scrolling -- .ag-center-cols-viewport has overflow:hidden.
// We sync with the fake scrollbar and align position with the center viewport.
function initTopScrollbar(attempt) {
  attempt = attempt || 0;

  var topScrollbar = document.getElementById('topScrollbar');
  var topScrollbarInner = document.getElementById('topScrollbarInner');
  if (!topScrollbar || !topScrollbarInner) return;

  var gridEl = document.getElementById('leaderboardGrid');
  if (!gridEl) return;

  var agScrollViewport = gridEl.querySelector('.ag-body-horizontal-scroll-viewport');
  var agScrollContainer = gridEl.querySelector('.ag-body-horizontal-scroll-container');
  var centerViewport = gridEl.querySelector('.ag-center-cols-viewport');

  if (!agScrollViewport || !agScrollContainer || !centerViewport) {
    if (attempt < 20) {
      setTimeout(function () { initTopScrollbar(attempt + 1); }, 200);
    }
    return;
  }

  var syncing = false;

  function syncWidths() {
    var scrollWidth = agScrollContainer.scrollWidth;
    var clientWidth = agScrollViewport.clientWidth;
    topScrollbarInner.style.width = scrollWidth + 'px';
    topScrollbar.style.display = scrollWidth > clientWidth ? '' : 'none';

    // Align with the center viewport (offset past pinned columns)
    var gridRect = gridEl.getBoundingClientRect();
    var vpRect = centerViewport.getBoundingClientRect();
    topScrollbar.style.marginLeft = (vpRect.left - gridRect.left) + 'px';
    topScrollbar.style.width = vpRect.width + 'px';
  }

  syncWidths();

  topScrollbar.addEventListener('scroll', function () {
    if (syncing) return;
    syncing = true;
    agScrollViewport.scrollLeft = topScrollbar.scrollLeft;
    requestAnimationFrame(function () { syncing = false; });
  });

  agScrollViewport.addEventListener('scroll', function () {
    if (syncing) return;
    syncing = true;
    topScrollbar.scrollLeft = agScrollViewport.scrollLeft;
    requestAnimationFrame(function () { syncing = false; });
  });

  // Re-sync widths when columns change (expand/collapse)
  var mutObs = new MutationObserver(syncWidths);
  mutObs.observe(agScrollContainer, { attributes: true, childList: true, subtree: true });

  // Re-sync when the grid itself resizes (sidebar toggle, window resize, etc.)
  var resizeObs = new ResizeObserver(syncWidths);
  resizeObs.observe(gridEl);

  window.addEventListener('resize', syncWidths);

  // Expose syncWidths so resizeGridToViewport can re-sync after layout changes
  window._topScrollbarSyncWidths = syncWidths;
}

// Size the grid to fill the remaining viewport height
function resizeGridToViewport() {
  var grid = document.getElementById('leaderboardGrid');
  if (!grid) return;
  var top = grid.getBoundingClientRect().top;
  var available = window.innerHeight - top - 16;
  var height = Math.max(400, available);
  grid.style.height = height + 'px';

  // Match filters panel height to grid in sidebar mode
  var container = grid.closest('.leaderboard-container');
  var panel = document.getElementById('advancedFiltersPanel');
  if (panel) {
    if (container && container.classList.contains('sidebar-mode')) {
      panel.style.maxHeight = height + 'px';
    } else {
      panel.style.maxHeight = '';
    }
  }

  // Tell AG Grid to recalculate after container height change
  if (window.globalGridApi) {
    window.globalGridApi.resetRowHeights();
  }

  // Re-sync top scrollbar after grid resize settles
  // Use double-rAF to ensure AG Grid has finished its layout pass
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      if (window._topScrollbarSyncWidths) {
        window._topScrollbarSyncWidths();
      } else {
        initTopScrollbar();
      }
    });
  });
}
