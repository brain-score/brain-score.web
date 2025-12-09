// Hierarchy utilities for benchmark tree navigation and management

// Get filtered leaf count for a benchmark category
function getFilteredLeafCount(parentField) {
  if (!window.benchmarkTree || !window.filteredOutBenchmarks) {
    console.warn('getFilteredLeafCount: Missing dependencies:', {
      benchmarkTree: !!window.benchmarkTree,
      filteredOutBenchmarks: !!window.filteredOutBenchmarks,
      parentField
    });
    return 0;
  }
  
  // Use cached hierarchy map to improve performance
  if (!window.cachedHierarchyMap) {
    window.cachedHierarchyMap = buildHierarchyFromTree(window.benchmarkTree);
  }
  const hierarchyMap = window.cachedHierarchyMap;
  const excludedBenchmarks = window.filteredOutBenchmarks;
  
  // For top-level categories like 'average_vision_v0', we want to count all included benchmarks across all categories
  if (parentField === 'average_vision_v0') {
    // Get all leaf benchmarks across all categories
    const allLeafIds = new Set();
    const visionCategories = ['neural_vision_v0', 'behavior_vision_v0'];
    
    visionCategories.forEach(category => {
      if (hierarchyMap.has(category)) {
        const categoryLeafs = getAllLeafDescendants(category, hierarchyMap);
        categoryLeafs.forEach(leafId => allLeafIds.add(leafId));
      }
    });
    
    // Count how many are NOT excluded
    const count = Array.from(allLeafIds).filter(leafId => !excludedBenchmarks.has(leafId)).length;
    return count;
  }
  
  // For specific categories, get direct leaf descendants
  const leafDescendants = getAllLeafDescendants(parentField, hierarchyMap);
  
  // Count how many are NOT excluded
  const count = leafDescendants.filter(leafId => !excludedBenchmarks.has(leafId)).length;
  
  return count;
}

// Get all leaf descendants of a benchmark
function getAllLeafDescendants(benchmarkId, hierarchyMap) {
  const children = hierarchyMap.get(benchmarkId) || [];
  let leafDescendants = [];
  
  children.forEach(childId => {
    const grandchildren = hierarchyMap.get(childId) || [];
    if (grandchildren.length === 0) {
      // This is a leaf
      leafDescendants.push(childId);
    } else {
      // This has children, recurse
      leafDescendants.push(...getAllLeafDescendants(childId, hierarchyMap));
    }
  });
  
  return leafDescendants;
}

// Build hierarchy map from benchmark tree
function buildHierarchyFromTree(tree, hierarchyMap = new Map()) {
  console.log('🔧 buildHierarchyFromTree called with:', {
    treeLength: tree?.length,
    mapSize: hierarchyMap.size,
    firstNodes: tree?.slice(0, 3)?.map(node => ({
      id: node.id,
      identifier: node.identifier,
      name: node.name,
      childrenCount: node.children?.length || 0
    }))
  });
  
  tree.forEach((node, index) => {
    // More comprehensive property checking
    const nodeId = node.id || node.identifier || node.field || node.name;
    
    const children = node.children ? 
      node.children.map(child => child.id || child.identifier || child.field || child.name).filter(Boolean) : 
      [];
    
    hierarchyMap.set(nodeId, children);
    
    if (node.children && node.children.length > 0) {
      buildHierarchyFromTree(node.children, hierarchyMap);
    }
  });
  
  return hierarchyMap;
}

// Get all descendants recursively
function getAllDescendantsFromHierarchy(parentId, hierarchyMap) {
  const children = hierarchyMap.get(parentId) || [];
  let descendants = [...children];
  children.forEach(childId => {
    descendants.push(...getAllDescendantsFromHierarchy(childId, hierarchyMap));
  });
  return descendants;
}

// Get all ancestors of a benchmark
function getAllAncestors(benchmarkId, hierarchyMap) {
  const ancestors = [];
  
  for (const [parentId, children] of hierarchyMap.entries()) {
    if (children.includes(benchmarkId)) {
      ancestors.push(parentId);
      ancestors.push(...getAllAncestors(parentId, hierarchyMap));
    }
  }
  
  return ancestors;
}

// Find parent of a benchmark
function findParent(benchmarkId, hierarchyMap) {
  for (const [parentId, children] of hierarchyMap.entries()) {
    if (children.includes(benchmarkId)) {
      return parentId;
    }
  }
  return null;
}

// Check if benchmark is a leaf node
function isLeafBenchmark(benchmarkId, hierarchyMap) {
  const children = hierarchyMap.get(benchmarkId) || [];
  return children.length === 0;
}

// Check if benchmark is a parent node
function isParentBenchmark(benchmarkId, hierarchyMap) {
  const children = hierarchyMap.get(benchmarkId) || [];
  return children.length > 0;
}

