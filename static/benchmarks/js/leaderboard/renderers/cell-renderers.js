// Cell renderers for leaderboard grid

// ModelCellRenderer - displays model name with link and submitter info
function ModelCellRenderer() {}
ModelCellRenderer.prototype.init = function(params) {
  this.eGui = document.createElement('div');
  this.eGui.className = 'model-cell';
  const a = document.createElement('a');
  a.href = `/model/vision/${params.value.id}`;
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
  if (cellObj.value != null && cellObj.value !== '' && !isNaN(Number(cellObj.value))) {
    display = Number(cellObj.value).toFixed(2);
  }
  
  let bg = window.LeaderboardConstants.DEFAULT_CELL_BG;
  if (cellObj.color) {
    const m = cellObj.color.match(/rgba?\([^)]*\)/);
    if (m) {
      const colorStr = m[0];
      if (colorStr.startsWith('rgba(')) {
        bg = colorStr.replace(/,\s*[\d.]+\)$/, `, ${window.LeaderboardConstants.CELL_ALPHA})`);
      } else if (colorStr.startsWith('rgb(')) {
        bg = colorStr.replace('rgb(', 'rgba(').replace(')', `, ${window.LeaderboardConstants.CELL_ALPHA})`);
      } else {
        bg = colorStr;
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
    pinned: 'left',
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
  createRunnableStatusColumn,
  modelComparator
};
