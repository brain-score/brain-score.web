/**
 * Tooltip Component JavaScript
 * 
 * A reusable tooltip utility for creating positioned tooltips with various styles.
 * 
 * Usage:
 * - createTooltip(element, message, options) - Advanced usage with full configuration
 * - showTooltip(elementId, message, type) - Simple usage for backward compatibility
 */

/**
 * Creates a tooltip for the given element with advanced options
 * @param {HTMLElement} element - DOM element to attach tooltip to
 * @param {string} message - Text to display in tooltip
 * @param {Object} options - Configuration object
 * @param {string} options.type - Tooltip type: 'info', 'success', 'error', 'warning' (default: 'info')
 * @param {string} options.position - Tooltip position: 'top', 'bottom', 'left', 'right' (default: 'top')
 * @param {number} options.duration - Auto-hide duration in ms (default: 2500)
 * @param {number} options.offset - Distance from element in pixels (default: 10)
 * @returns {Object|null} Object with `element` and `remove()` method, or null if element is invalid
 */
function createTooltip(element, message, options = {}) {
  const {
    type = 'info',
    position = 'top',
    duration = 2500,
    offset = 10
  } = options;
  
  if (!element) return null;
  
  // Remove any existing tooltip
  const existingTooltip = document.querySelector('.tooltip');
  if (existingTooltip) {
    existingTooltip.remove();
  }
  
  // Create tooltip element
  const tooltip = document.createElement('div');
  tooltip.className = `tooltip tooltip-${type}`;
  if (position !== 'top') {
    tooltip.classList.add(`tooltip-${position}`);
  }
  tooltip.textContent = message;
  
  // Position tooltip
  const rect = element.getBoundingClientRect();
  
  switch (position) {
    case 'bottom':
      tooltip.style.left = `${rect.left + (rect.width / 2)}px`;
      tooltip.style.top = `${rect.bottom + offset}px`;
      tooltip.style.transform = 'translateX(-50%)';
      break;
    case 'left':
      tooltip.style.left = `${rect.left - offset}px`;
      tooltip.style.top = `${rect.top + (rect.height / 2)}px`;
      tooltip.style.transform = 'translateX(-100%) translateY(-50%)';
      break;
    case 'right':
      tooltip.style.left = `${rect.right + offset}px`;
      tooltip.style.top = `${rect.top + (rect.height / 2)}px`;
      tooltip.style.transform = 'translateY(-50%)';
      break;
    default: // top
      tooltip.style.left = `${rect.left + (rect.width / 2)}px`;
      tooltip.style.top = `${rect.top - offset}px`;
      tooltip.style.transform = 'translateX(-50%) translateY(-100%)';
  }
  
  document.body.appendChild(tooltip);
  
  // Auto-remove after specified duration
  const timeoutId = setTimeout(() => {
    if (tooltip.parentNode) {
      tooltip.parentNode.removeChild(tooltip);
    }
  }, duration);
  
  // Return tooltip element and cleanup function
  return {
    element: tooltip,
    remove: () => {
      clearTimeout(timeoutId);
      if (tooltip.parentNode) {
        tooltip.parentNode.removeChild(tooltip);
      }
    }
  };
}

/**
 * Simplified tooltip function for backward compatibility
 * @param {string} elementId - ID of element to attach tooltip to
 * @param {string} message - Text to display
 * @param {string} type - Tooltip type (default: 'info')
 * @returns {Object|null} Tooltip object or null if element not found
 */
function showTooltip(elementId, message, type = 'info') {
  const element = document.getElementById(elementId);
  return createTooltip(element, message, { type });
}

/**
 * Creates a tooltip on hover for the given element
 * @param {HTMLElement} element - Element to add hover tooltip to
 * @param {string} message - Tooltip message
 * @param {Object} options - Tooltip options (same as createTooltip)
 */
function addHoverTooltip(element, message, options = {}) {
  if (!element) return;
  
  let currentTooltip = null;
  
  element.addEventListener('mouseenter', () => {
    currentTooltip = createTooltip(element, message, {
      ...options,
      duration: 999999 // Don't auto-hide on hover
    });
  });
  
  element.addEventListener('mouseleave', () => {
    if (currentTooltip) {
      currentTooltip.remove();
      currentTooltip = null;
    }
  });
}

/**
 * Utility function to add tooltips to elements with data-tooltip attributes
 * Usage: <button data-tooltip="Click me!" data-tooltip-type="info">Button</button>
 */
function initializeDataTooltips() {
  document.querySelectorAll('[data-tooltip]').forEach(element => {
    const message = element.getAttribute('data-tooltip');
    const type = element.getAttribute('data-tooltip-type') || 'info';
    const position = element.getAttribute('data-tooltip-position') || 'top';
    
    addHoverTooltip(element, message, { type, position });
  });
}

// Auto-initialize data tooltips when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeDataTooltips);
} else {
  initializeDataTooltips();
}

// Make functions available globally
window.createTooltip = createTooltip;
window.showTooltip = showTooltip;
window.addHoverTooltip = addHoverTooltip;
window.initializeDataTooltips = initializeDataTooltips; 