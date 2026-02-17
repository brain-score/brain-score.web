/**
 * Refresh Leaderboard Module
 * Handles the "Apply Changes" button functionality for public/private model toggles
 */

(function(){
  // Wait for DOM to be ready
  function init() {
    const btn = document.getElementById('applyPublicChangesBtn');
    if (!btn) return;
    
    btn.addEventListener('click', function(){
      // Build list of changed models (compare current grid data vs originalRowData snapshot)
      const gridApi = window.globalGridApi;
      if (!gridApi || !Array.isArray(window.originalRowData)) {
        // Fallback generic confirmation
        const fallbackMsg = 'You are about to apply your public/private changes.\nThis may take up to 5 minutes. Proceed?';
        if (!window.confirm(fallbackMsg)) return;
        return triggerRefresh(btn);
      }

      const originalById = new Map(window.originalRowData.map(r => [r.id, r]));
      const pending = [];
      gridApi.forEachNode((node) => {
        const current = node.data;
        const original = originalById.get(current.id);
        if (!original) return;
        const origPublic = original.public === true || original.public === 'true' || original.public === 1 || original.public === '1';
        const currPublic = current.public === true || current.public === 'true' || current.public === 1 || current.public === '1';
        if (origPublic !== currPublic) {
          pending.push({ name: current?.model?.name || `ID ${current.id}` , to: currPublic ? 'public' : 'private' });
        }
      });

      if (pending.length === 0) {
        alert('No changes to apply.');
        return;
      }

      // Use a styled confirmation modal to allow bold names
      showConfirmListModal(pending, () => triggerRefresh(btn));
    });
  }

  function triggerRefresh(btn){
    btn.disabled = true;
    fetch('/profile/refresh-leaderboard/', {
      method: 'POST',
      headers: {
        'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/)||[])[1] || ''
      }
    }).then(r => {
      if (!r.ok) throw new Error('Request failed');
      return r.json();
    }).then(() => {
      btn.textContent = 'Applied. Refreshing soon...';
    }).catch(() => {
      btn.disabled = false;
      alert('Failed to trigger refresh. Please try again.');
    });
  }

  function showConfirmListModal(items, onConfirm){
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:10000;display:flex;align-items:center;justify-content:center;';
    const modal = document.createElement('div');
    modal.style.cssText = 'background:#fff;border-radius:8px;max-width:560px;width:92%;padding:20px;box-shadow:0 8px 24px rgba(0,0,0,.2);color:#1a1a1a;';
    const listHtml = items.map(p => `<li style="margin:0;">You are about to make your model <strong>${escapeHtml(p.name)}</strong> ${p.to}.</li>`).join('');
    modal.innerHTML = `
      <div style="font-size:16px;line-height:1.45;">
        <ul style="list-style:none;padding-left:0;margin:0 0 10px 0;">${listHtml}</ul>
        <div style="font-size:13px;color:#555;margin-top:8px;">Please confirm this is what you want to do.</div>
        <div style="font-size:12px;color:#777;margin-top:6px;">Note: It may take up to 5 minutes for changes to be reflected on the public leaderboard. Please do not submit another request during this time.</div>
      </div>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px;">
        <button id="confirm-cancel" class="button" style="background:#6c757d;color:#fff;border:none;padding:8px 14px;border-radius:4px;cursor:pointer;">Cancel</button>
        <button id="confirm-yes" class="button button-primary" style="padding:8px 14px;border-radius:4px;cursor:pointer;">Confirm</button>
      </div>`;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    modal.querySelector('#confirm-cancel').addEventListener('click', () => close(false));
    modal.querySelector('#confirm-yes').addEventListener('click', () => close(true));
    overlay.addEventListener('click', e => { if (e.target === overlay) close(false); });
    function close(ok){
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      if (ok && typeof onConfirm === 'function') onConfirm();
    }
    function escapeHtml(str){
      return String(str).replace(/[&<>\"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[s]));
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

