// Search functionality for leaderboard filtering

// Get searchable text from a row - EXACTLY like original
function getSearchableText(rowData) {
  const model = rowData.model || {};
  const searchFields = [
    model.name || '',
    model.submitter || ''
    // Future: Add metadata fields here when needed
    // rowData.metadata?.architecture || '', // Example: architecture: transformer
    // rowData.metadata?.model_family || ''
  ];
  
  return searchFields.join(' ').toLowerCase();
}

// Parse search query with logical operators (OR, AND, NOT) - EXACTLY like original
function parseSearchQuery(query) {
  if (!query.trim()) return null;
  
  // Split by OR first (lowest precedence)
  const orParts = query.toLowerCase().split(/\s+or\s+/);
  
  return {
    type: 'OR',
    parts: orParts.map(orPart => {
      // Split by AND (higher precedence than OR)
      const andParts = orPart.split(/\s+and\s+/);
      
      if (andParts.length === 1) {
        // Handle NOT for single terms (e.g., "NOT alexnet")
        const term = andParts[0].trim();
        if (term.startsWith('not ')) {
          return { type: 'NOT', term: term.substring(4).trim() };
        }
        return { type: 'TERM', term };
      }
      
      return {
        type: 'AND',
        parts: andParts.map(andPart => {
          const term = andPart.trim();
          if (term.startsWith('not ')) {
            return { type: 'NOT', term: term.substring(4).trim() };
          }
          return { type: 'TERM', term };
        })
      };
    })
  };
}

// Execute parsed search query against searchable text - EXACTLY like original
function executeSearchQuery(parsedQuery, searchableText) {
  if (!parsedQuery) return true;
  
  function evaluateNode(node) {
    switch (node.type) {
      case 'TERM':
        return searchableText.includes(node.term);
      case 'NOT':
        return !searchableText.includes(node.term);
      case 'AND':
        return node.parts.every(evaluateNode);
      case 'OR':
        return node.parts.some(evaluateNode);
      default:
        return false;
    }
  }
  
  return evaluateNode(parsedQuery);
}

// Setup search input handlers - uses same pattern as original initializeGrid
function setupSearchHandlers() {
  // This will be called from initializeGrid in the main file
  // The original connects search directly in initializeGrid()
  
  // Connect the search input with logical operators - EXACTLY like original
  const searchInput = document.getElementById('modelSearchInput');
  if (searchInput && window.globalGridApi) {
    // Remove any existing listeners
    const newInput = searchInput.cloneNode(true);
    searchInput.parentNode.replaceChild(newInput, searchInput);

    newInput.addEventListener('input', function () {
      const searchText = this.value;
      // Parse search query with logical operators (OR, AND, NOT)
      window.currentSearchQuery = parseSearchQuery(searchText);
      
      // Use external filter for logical search
      if (typeof window.globalGridApi.onFilterChanged === 'function') {
        window.globalGridApi.onFilterChanged();
      } else {
        console.warn('onFilterChanged not available on gridApi');
      }
    });
  } else {
    console.error('Search input not found or grid API not available');
  }
}

// Clear search
function clearSearch() {
  const searchInput = document.getElementById('modelSearchInput');
  if (searchInput) {
    searchInput.value = '';
    if (window.globalGridApi) {
      window.globalGridApi.setFilterModel(null);
      window.globalGridApi.setGridOption('isExternalFilterPresent', () => false);
      window.globalGridApi.onFilterChanged();
    }
  }
}

// Export functions for use by other modules
window.LeaderboardSearch = {
  getSearchableText,
  parseSearchQuery,
  executeSearchQuery,
  setupSearchHandlers,
  clearSearch
};

