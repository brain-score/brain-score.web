// =====================================
// LOADING ANIMATION (global)
// =====================================
window.LoadingSpinner = {
  show() {
    document.getElementById('loading-overlay')?.classList.add('is-active')
    window.addEventListener('beforeunload', this.handleCancel)
  },
  hide() {
    console.log('[spinner] hide')
    document.getElementById('loading-overlay')?.classList.remove('is-active')
    window.removeEventListener('beforeunload', this.handleCancel)
  },
  handleCancel() {
    window.LoadingSpinner.hide()
  }
}

// Show spinner on same-tab, same-origin link clicks that opt-in via .show-spinner
document.addEventListener('click', function (e) {
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; // ignore new-tab/middle/modifiers
  const a = e.target.closest('a.show-spinner');
  if (!a) return;

  // same-origin, not _blank
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin || a.target === '_blank') return;

  LoadingSpinner.show(); // <-- shows immediately on click
  // allow normal navigation to proceed
}, { capture: true });


// keep spinner up for a minimum duration
const SPINNER_MIN_MS = 0;
function hideSpinnerDelayed(ms = SPINNER_MIN_MS) {
  setTimeout(() => LoadingSpinner.hide(), ms);
}

// --- Global: show spinner on any click to leaderboard URLs ---
const LEADERBOARD_PATHS = [
  /^\/vision\/leaderboard\/?$/i,
  /^\/language\/leaderboard\/?$/i
];

function isSameOrigin(url) {
  try { return new URL(url, location.href).origin === location.origin; }
  catch { return false; }
}

function matchesLeaderboard(url) {
  try {
    const { pathname } = new URL(url, location.href);
    return LEADERBOARD_PATHS.some(rx => rx.test(pathname));
  } catch {
    return false;
  }
}

function resolveHrefFromTarget(target) {
  // <a href="...">
  const a = target.closest('a[href]');
  if (a) return a.href;

  // Buttons or custom elements can opt-in via data-href
  const btn = target.closest('[data-href]');
  if (btn) return btn.getAttribute('data-href');

  return null;
}

document.addEventListener('click', (e) => {
  // ignore middle/right clicks or modifier-key opens
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

  const href = resolveHrefFromTarget(e.target);
  if (!href) return;

  // only same-origin, same-tab navigations
  if (!isSameOrigin(href)) return;

  if (matchesLeaderboard(href)) {
    window.LoadingSpinner.show();
    // allow normal navigation to proceed
  }
}, { capture: true });

//------------
// --- Global: show spinner on any same-tab click that goes to a leaderboard URL ---
const LEADERBOARD_RX = /^(\/vision\/leaderboard\/?|\/language\/leaderboard\/?)(?:$|\/|\?)/i;

function resolveNavUrlFromEventTarget(target) {
  // Prefer explicit data-href (works with buttons)
  const withData = target.closest('[data-href]');
  if (withData?.dataset?.href) return withData.dataset.href;
  // Fall back to anchors
  const a = target.closest('a[href]');
  return a?.getAttribute('href') || null;
}

document.addEventListener('click', (e) => {
  // ignore middle/right clicks or modifier-key opens
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

  const rawHref = resolveNavUrlFromEventTarget(e.target);
  if (!rawHref) return;

  let url;
  try { url = new URL(rawHref, location.href); } catch { return; }
  if (url.origin !== location.origin) return;              // only same-origin
  if (e.target.closest('a[target="_blank"]')) return;      // skip new-tab anchors
  if (!LEADERBOARD_RX.test(url.pathname + (url.search || ''))) return; // match path even with query

  // Show overlay now and force a paint before navigation takes over.
  window.LoadingSpinner.show();
  // In some browsers, scheduling 1 frame improves reliability of seeing the overlay.
  // We don't preventDefault, so navigation proceeds normally.
  requestAnimationFrame(() => {});
}, { capture: true });