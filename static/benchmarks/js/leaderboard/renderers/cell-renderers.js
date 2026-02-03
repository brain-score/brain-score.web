// Cell renderers for leaderboard grid

// ModelCellRenderer - displays model name with link and submitter info
function ModelCellRenderer() {}
ModelCellRenderer.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'model-cell';
  const a = document.createElement('a');
  const domain = (window.DJANGO_DATA && window.DJANGO_DATA.domain) || 'vision';
  a.href = `/model/${domain}/${params.value.id}`;
  a.textContent = params.value.name;
  this.eGui.appendChild(a);

  if (params.value.submitter) {
    const contributor = document.createElement('div');
    contributor.className = 'model-submitter';
    contributor.textContent = params.value.submitter;
    this.eGui.appendChild(contributor);
  }
};
ModelCellRenderer.prototype.getGui = function() {
  return this.eGui;
};

// RunnableStatusCellRenderer - displays colored status circles
function RunnableStatusCellRenderer() {}
RunnableStatusCellRenderer.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'runnable-status-cell';
  
  const runnable = params.data?.metadata?.runnable;
  const statusIcon = document.createElement('div');
  statusIcon.className = 'runnable-status-icon';
  
  if (runnable === true) {
    statusIcon.classList.add(window.LeaderboardConstants.RUNNABLE_STATUS.FUNCTIONAL);
  } else if (runnable === false) {
    statusIcon.classList.add(window.LeaderboardConstants.RUNNABLE_STATUS.ISSUES);
  } else {
    statusIcon.classList.add(window.LeaderboardConstants.RUNNABLE_STATUS.UNKNOWN);
  }
  
  this.eGui.appendChild(statusIcon);
};
RunnableStatusCellRenderer.prototype.getGui = function() {
  return this.eGui;
};

// ScoreCellRenderer - displays colored score pills
function ScoreCellRenderer() {}
ScoreCellRenderer.prototype.init = function(params) {
  const field = params.colDef.field;
  const cellObj = params.data[field] || {};

  let display = 'X';
  let bg = window.LeaderboardConstants.DEFAULT_CELL_BG;

  if (cellObj.value != null && cellObj.value !== '' && !isNaN(Number(cellObj.value))) {
    // Value is pre-rounded to 2 decimal places by Python backend
    // Use the value directly - it's already properly formatted
    display = String(cellObj.value);

    // Check if color is already set (e.g., blue from advanced filtering)
    // If so, use that color instead of recalculating
    if (cellObj.color) {
      bg = cellObj.color;
    } else {
      // Compute color client-side using existing color-utils.js function
      const benchmarkId = field;
      const stats = window.benchmarkStats && window.benchmarkStats[benchmarkId];

      if (stats && window.LeaderboardColorUtils?.calculateRepresentativeColor) {
        // Get root parent for color palette selection (engineering vs. non-engineering)
        const rootParent = params.colDef.context?.rootParent || null;

        // Calculate color using existing function
        const colorCss = window.LeaderboardColorUtils.calculateRepresentativeColor(
          parseFloat(cellObj.value),
          stats.min,
          stats.max,
          rootParent
        );

        // Extract rgba value from CSS string (format: "background-color: rgb(...); background-color: rgba(...);")
        const rgbaMatch = colorCss.match(/rgba?\([^)]*\)/g);
        if (rgbaMatch && rgbaMatch.length > 0) {
          // Use the last match (rgba with alpha channel)
          const colorStr = rgbaMatch[rgbaMatch.length - 1];
          if (colorStr.startsWith('rgba(')) {
            bg = colorStr.replace(/,\s*[\d.]+\)$/, `, ${window.LeaderboardConstants.CELL_ALPHA})`);
          } else if (colorStr.startsWith('rgb(')) {
            bg = colorStr.replace('rgb(', 'rgba(').replace(')', `, ${window.LeaderboardConstants.CELL_ALPHA})`);
          } else {
            bg = colorStr;
          }
        }
      }
    }
  }

  this.eGui = document.createElement('div');
  this.eGui.className = 'score-pill-container';
  const pill = document.createElement('div');
  pill.className = 'score-pill';
  pill.textContent = display;
  pill.style.backgroundColor = bg;
  this.eGui.appendChild(pill);
};
ScoreCellRenderer.prototype.getGui = function() {
  return this.eGui;
};

// Helper function to create runnable status column definition
function createRunnableStatusColumn() {
  return {
    headerName: '',
    field: 'runnable_status',
    colId: 'runnable_status',
    lockPosition: true,
    suppressMovable: true,
    width: window.LeaderboardConstants.COLUMN_WIDTHS.RUNNABLE_STATUS,
    cellRenderer: 'runnableStatusCellRenderer',
    sortable: true,
    filter: false,
    headerClass: 'centered-header',
    valueGetter: params => {
      const runnable = params.data?.metadata?.runnable;
      return runnable === true ? 
        window.LeaderboardConstants.RUNNABLE_SORT_VALUES.FUNCTIONAL : 
        runnable === false ? 
          window.LeaderboardConstants.RUNNABLE_SORT_VALUES.ISSUES : 
          window.LeaderboardConstants.RUNNABLE_SORT_VALUES.UNKNOWN;
    },
    tooltipValueGetter: params => {
      const runnable = params.data?.metadata?.runnable;
      if (runnable === true) {
        return window.LeaderboardConstants.RUNNABLE_TOOLTIPS.FUNCTIONAL;
      } else if (runnable === false) {
        return window.LeaderboardConstants.RUNNABLE_TOOLTIPS.ISSUES;
      } else {
        return window.LeaderboardConstants.RUNNABLE_TOOLTIPS.UNKNOWN;
      }
    }
  };
}

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

// Model comparator for sorting
function modelComparator(a, b) {
  const nameA = a?.name?.toLowerCase() || '';
  const nameB = b?.name?.toLowerCase() || '';
  return nameA.localeCompare(nameB);
}

// Export functions for use by other modules
window.LeaderboardRenderers = {
  ModelCellRenderer,
  RunnableStatusCellRenderer,
  ScoreCellRenderer,
  PublicToggleCellRenderer,
  createRunnableStatusColumn,
  modelComparator
};
