AG-Grid Leaderboard System - Internal Developer Documentation
==============================================================

Overview
--------

The AG-Grid leaderboard system is a complete rewrite of Brain-Score's model comparison interface, transforming it from a static Django-rendered table into a highly interactive, client-side data exploration tool. This document covers the technical architecture, component interactions, and development patterns for engineers working on the system.

System Architecture
-------------------

High-Level Flow
~~~~~~~~~~~~~~~

.. code-block:: text

   Django Backend → Materialized Views → JSON Serialization → Progressive Loading → AG-Grid Frontend

The system follows a **split-loading architecture**:

1. **Shell View**: Delivers page structure and dependencies immediately
2. **Content View**: Streams heavy data payload via AJAX
3. **Client Processing**: All interactions happen browser-side after initial load

Backend Architecture
~~~~~~~~~~~~~~~~~~~~

View Layer (``benchmarks/views/leaderboard.py``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**ag_grid_leaderboard_shell(request, domain)**
   - Lightweight view that loads immediately
   - Returns basic page structure with AG-Grid dependencies
   - No data processing - just domain context

**ag_grid_leaderboard_content(request, domain)**
   - Heavy lifting view loaded via AJAX
   - Handles user permissions and caching strategies
   - Returns complete dataset as JSON

**get_ag_grid_context(user, domain, ...)**
   - Core data processing function (cached for 7 days)
   - Queries materialized views for model/benchmark data
   - Builds filter metadata and column definitions
   - Serializes everything to JSON for frontend consumption

Data Flow
^^^^^^^^^

1. **Materialized View Query**: Fast lookups from pre-computed database views
2. **Permission Filtering**: Apply user-specific model visibility rules
3. **Metadata Extraction**: Build filter options from model/benchmark properties
4. **JSON Serialization**: Convert all data to optimized frontend format
5. **Caching**: Store results with user-specific cache keys

Key Data Structures
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Column definitions for AG-Grid
   column_defs = [
       {'field': 'rank', 'pinned': 'left', 'width': 100},
       {'field': 'model', 'pinned': 'left', 'cellRenderer': 'modelCellRenderer'},
       # Dynamic benchmark columns with hierarchical structure
   ]

   # Row data with nested score objects
   row_data = [
       {
           'id': model_id,
           'model': {'name': '...', 'submitter': '...'},
           'benchmark_id': {'value': 0.85, 'color': 'rgba(...)'},
           # ... all benchmark scores
       }
   ]

Frontend Architecture
~~~~~~~~~~~~~~~~~~~~~

Module Organization
^^^^^^^^^^^^^^^^^^^

The frontend is organized into functional modules under ``static/benchmarks/js/leaderboard/``:

.. code-block:: text

   leaderboard/
   ├── core/                    # Foundation modules
   │   ├── constants.js         # Configuration constants
   │   ├── state-management.js  # Global state management
   │   ├── grid-initialization.js # AG-Grid setup
   │   └── template-initialization.js # Progressive loading
   ├── filters/                 # Filtering system
   │   ├── filter-coordinator.js # Orchestrates all filters
   │   ├── model-filters.js     # Model property filtering
   │   ├── benchmark-filters.js # Benchmark metadata filtering
   │   ├── range-filters.js     # Slider-based filters
   │   └── search-filters.js    # Text search with logical operators
   ├── renderers/               # Display components
   │   ├── cell-renderers.js    # Model, score, status cells
   │   └── header-components.js # Expandable column headers
   ├── navigation/              # URL and state management
   │   └── url-state.js         # Filter persistence in URLs
   ├── export/                  # Data export functionality
   │   ├── csv-export.js        # CSV generation
   │   └── citation-export.js   # BibTeX export
   └── utilities/               # Helper functions
       └── hierarchy-utils.js   # Benchmark tree operations

Core Components
^^^^^^^^^^^^^^^

**State Management** (``core/state-management.js``)

Manages global application state:

.. code-block:: javascript

   // Global grid references
   window.globalGridApi = null;

   // Filter state
   window.activeFilters = {
     architecture: [],
     model_family: [],
     training_dataset: [],
     // ... all filter dimensions
   };

   // Data state
   window.originalRowData = [];        // Immutable source data
   window.currentFilteredData = null;  // Current filtered dataset
   window.filteredOutBenchmarks = new Set(); // Hidden benchmarks

**Grid Initialization** (``core/grid-initialization.js``)

Sets up AG-Grid with Brain-Score-specific configuration:

.. code-block:: javascript

   function initializeGrid(rowData, columnDefs, benchmarkGroups) {
     const gridOptions = {
       rowData,
       columnDefs,
       components: {
         modelCellRenderer: ModelCellRenderer,
         scoreCellRenderer: ScoreCellRenderer,
         expandableHeaderComponent: ExpandableHeaderComponent,
       },
       // External filtering for search
       isExternalFilterPresent: () => window.currentSearchQuery !== null,
       doesExternalFilterPass: (node) => {
         // Custom search logic with AND/OR/NOT operators
       }
     };
   }

**Filter Coordination** (``filters/filter-coordinator.js``)

Orchestrates all filtering operations:

.. code-block:: javascript

   function applyCombinedFilters() {
     // 1. Update benchmark filters (regions, species, tasks)
     updateBenchmarkFilters();

     // 2. Apply model property filters (architecture, size, etc.)
     applyModelFilters();

     // 3. Recalculate filtered scores based on included benchmarks
     updateFilteredScores();

     // 4. Update column visibility
     updateColumnVisibility();

     // 5. Persist state to URL
     updateURLFromFilters();
   }

Rendering System
^^^^^^^^^^^^^^^^

**Cell Renderers** (``renderers/cell-renderers.js``)

ModelCellRenderer
   Displays model name with link and submitter info

   - Handles model detail page navigation
   - Shows submitter attribution
   - Manages model status indicators

ScoreCellRenderer
   Color-coded performance pills

   - Applies statistical color coding (percentile-based)
   - Handles missing data display ('X' for no score)
   - Responsive formatting for different score ranges

RunnableStatusCellRenderer
   Model functionality indicators

   - Green: Functional/runnable code
   - Red: Known issues or non-functional
   - Gray: Unknown status

**Header Components** (``renderers/header-components.js``)

ExpandableHeaderComponent
   Hierarchical benchmark navigation

   - Expand/collapse benchmark categories
   - Dynamic child column loading
   - Sort indicators with 3-state cycling (desc → asc → none)

Navigation vs. Sort Areas
   Headers are split into regions:

   - 80% click area: Navigation (expand/collapse)
   - 20% click area: Sorting functionality

Filtering System
^^^^^^^^^^^^^^^^

**Model Filters** (``filters/model-filters.js``)
   - Architecture filtering (transformer, CNN, etc.)
   - Model family grouping (ResNet, CLIP, etc.)
   - Training dataset filtering (ImageNet, etc.)
   - Parameter count and model size sliders
   - Runnable-only toggle

**Benchmark Filters** (``filters/benchmark-filters.js``)
   - Brain region filtering (V1, V4, IT, etc.)
   - Species filtering (macaque, human, etc.)
   - Task type filtering (object recognition, etc.)
   - Public data availability toggle
   - Stimuli count range filtering

**Search System** (``filters/search-filters.js``)

Supports logical operators for complex queries:

.. code-block:: javascript

   // Examples:
   "alexnet OR resnet"           // Either model type
   "transformer AND vision"      // Both terms required
   "NOT imagenet"               // Exclude ImageNet models
   "(clip OR blip) AND NOT gpt" // Complex grouping

Data Flow Patterns
^^^^^^^^^^^^^^^^^^

**Progressive Loading**

1. **Shell loads**: Page structure, AG-Grid framework, loading animation
2. **AJAX request**: Fetch complete dataset from content view
3. **Data processing**: Initialize filters, build column definitions
4. **Grid rendering**: Populate AG-Grid with data
5. **Interactive state**: Enable all filtering and exploration features

**Filtering Pipeline**

1. **User interaction**: Filter UI change (checkbox, slider, search)
2. **State update**: Update ``window.activeFilters``
3. **Data filtering**: Apply filters to ``originalRowData``
4. **Score recalculation**: Update aggregate scores based on included benchmarks
5. **Grid refresh**: Update AG-Grid display
6. **URL persistence**: Save filter state to browser URL

**Column Management**

- **Lazy loading**: Benchmark columns load on-demand as users expand categories
- **Visibility rules**: Hide columns with all missing data or zeros
- **Hierarchy respect**: Parent columns show/hide based on children state

Development Patterns
--------------------

Adding New Filters
~~~~~~~~~~~~~~~~~~

1. **Backend**: Add filter logic to ``get_ag_grid_context()`` metadata extraction
2. **Frontend State**: Add filter property to ``window.activeFilters``
3. **UI Component**: Create filter controls in appropriate template
4. **Filter Logic**: Implement filtering in ``filter-coordinator.js``
5. **URL Persistence**: Add URL parameter handling in ``url-state.js``

Custom Cell Renderers
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   function CustomCellRenderer() {}
   CustomCellRenderer.prototype.init = function(params) {
     this.eGui = document.createElement('div');
     // Custom rendering logic
   };
   CustomCellRenderer.prototype.getGui = function() {
     return this.eGui;
   };

   // Register in grid initialization
   components: {
     customCellRenderer: CustomCellRenderer
   }

Performance Considerations
~~~~~~~~~~~~~~~~~~~~~~~~~~

Backend Optimizations
^^^^^^^^^^^^^^^^^^^^^^

- **Materialized views**: Pre-compute expensive aggregations
- **Aggressive caching**: 7-day cache with user-specific keys
- **JSON serialization**: Custom serializers for numpy/pandas data
- **Split loading**: Separate shell and content views

Frontend Optimizations
^^^^^^^^^^^^^^^^^^^^^^

- **Client-side processing**: All filtering happens in-browser
- **Lazy column rendering**: Load benchmark columns on-demand
- **Efficient state management**: Minimal DOM manipulation
- **Debounced updates**: Prevent excessive filtering operations

Testing Patterns
~~~~~~~~~~~~~~~~

Backend Testing
^^^^^^^^^^^^^^^

- Test materialized view queries
- Verify caching behavior
- Test user permission filtering
- Validate JSON serialization

Frontend Testing
^^^^^^^^^^^^^^^^

- Test filter combinations
- Verify column visibility rules
- Test search query parsing
- Validate export functionality

Debugging Tips
~~~~~~~~~~~~~~

Common Issues
^^^^^^^^^^^^^

- **Missing data**: Check materialized view refresh status
- **Slow loading**: Verify caching is working properly
- **Filter conflicts**: Check ``applyCombinedFilters()`` logic
- **Column visibility**: Debug ``shouldColumnBeVisible()`` rules

Debug Tools
^^^^^^^^^^^

.. code-block:: javascript

   // Inspect current state
   console.log(window.activeFilters);
   console.log(window.filteredOutBenchmarks);
   console.log(window.globalGridApi.getDisplayedRowCount());

   // Force filter refresh
   applyCombinedFilters();

   // Check grid state
   window.globalGridApi.getColumnDefs();
   window.globalGridApi.getFilterModel();

Future Architecture Considerations
----------------------------------

Scalability
~~~~~~~~~~~

- Consider virtual scrolling for 1000+ models
- Implement progressive data loading for large benchmark sets
- Add client-side caching for filter metadata

Feature Extensions
~~~~~~~~~~~~~~~~~~

- Real-time collaboration features
- Advanced statistical analysis integration
- Custom visualization components
- Enhanced export formats (Excel, JSON, etc.)

Performance Monitoring
~~~~~~~~~~~~~~~~~~~~~~

- Add client-side performance metrics
- Monitor filter operation timing
- Track data payload sizes
- Measure initial load performance

This architecture provides a solid foundation for continued development while maintaining the interactive, exploratory experience that makes the leaderboard a powerful scientific tool.