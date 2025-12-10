// Color calculation utilities
// Replicates the SQL representative_color_sql_precomputed function logic

// Precomputed color arrays matching SQL (101 colors each)
const REDGREEN_COLORS = [
  '#ff0000', '#ff0000', '#ff0000', '#ff0000', '#fe0600', '#fe0600', '#fd0d01', '#fd0d01', '#fc1301', '#fb1901', 
  '#fb1901', '#fa1f02', '#f92502', '#f92502', '#f82b02', '#f73103', '#f73103', '#f63703', '#f53d03', '#f44204', 
  '#f44204', '#f44804', '#f34d04', '#f25305', '#f15805', '#f15805', '#f05e05', '#ef6306', '#ee6806', '#ed6e06', 
  '#ec7307', '#eb7807', '#ea7d07', '#e98208', '#e88708', '#e88708', '#e78c08', '#e69109', '#e69509', '#e59a09', 
  '#e49f0a', '#e3a30a', '#e2a80a', '#e1ac0a', '#e0b10b', '#dfb50b', '#deb90b', '#ddbe0c', '#dcc20c', '#dcc60c', 
  '#dbca0d', '#d9d20d', '#d8d60d', '#d4d70e', '#cfd60e', '#c9d50e', '#c4d40f', '#bed40f', '#b9d30f', '#b4d20f', 
  '#aed110', '#a4cf10', '#9fce10', '#9acd11', '#95cc11', '#90cc11', '#8bcb11', '#86ca12', '#7dc812', '#78c712', 
  '#74c613', '#6fc613', '#6ac513', '#66c413', '#5dc214', '#59c114', '#55c014', '#51c015', '#48be15', '#44bd15', 
  '#40bc16', '#3cbb16', '#38bb16', '#31b917', '#2db817', '#29b717', '#26b617', '#1eb518', '#1bb418', '#18b319', 
  '#18b21c', '#19b124', '#19b028', '#19af2b', '#19ad32', '#1aad36', '#1aac39', '#1aaa40', '#1aa943', '#1ba947', 
  '#1ba84a'
];

const GRAY_COLORS = [
  '#f2f2f2', '#f2f2f2', '#f2f2f2', '#f2f2f2', '#f0f0f0', '#f0f0f0', '#eeeeee', '#eeeeee', '#ededed', '#ebebeb', 
  '#ebebeb', '#e9e9e9', '#e7e7e7', '#e7e7e7', '#e6e6e6', '#e4e4e4', '#e4e4e4', '#e2e2e2', '#e0e0e0', '#dedede', 
  '#dedede', '#dddddd', '#dbdbdb', '#d9d9d9', '#d7d7d7', '#d7d7d7', '#d6d6d6', '#d4d4d4', '#d2d2d2', '#d0d0d0', 
  '#cecece', '#cdcdcd', '#cbcbcb', '#c9c9c9', '#c7c7c7', '#c7c7c7', '#c5c5c5', '#c4c4c4', '#c2c2c2', '#c0c0c0', 
  '#bebebe', '#bdbdbd', '#bbbbbb', '#b9b9b9', '#b7b7b7', '#b5b5b5', '#b4b4b4', '#b2b2b2', '#b0b0b0', '#aeaeae', 
  '#adadad', '#a9a9a9', '#a7a7a7', '#a5a5a5', '#a4a4a4', '#a2a2a2', '#a0a0a0', '#9e9e9e', '#9d9d9d', '#9b9b9b', 
  '#999999', '#959595', '#949494', '#929292', '#909090', '#8e8e8e', '#8d8d8d', '#8b8b8b', '#878787', '#858585', 
  '#848484', '#828282', '#808080', '#7e7e7e', '#7b7b7b', '#797979', '#777777', '#757575', '#727272', '#707070', 
  '#6e6e6e', '#6c6c6c', '#6b6b6b', '#676767', '#656565', '#646464', '#626262', '#5e5e5e', '#5c5c5c', '#5b5b5b', 
  '#595959', '#555555', '#545454', '#525252', '#4e4e4e', '#4c4c4c', '#4b4b4b', '#474747', '#454545', '#444444', 
  '#424242'
];

const COLOR_NONE = '#e0e1e2';
const GAMMA = 0.5;  // Gamma value to stretch high-end differences

/**
 * Calculate representative color for a score value
 * Replicates the SQL representative_color_sql_precomputed function
 * 
 * @param {number} value - The score value
 * @param {number} minValue - Minimum value in the distribution
 * @param {number} maxValue - Maximum value in the distribution
 * @param {string} rootParent - Root parent identifier (e.g., 'engineering_vision_v0')
 * @returns {string} CSS color string in format "background-color: rgb(...); background-color: rgba(...);"
 */
