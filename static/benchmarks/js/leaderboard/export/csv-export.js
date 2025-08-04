// CSV export functionality for leaderboard data

// Setup CSV export functionality
function setupCSVExport() {
  const exportButton = document.getElementById('exportCsvButton');
  if (!exportButton) return;
  
  exportButton.addEventListener('click', handleCSVExport);
}

// Handle CSV export button click
function handleCSVExport() {
  if (!window.globalGridApi) {
    console.error('Grid API not available for export');
    return;
  }
  
  try {
    // Get current grid data (filtered)
    const rowData = [];
    window.globalGridApi.forEachNodeAfterFilterAndSort(node => {
      rowData.push(node.data);
    });
    
    if (rowData.length === 0) {
      alert('No data to export. Please adjust your filters.');
      return;
    }
    
    // Show loading state
    const originalText = document.getElementById('exportCsvButton').innerHTML;
    document.getElementById('exportCsvButton').innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Exporting...';
    document.getElementById('exportCsvButton').disabled = true;
    
    // Generate CSV files
    setTimeout(() => {
      try {
        generateCSVZip(rowData);
      } catch (error) {
        console.error('Error generating CSV:', error);
        alert('Error generating CSV export. Please try again.');
      } finally {
        // Reset button state
        document.getElementById('exportCsvButton').innerHTML = originalText;
        document.getElementById('exportCsvButton').disabled = false;
      }
    }, 100);
    
  } catch (error) {
    console.error('Error in CSV export:', error);
    alert('Error starting CSV export. Please try again.');
  }
}

// Generate ZIP file with CSV data
function generateCSVZip(rowData) {
  const zip = new JSZip();
  
  // Generate leaderboard CSV
  const leaderboardCSV = generateLeaderboardCSV(rowData);
  const timestamp = new Date().toISOString().split('T')[0];
  const filename = `brain-score-leaderboard-${timestamp}.csv`;
  
  zip.file(filename, leaderboardCSV);
  
  // Generate plugin metadata CSV
  const pluginCSV = generatePluginMetadataCSV(rowData);
  const pluginFilename = `brain-score-plugin-metadata-${timestamp}.csv`;
  
  zip.file(pluginFilename, pluginCSV);
  
  // Generate ZIP and download
  zip.generateAsync({ type: 'blob' }).then(function(content) {
    const url = URL.createObjectURL(content);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brain-score-export-${timestamp}.zip`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });
}

// Generate leaderboard CSV content
function generateLeaderboardCSV(rowData) {
  if (!rowData || rowData.length === 0) return '';
  
  // Get all benchmark columns from the first row
  const firstRow = rowData[0];
  const benchmarkColumns = Object.keys(firstRow).filter(key => 
    key !== 'model' && 
    key !== 'rank' && 
    key !== 'metadata' &&
    typeof firstRow[key] === 'object' &&
    firstRow[key] !== null
  );
  
  // Sort benchmark columns for consistent output
  benchmarkColumns.sort();
  
  // Create header
  const headers = [
    'Model Name',
    'Submitter',
    'Identifier',
    ...benchmarkColumns
  ];
  
  // Create rows
  const rows = rowData.map(row => {
    const modelData = row.model || {};
    const rowArray = [
      escapeCSVField(modelData.name || ''),
      escapeCSVField(modelData.submitter || ''),
      escapeCSVField(modelData.id || ''),
      ...benchmarkColumns.map(col => {
        const cellData = row[col];
        if (cellData && cellData.value !== undefined) {
          return cellData.value === 'X' ? 'X' : cellData.value;
        }
        return '';
      })
    ];
    return rowArray.join(',');
  });
  
  // Add generation timestamp
  const timestamp = new Date().toISOString();
  const headerComment = `# Brain-Score Leaderboard Export\n# Generated on: ${timestamp}\n# Total models: ${rowData.length}\n`;
  
  return headerComment + headers.join(',') + '\n' + rows.join('\n');
}

// Generate plugin metadata CSV content
function generatePluginMetadataCSV(rowData) {
  if (!rowData || rowData.length === 0) return '';
  
  // Get all possible metadata fields from all rows
  const metadataFields = new Set();
  rowData.forEach(row => {
    if (row.metadata) {
      Object.keys(row.metadata).forEach(key => metadataFields.add(key));
    }
  });
  
  const sortedFields = Array.from(metadataFields).sort();
  
  // Create header
  const headers = [
    'Model Name',
    'Submitter',
    'Identifier',
    ...sortedFields
  ];
  
  // Create rows
  const rows = rowData.map(row => {
    const modelData = row.model || {};
    const metadata = row.metadata || {};
    
    const rowArray = [
      escapeCSVField(modelData.name || ''),
      escapeCSVField(modelData.submitter || ''),
      escapeCSVField(modelData.id || ''),
      ...sortedFields.map(field => {
        const value = metadata[field];
        if (value === null || value === undefined) {
          return '';
        }
        return escapeCSVField(value.toString());
      })
    ];
    return rowArray.join(',');
  });
  
  // Add generation timestamp
  const timestamp = new Date().toISOString();
  const headerComment = `# Brain-Score Plugin Metadata Export\n# Generated on: ${timestamp}\n# Total models: ${rowData.length}\n`;
  
  return headerComment + headers.join(',') + '\n' + rows.join('\n');
}

// Escape CSV field if it contains special characters
function escapeCSVField(field) {
  if (typeof field !== 'string') {
    field = String(field);
  }
  
  // If field contains comma, newline, or quote, wrap in quotes and escape internal quotes
  if (field.includes(',') || field.includes('\n') || field.includes('"')) {
    return '"' + field.replace(/"/g, '""') + '"';
  }
  
  return field;
}

// Get current filter summary for export metadata
function getFilterSummary() {
  const activeFilters = window.activeFilters || {};
  const summary = [];
  
  // Model property filters
  if (activeFilters.architecture?.length > 0) {
    summary.push(`Architecture: ${activeFilters.architecture.join(', ')}`);
  }
  
  if (activeFilters.model_family?.length > 0) {
    summary.push(`Model Family: ${activeFilters.model_family.join(', ')}`);
  }
  
  // Benchmark filters
  if (activeFilters.benchmark_regions?.length > 0) {
    summary.push(`Regions: ${activeFilters.benchmark_regions.join(', ')}`);
  }
  
  if (activeFilters.benchmark_species?.length > 0) {
    summary.push(`Species: ${activeFilters.benchmark_species.join(', ')}`);
  }
  
  if (activeFilters.benchmark_tasks?.length > 0) {
    summary.push(`Tasks: ${activeFilters.benchmark_tasks.join(', ')}`);
  }
  
  if (activeFilters.public_data_only) {
    summary.push('Public Data Only: Yes');
  }
  
  // Range filters
  if (activeFilters.min_param_count || activeFilters.max_param_count) {
    summary.push(`Parameter Count: ${activeFilters.min_param_count || 0}M - ${activeFilters.max_param_count || 'unlimited'}M`);
  }
  
  if (activeFilters.min_model_size || activeFilters.max_model_size) {
    summary.push(`Model Size: ${activeFilters.min_model_size || 0}MB - ${activeFilters.max_model_size || 'unlimited'}MB`);
  }
  
  return summary.length > 0 ? summary.join('; ') : 'No filters applied';
}

// Export functions for use by other modules
window.LeaderboardCSVExport = {
  setupCSVExport,
  handleCSVExport,
  generateCSVZip,
  generateLeaderboardCSV,
  generatePluginMetadataCSV,
  escapeCSVField,
  getFilterSummary
};