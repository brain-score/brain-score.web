// Model property filtering functionality for leaderboard

// Populate filter dropdowns with available options
function populateFilterDropdowns(filterOptions) {
  populateDropdown('architectureFilter', filterOptions.architectures || []);
  populateDropdown('modelFamilyFilter', filterOptions.model_families || []);
  populateDropdown('trainingDatasetFilter', filterOptions.training_datasets || []);
  populateDropdown('taskSpecFilter', filterOptions.task_specializations || []);
}

// Generic function to populate a dropdown with options
function populateDropdown(filterId, options) {
  const filter = document.getElementById(filterId);
  if (!filter) return;
  
  const dropdown = filter.querySelector('.dropdown-content');
  if (!dropdown) return;
  
  dropdown.innerHTML = '';
  
  options.forEach(option => {
    const optionElement = document.createElement('div');
    optionElement.className = 'dropdown-option';
    optionElement.textContent = option;
    optionElement.addEventListener('click', () => {
      selectFilterOption(getFilterTypeFromId(filterId), option, optionElement);
    });
    dropdown.appendChild(optionElement);
  });
}

// Handle filter option selection
function selectFilterOption(filterType, value, optionElement) {
  const dropdown = optionElement.closest('.filter-dropdown');
  const input = dropdown.querySelector('.filter-input');

  // Toggle selection
  optionElement.classList.toggle('selected');

  // Initialize filter array if needed
  if (!window.activeFilters[filterType]) {
    window.activeFilters[filterType] = [];
  }

  // Update filter state
  if (optionElement.classList.contains('selected')) {
    // Add to array if not already present
    if (!window.activeFilters[filterType].includes(value)) {
      window.activeFilters[filterType].push(value);
    }
  } else {
    // Remove from array
    window.activeFilters[filterType] = window.activeFilters[filterType].filter(v => v !== value);
  }

  // Update input display to show selected values
  if (window.activeFilters[filterType].length > 0) {
    input.value = window.activeFilters[filterType].join(', ');
  } else {
    input.value = '';
  }

  // Don't hide dropdown on selection
  // Apply filters immediately - skip benchmark filters for model properties
  if (typeof window.applyCombinedFilters === 'function') {
    window.applyCombinedFilters(false, false, true);
  }
}

// Get filter type from element ID
function getFilterTypeFromId(filterId) {
  const mapping = {
    'architectureFilter': 'architecture',
    'modelFamilyFilter': 'model_family',
    'trainingDatasetFilter': 'training_dataset',
    'taskSpecFilter': 'task_specialization'
  };
  return mapping[filterId];
}

// Setup dropdown interaction handlers
function setupDropdownHandlers() {
  const dropdowns = document.querySelectorAll('.filter-dropdown .filter-input');
  
  dropdowns.forEach(input => {
    const originalPlaceholder = input.placeholder;

    input.addEventListener('click', (e) => {
      e.stopPropagation();
      const dropdown = e.target.closest('.filter-dropdown');
      const content = dropdown.querySelector('.dropdown-content');

      // Close other dropdowns
      document.querySelectorAll('.filter-dropdown').forEach(other => {
        if (other !== dropdown) {
          other.classList.remove('active');
          other.querySelector('.dropdown-content').classList.add('hidden');
        }
      });

      dropdown.classList.add('active');
      content.classList.remove('hidden');
    });

    input.addEventListener('input', (e) => {
      const searchTerm = e.target.value.toLowerCase();
      const dropdown = e.target.closest('.filter-dropdown');
      const content = dropdown.querySelector('.dropdown-content');
      const options = content.querySelectorAll('.dropdown-option');
      
      options.forEach(option => {
        const text = option.textContent.toLowerCase();
        if (text.includes(searchTerm)) {
          option.style.display = 'block';
        } else {
          option.style.display = 'none';
        }
      });
      
      content.classList.remove('hidden');
    });

    input.addEventListener('blur', (e) => {
      setTimeout(() => {
        const dropdown = e.target.closest('.filter-dropdown');
        if (!dropdown.classList.contains('active')) {
          if (!e.target.value) {
            e.target.placeholder = originalPlaceholder;
          }
        }
      }, 200);
    });
  });

  // Prevent dropdown from closing when clicking inside
  document.querySelectorAll('.leaderboard-container .dropdown-content').forEach(content => {
    content.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  });

  // Close dropdowns when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.leaderboard-container .filter-dropdown')) {
      document.querySelectorAll('.leaderboard-container .filter-dropdown').forEach(dropdown => {
        dropdown.classList.remove('active');
        const content = dropdown.querySelector('.dropdown-content');
        content.classList.add('hidden');

        const input = dropdown.querySelector('.filter-input');
        // Don't clear value for multi-select
        if (!input.value && window.activeFilters) {
          const filterType = dropdown.id.replace('Filter', '')
            .replace(/([A-Z])/g, '_$1').toLowerCase().substring(1);
          if (window.activeFilters[filterType] && window.activeFilters[filterType].length > 0) {
            input.value = window.activeFilters[filterType].join(', ');
          }
        }

        if (!input.value) {
          input.placeholder = input.getAttribute('placeholder') || 'Select...';
        }
      });
    }
  });
}

// Export functions for use by other modules
window.LeaderboardModelFilters = {
  populateFilterDropdowns,
  setupDropdownHandlers,
  selectFilterOption,
  getFilterTypeFromId
};

// Make functions globally available for compatibility
window.populateFilterDropdowns = populateFilterDropdowns;
window.setupDropdownHandlers = setupDropdownHandlers;