function calculateRepresentativeColor(value, minValue, maxValue, rootParent) {
  // Return neutral grey if value is null, NaN, or invalid
  if (value === null || value === undefined || isNaN(value) || value === 'NaN' || value === '') {
    return `background-color: ${COLOR_NONE};`;
  }
  
  // Normalize the input value between 0 and 1
  let normalizedValue;
  if (maxValue - minValue === 0) {
    normalizedValue = 0.5;
  } else {
    normalizedValue = (value - minValue) / (maxValue - minValue);
  }
  normalizedValue = Math.max(0, Math.min(1, normalizedValue));
  
  // Apply gamma correction to emphasize differences at the top-end
  normalizedValue = Math.pow(normalizedValue, 1.0 / GAMMA);
  
  // Scale down the normalized value (0.8 factor)
  normalizedValue = 0.8 * normalizedValue;
  normalizedValue = Math.max(0, Math.min(1, normalizedValue));
  
  // Get color array index (0-100)
  let idx = Math.floor(100 * normalizedValue);
  if (idx > 100) {
    idx = 100;
  }
  
  // Determine color palette based on root parent
  const isEngineering = rootParent && rootParent.toLowerCase().includes('engineering');
  const colorHex = isEngineering ? GRAY_COLORS[idx] : REDGREEN_COLORS[idx];
  
  // Extract RGB values from hex color
  const r = parseInt(colorHex.substring(1, 3), 16);
  const g = parseInt(colorHex.substring(3, 5), 16);
  const b = parseInt(colorHex.substring(5, 7), 16);
  
  // Calculate alpha based on value position
  let alpha;
  if (maxValue - minValue === 0) {
    alpha = 1.0;
  } else {
    // Linear interpolation: alpha ranges from 0.1 (at min) to 1.0 (at max)
    // slope = -0.9 / (min_value - max_value)
    // intercept = 0.1 - slope * min_value
    const slope = -0.9 / (minValue - maxValue);
    const intercept = 0.1 - slope * minValue;
    alpha = slope * value + intercept;
  }
  alpha = Math.max(0, Math.min(1, alpha));
  
  // Build CSS color string
  const fallbackColor = `rgb(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)})`;
  const rgbaColor = `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(2)})`;
  
  return `background-color: ${fallbackColor}; background-color: ${rgbaColor};`;
}

/**
 * Recalculate colors for a set of benchmarks based on new score distribution
 * This is used when excluded benchmarks change the min/max ranges
 * 
 * @param {Array} rowData - Array of model row data
 * @param {string} benchmarkId - Benchmark identifier to recalculate colors for
 * @param {Map} hierarchyMap - Benchmark hierarchy map
 * @returns {void} Modifies rowData in place
 */
function recalculateColorsForBenchmark(rowData, benchmarkId, hierarchyMap) {
  // Collect all values for this benchmark across all models
  const values = [];
  rowData.forEach(row => {
    if (row[benchmarkId] && row[benchmarkId].value !== 'X' && row[benchmarkId].value !== null) {
      const val = row[benchmarkId].value;
      const numVal = typeof val === 'string' ? parseFloat(val) : val;
      if (!isNaN(numVal)) {
        values.push(numVal);
      }
    }
  });
  
  if (values.length === 0) {
    return;  // No valid scores to calculate colors for
  }
  
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  
  // Determine root parent for color palette selection
  // Find the root parent by traversing up the hierarchy
  let rootParent = null;
  let currentId = benchmarkId;
  const visited = new Set();
  
  // Traverse up the hierarchy to find root
  while (currentId && !visited.has(currentId)) {
    visited.add(currentId);
    
    // Check if currentId is a root (no parent in hierarchy)
    let hasParent = false;
    for (const [parentId, children] of hierarchyMap.entries()) {
      if (children.includes(currentId)) {
        currentId = parentId;
        hasParent = true;
        break;
      }
    }
    
    if (!hasParent) {
      // This is a root
      rootParent = currentId;
      break;
    }
  }
  
  // Fallback: if we couldn't determine root parent, infer from benchmarkId
  if (!rootParent) {
    // Check if benchmarkId or any ancestor contains 'engineering'
    const checkId = benchmarkId.toLowerCase();
    if (checkId.includes('engineering')) {
      rootParent = 'engineering_vision_v0';
    } else {
      // Default to neural for non-engineering benchmarks
      rootParent = 'neural_vision_v0';
    }
  }
  
  // Recalculate colors for each model
  rowData.forEach(row => {
    if (row[benchmarkId] && row[benchmarkId].value !== 'X' && row[benchmarkId].value !== null) {
      const val = row[benchmarkId].value;
      const numVal = typeof val === 'string' ? parseFloat(val) : val;
      if (!isNaN(numVal)) {
        const color = calculateRepresentativeColor(numVal, minValue, maxValue, rootParent);
        row[benchmarkId].color = color;
      }
    }
  });
}

// Export functions
window.LeaderboardColorUtils = {
  calculateRepresentativeColor,
  recalculateColorsForBenchmark
};

