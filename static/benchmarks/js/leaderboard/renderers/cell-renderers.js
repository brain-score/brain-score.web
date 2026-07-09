// Cell renderers owned by the modular tree.
// The model/score/group-status renderers live in ag-grid-leaderboard.js
// (the file that wins by load order); only the profile-page public toggle
// is owned here and pulled in via window.LeaderboardRenderers.

// PublicToggleCellRenderer - displays toggle switch for public/private
function PublicToggleCellRenderer() {}
PublicToggleCellRenderer.prototype.init = function(params) {
  this.params = params;
  this.eGui = document.createElement('div');
  this.eGui.className = 'public-toggle-cell';
  this.eGui.style.display = 'flex';
  this.eGui.style.justifyContent = 'center';
  this.eGui.style.alignItems = 'center';
  this.eGui.style.height = '100%';

  // Only show toggle if user owns the model
  if (params.data && params.data.is_owner) {
    const toggleWrapper = document.createElement('div');
    toggleWrapper.className = 'toggle-wrapper';
    toggleWrapper.style.cursor = 'pointer';

    const toggleButton = document.createElement('button');
    toggleButton.className = 'toggle-switch';

    const isPublic = params.data.public === true || params.data.public === 'true' || params.data.public === 1 || params.data.public === '1';
    toggleButton.setAttribute('aria-pressed', isPublic ? 'true' : 'false');
    toggleButton.title = isPublic ? 'Make private' : 'Make public';

    const knob = document.createElement('span');
    knob.className = 'knob';

    toggleButton.appendChild(knob);
    toggleWrapper.appendChild(toggleButton);
    this.eGui.appendChild(toggleWrapper);

    // Add click handler
    toggleButton.addEventListener('click', (e) => {
      e.stopPropagation();
      this.handleToggle(params);
    });
  }
};
PublicToggleCellRenderer.prototype.getGui = function() {
  return this.eGui;
};
PublicToggleCellRenderer.prototype.handleToggle = function(params) {
  const modelId = params.data.id;
  const currentPublicStatus = !!params.data.public;
  const newPublicStatus = !currentPublicStatus;

  // Send AJAX request to backend
  fetch('/profile/public-ajax/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': this.getCookie('csrftoken')
    },
    body: JSON.stringify({
      id: modelId,
      public: newPublicStatus
    })
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Failed to update model visibility');
    }
    return response.json();
  })
  .then(data => {
    // Update the row data
    params.data.public = newPublicStatus;

    // Update the UI
    const toggleButton = this.eGui.querySelector('.toggle-switch');
    if (toggleButton) {
      toggleButton.setAttribute('aria-pressed', newPublicStatus ? 'true' : 'false');
      toggleButton.title = newPublicStatus ? 'Make private' : 'Make public';

      // Trigger AG-Grid refresh
      if (window.globalGridApi) {
        window.globalGridApi.refreshCells({ rowNodes: [params.node] });
      }
    }

    // Inform user to apply changes (with bold model name)
    const modelName = params.data?.model?.name || 'your model';
    const note = document.createElement('div');
    note.className = 'notification is-info is-light';
    note.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      max-width: 420px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      padding: 12px 14px;
      border-radius: 6px;
      background: #eef6ff;
      color: #114a7a;
      font-size: 14px;
    `;
    note.innerHTML = `Changes saved for <strong>${modelName}</strong>.<br/>Please hit <strong>Apply</strong> below to apply your changes.`;
    document.body.appendChild(note);
    setTimeout(() => { if (note.parentNode) note.parentNode.removeChild(note); }, 5000);
  })
  .catch(error => {
    console.error('Error updating model visibility:', error);
    alert('Failed to update model visibility. Please try again.');
  });
};
PublicToggleCellRenderer.prototype.getCookie = function(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
};

// Export for use by other modules (the grid pulls publicToggleCellRenderer from here)
window.LeaderboardRenderers = {
  PublicToggleCellRenderer
};
