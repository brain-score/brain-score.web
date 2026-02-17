// Citation export functionality for benchmark references

// Setup citation export functionality
function setupCitationExport() {
  const copyBibtexBtn = document.getElementById('copyBibtexBtn');
  if (!copyBibtexBtn) return;

  copyBibtexBtn.addEventListener('click', (e) => {
    e.preventDefault();
    copyBibtexToClipboard();
  });
}

// Handle citation export button click
function handleCitationExport() {
  try {
    const bibtexContent = collectBenchmarkBibtex();

    if (!bibtexContent || bibtexContent.length === 0) {
      alert('No benchmarks selected for citation export.');
      return;
    }

    copyToClipboard(bibtexContent);
    showCopyFeedback();

  } catch (error) {
    console.error('Error copying BibTeX to clipboard:', error);
    alert('Error copying citations to clipboard. Please try again.');
  }
}

// Copy BibTeX to clipboard
function copyBibtexToClipboard() {
  const bibtexList = collectBenchmarkBibtex();

  if (bibtexList.length === 0) {
    alert('No citations found for selected benchmarks');
    return;
  }

  // Format as a single string with double line breaks between entries
  const formattedBibtex = bibtexList.join('\n\n');

  // Copy to clipboard
  navigator.clipboard.writeText(formattedBibtex).then(() => {
    const count = bibtexList.length;
    const message = `Copied ${count} citation${count === 1 ? '' : 's'} to clipboard`;
    alert(message);
  }).catch(err => {
    console.error('Failed to copy to clipboard:', err);
    alert('Failed to copy to clipboard');
  });
}

// Collect BibTeX citations for selected benchmarks
function collectBenchmarkBibtex() {
  if (!window.originalRowData || window.originalRowData.length === 0) {
    console.warn('Original row data not available');
    return [];
  }

  const excludedBenchmarks = new Set(window.filteredOutBenchmarks || []);
  const hierarchyMap = window.LeaderboardHierarchyUtils?.buildHierarchyFromTree
    ? window.LeaderboardHierarchyUtils.buildHierarchyFromTree(window.benchmarkTree)
    : (window.benchmarkTree ? buildHierarchyFromTree(window.benchmarkTree) : new Map());

  const bibtexSet = new Set();

  // Helper function to determine if a benchmark is a leaf (has no children)
  function isLeafBenchmark(benchmarkId) {
    const children = hierarchyMap.get(benchmarkId) || [];
    return children.length === 0;
  }

  // Use first model as reference for benchmark structure
  const firstModel = window.originalRowData[0];

  // Go through each field in the model data
  Object.keys(firstModel).forEach(fieldName => {
    // Skip non-benchmark fields
    if (fieldName === 'id' || fieldName === 'rank' || fieldName === 'model' || fieldName === 'metadata') {
      return;
    }

    const scoreData = firstModel[fieldName];

    // Check if this is a leaf benchmark
    if (scoreData &&
        typeof scoreData === 'object' &&
        isLeafBenchmark(fieldName)) {

      // Look up bibtex from the benchmark bibtex map
      const bibtexData = window.benchmarkBibtexMap?.[fieldName];
      // If there is bibtex data
      if (bibtexData && bibtexData.bibtex) {
        // Check if this benchmark is excluded using multiple patterns
        const baseFieldName = fieldName.replace(/_v\d+$/, '');
        const benchmarkTypeId = bibtexData.benchmark_type_id;

        // Makes sure that we do not include benchmarks that we have excluded
        const isExcluded = excludedBenchmarks.has(fieldName) ||
                          excludedBenchmarks.has(baseFieldName) ||
                          excludedBenchmarks.has(benchmarkTypeId);

        if (!isExcluded) {
          const bibtex = bibtexData.bibtex.trim();

          // Add to set if valid (Set automatically handles duplicates)
          if (bibtex && bibtex !== 'null') {
            bibtexSet.add(bibtex);
          }
        }
      }
    }
  });

  return Array.from(bibtexSet);
}

// Fallback buildHierarchyFromTree if not available from utilities
function buildHierarchyFromTree(tree, hierarchyMap = new Map()) {
  tree.forEach(node => {
    const nodeId = node.id || node.identifier || node.field || node.name;
    const children = node.children ?
      node.children.map(child => child.id || child.identifier || child.field || child.name).filter(Boolean) :
      [];
    if (nodeId) {
      hierarchyMap.set(nodeId, children);
      if (node.children && node.children.length > 0) {
        buildHierarchyFromTree(node.children, hierarchyMap);
      }
    }
  });
  return hierarchyMap;
}

// Copy text to clipboard
function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    // Modern clipboard API
    return navigator.clipboard.writeText(text);
  } else {
    // Fallback for older browsers
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
      document.execCommand('copy');
      document.body.removeChild(textArea);
      return Promise.resolve();
    } catch (err) {
      document.body.removeChild(textArea);
      return Promise.reject(err);
    }
  }
}

// Show copy feedback
function showCopyFeedback() {
  // Citations copied to clipboard
}

// Get citation count
function getCitationCount() {
  return collectBenchmarkBibtex().length;
}

// Get citation preview
function getCitationPreview(maxEntries = 3) {
  const bibtexList = collectBenchmarkBibtex();
  return bibtexList.slice(0, maxEntries);
}

// Export benchmark references
function exportBenchmarkReferences() {
  const bibtexList = collectBenchmarkBibtex();

  return {
    metadata: {
      generated_on: new Date().toISOString(),
      total_benchmarks: bibtexList.length,
      brain_score_version: '2.0'
    },
    references: bibtexList.map(bibtex => ({ bibtex }))
  };
}

// Export functions for use by other modules
window.LeaderboardCitationExport = {
  setupCitationExport,
  handleCitationExport,
  copyBibtexToClipboard,
  collectBenchmarkBibtex,
  copyToClipboard,
  showCopyFeedback,
  getCitationCount,
  getCitationPreview,
  exportBenchmarkReferences
};

window.copyBibtexToClipboard = copyBibtexToClipboard;