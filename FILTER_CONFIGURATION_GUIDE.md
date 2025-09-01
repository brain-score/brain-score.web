# 🔧 Filter Configuration System Guide

## Overview

The Filter Configuration System allows users to control which advanced filters are visible in the leaderboard interface. This guide explains how to add new filters, configure defaults, and customize the system.

## Architecture

The system consists of 4 main components:

1. **`filter-config-state.js`** - Central registry and state management
2. **`filter-config-modal.js`** - User interface for configuration
3. **`filter-config-renderer.js`** - DOM manipulation for showing/hiding filters
4. **`filter-config-test.js`** - Debugging and testing utilities

## Adding a New Filter

### Step 1: Add to FILTER_REGISTRY

Edit `/static/benchmarks/js/leaderboard/filters/filter-config-state.js` and add your filter to the `FILTER_REGISTRY` object:

```javascript
const FILTER_REGISTRY = {
  // ... existing filters ...
  
  'your_filter_id': {
    id: 'your_filter_id',                    // Unique identifier
    category: 'model_properties',            // See categories below
    label: 'Your Filter Name',               // Display name in modal
    description: 'What this filter does',    // Help text for users
    type: 'dropdown',                        // See filter types below
    elementId: 'yourFilterElement',          // DOM element ID
    containerSelector: '.filter-group',      // Parent container selector
    defaultVisible: true,                    // Show by default?
    required: false                          // Always visible? (can't be hidden)
  }
};
```

### Step 2: Verify DOM Structure

Ensure your filter's HTML structure exists in the template:
```html
<div class="filter-group">
  <label>Your Filter Name</label>
  <div id="yourFilterElement">
    <!-- Your filter content -->
  </div>
</div>
```

### Step 3: Test the Integration

1. Refresh the page
2. Open the configuration modal (gear icon ⚙️)
3. Your filter should appear in the appropriate category
4. Test hiding/showing it

## Configuration Options

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (use lowercase with underscores) |
| `category` | string | Groups filters in the modal (see categories below) |
| `label` | string | User-friendly name displayed in the modal |
| `description` | string | Help text explaining what the filter does |
| `type` | string | Visual indicator type (see types below) |
| `elementId` | string | ID of the main DOM element for this filter |
| `containerSelector` | string | CSS selector for the parent container |
| `defaultVisible` | boolean | Whether filter is visible by default |
| `required` | boolean | Whether filter can be hidden by users |

### Categories

Filters are grouped into these categories in the modal:

- **`benchmarks`** - 📊 Benchmark Filters (e.g., benchmark selection tree)
- **`model_properties`** - 🤖 Model Properties (e.g., architecture, parameters)  
- **`benchmark_properties`** - 🧠 Benchmark Properties (e.g., brain region, species)

### Filter Types

Types affect the icon shown in the modal:

- **`tree`** - 🌳 Tree selector
- **`dropdown`** - 📋 Dropdown menu
- **`range_slider`** - 📏 Range/slider input
- **`checkbox`** - ☑️ Single checkbox
- **`checkbox_group`** - ✅ Multiple checkboxes
- **`text`** - 📝 Text input
- **`other`** - ⚙️ Generic filter

### Default Visibility Options

```javascript
// Always visible by default, can be hidden
defaultVisible: true,
required: false

// Hidden by default, can be shown
defaultVisible: false,
required: false

// Always visible, cannot be hidden (core filters)
defaultVisible: true,
required: true

// Hidden by default, cannot be shown (disabled filters)
defaultVisible: false,
required: true  // (rare case)
```

## Example: Adding a New Filter

Let's add a "Training Dataset" filter:

```javascript
'training_dataset': {
  id: 'training_dataset',
  category: 'model_properties',
  label: 'Training Dataset',
  description: 'Filter by the dataset used to train the model',
  type: 'checkbox_group',
  elementId: 'trainingDatasetFilter',
  containerSelector: '.filter-group',
  defaultVisible: false,  // Hidden by default
  required: false         // Users can show/hide it
}
```