// Check if a benchmark subtree is fully excluded
// A benchmark is fully excluded if it OR all its descendants are in the excluded set
function isFullyExcluded(benchmarkId, hierarchyMap, excludedSet) {
  if (excludedSet.has(benchmarkId)) return true;
  const children = hierarchyMap.get(benchmarkId) || [];
  if (children.length === 0) return excludedSet.has(benchmarkId);
  return children.every(child => isFullyExcluded(child, hierarchyMap, excludedSet));
}

// Get depth level of a benchmark in the hierarchy
function getDepthLevel(benchmarkId, hierarchyMap, visited = new Set()) {
  if (visited.has(benchmarkId)) return 0;
  visited.add(benchmarkId);
  
  const children = hierarchyMap.get(benchmarkId) || [];
  if (children.length === 0) return 0;
  
  const maxChildDepth = Math.max(...children.map(child => getDepthLevel(child, hierarchyMap, new Set(visited))));
  return maxChildDepth + 1;
}

// Get all benchmarks at a specific depth level
function getBenchmarksAtDepth(hierarchyMap, targetDepth) {
  const benchmarks = [];
  
  for (const benchmarkId of hierarchyMap.keys()) {
    const depth = getDepthLevel(benchmarkId, hierarchyMap);
    if (depth === targetDepth) {
      benchmarks.push(benchmarkId);
    }
  }
  
  return benchmarks;
}

// Get benchmark tree path (from root to benchmark)
function getBenchmarkPath(benchmarkId, hierarchyMap) {
  const path = [];
  let currentId = benchmarkId;
  
  while (currentId) {
    path.unshift(currentId);
    currentId = findParent(currentId, hierarchyMap);
  }
  
  return path;
}

// Get siblings of a benchmark
function getSiblings(benchmarkId, hierarchyMap) {
  const parent = findParent(benchmarkId, hierarchyMap);
  if (!parent) return [];
  
  const siblings = hierarchyMap.get(parent) || [];
  return siblings.filter(id => id !== benchmarkId);
}

// Update all count badges in the UI
function updateAllCountBadges() {
  const countBadges = document.querySelectorAll('[data-parent-field]');
  
  countBadges.forEach(badge => {
    const parentField = badge.dataset.parentField;
    const countElement = badge.querySelector('.count-value');
    
    if (countElement && parentField) {
      const newCount = getFilteredLeafCount(parentField);
      countElement.textContent = newCount;
    }
  });
  
  // Debounced column visibility update to improve performance
  if (window.columnVisibilityUpdateTimeout) {
    clearTimeout(window.columnVisibilityUpdateTimeout);
  }
  window.columnVisibilityUpdateTimeout = setTimeout(() => {
    if (typeof window.LeaderboardHeaderComponents?.updateColumnVisibility === 'function') {
      window.LeaderboardHeaderComponents.updateColumnVisibility();
    }
  }, 150);
}

// Check if benchmark should be visible based on expansion state
function shouldBenchmarkBeVisible(benchmarkId, hierarchyMap) {
  const topLevelCategories = ['average_vision_v0', 'neural_vision_v0', 'behavior_vision_v0', 'engineering_vision_v0'];
  
  if (topLevelCategories.includes(benchmarkId)) {
    return true;
  }
  
  const parent = findParent(benchmarkId, hierarchyMap);
  if (!parent) return true;
  
  const isParentExpanded = window.columnExpansionState.get(parent) === true;
  const isParentVisible = shouldBenchmarkBeVisible(parent, hierarchyMap);
  
  return isParentExpanded && isParentVisible;
}

// Get benchmark display name
function getBenchmarkDisplayName(benchmarkId) {
  const nameMap = {
    'average_vision_v0': 'Global Score',
    'neural_vision_v0': 'Neural',
    'behavior_vision_v0': 'Behavior',
    'engineering_vision_v0': 'Engineering'
  };
  
  return nameMap[benchmarkId] || benchmarkId;
}

// Export functions for use by other modules
window.LeaderboardHierarchyUtils = {
  getFilteredLeafCount,
  getAllLeafDescendants,
  buildHierarchyFromTree,
  getAllDescendantsFromHierarchy,
  getAllAncestors,
  findParent,
  isLeafBenchmark,
  isParentBenchmark,
  isFullyExcluded,
  getDepthLevel,
  getBenchmarksAtDepth,
  getBenchmarkPath,
  getSiblings,
  updateAllCountBadges,
  shouldBenchmarkBeVisible,
  getBenchmarkDisplayName
};

// Make main functions globally available for compatibility with header components
window.getFilteredLeafCount = getFilteredLeafCount;
window.updateAllCountBadges = updateAllCountBadges;
window.buildHierarchyFromTree = buildHierarchyFromTree;
window.getAllDescendantsFromHierarchy = getAllDescendantsFromHierarchy;