Corresponding HTML in the template:
```html
<div class="filter-group">
  <label>Training Dataset</label>
  <div class="filter-dropdown" id="trainingDatasetFilter">
    <div class="checkbox-group">
      <label><input type="checkbox" value="imagenet"> ImageNet</label>
      <label><input type="checkbox" value="cifar10"> CIFAR-10</label>
      <!-- ... more options ... -->
    </div>
  </div>
</div>
```

## Advanced Configuration

### Container Selectors

The `containerSelector` determines what gets hidden/shown. Common patterns:

```javascript
// Hide the entire filter group
containerSelector: '.filter-group'

// Hide a specific column
containerSelector: '.benchmark-column'

// Hide just the filter element (not recommended)
containerSelector: '#yourFilterElement'

// Hide a custom wrapper
containerSelector: '.custom-filter-wrapper'
```

### Dynamic Filters

For filters added dynamically via JavaScript:

```javascript
// Add to registry after DOM is ready
if (window.FILTER_REGISTRY) {
  window.FILTER_REGISTRY.dynamic_filter = {
    id: 'dynamic_filter',
    // ... other properties
  };
  
  // Reinitialize if needed
  if (window.filterRenderer) {
    window.filterRenderer.mapFilterElements();
  }
}
```

## Testing Your Filter

### Manual Testing

1. **Add the filter** to `FILTER_REGISTRY`
2. **Refresh the page** and open Advanced Filters
3. **Open configuration modal** (gear icon ⚙️)
4. **Find your filter** in the appropriate category
5. **Toggle it off** - does the filter disappear?
6. **Toggle it back on** - does it reappear?
7. **Apply configuration** - are changes persisted?
8. **Refresh the page** - is your preference remembered?

### Console Testing

```javascript
// Check if filter is registered
console.log(FILTER_REGISTRY.your_filter_id);

// Check visibility state
console.log(window.filterVisibilityConfig.isVisible('your_filter_id'));

// Toggle programmatically
window.filterVisibilityConfig.toggle('your_filter_id');

// Force rendering update
window.filterRenderer.applyFilterVisibility();
```

### Debugging

Enable debug mode in console:
```javascript
// Show current state
window.filterDebug.showCurrentState();

// Test specific filter
window.filterDebug.testActualFilter('your_filter_id');

// Reset to defaults
window.filterDebug.resetToDefaults();
```

## Best Practices

### 1. Naming Conventions
- Use `snake_case` for IDs
- Keep labels concise but descriptive
- Write helpful descriptions

### 2. Default Visibility
- Set `defaultVisible: true` for commonly used filters
- Set `defaultVisible: false` for specialized/advanced filters
- Only use `required: true` for absolutely essential filters

### 3. DOM Structure
- Ensure consistent HTML structure
- Use semantic class names
- Test with different screen sizes

### 4. Performance
- Don't add too many filters to avoid modal clutter
- Group related filters in the same category
- Consider lazy loading for complex filters

## Troubleshooting

### Filter Not Appearing in Modal
- Check that `FILTER_REGISTRY` includes your filter
- Verify the `category` is valid
- Look for JavaScript errors in console

### Filter Not Hiding/Showing
- Verify `elementId` matches actual DOM element
- Check `containerSelector` targets the right element
- Ensure element exists when filter renderer initializes

### State Not Persisting
- Check browser localStorage for 'leaderboard_filter_visibility'
- Verify no JavaScript errors during save/load
- Test in incognito mode to rule out corrupted localStorage

### Visual Issues
- Check CSS conflicts with existing styles
- Test responsive behavior
- Verify icons display correctly for filter type

## Migration Guide

### From v1 to v2 (if applicable)
- Update `FILTER_REGISTRY` format
- Add required `category` field
- Update any custom container selectors

## Support

For questions or issues:
1. Check the browser console for errors
2. Use the debugging utilities in `filter-config-test.js`
3. Review the existing filter implementations as examples
4. Test incrementally (add one filter at a time)


