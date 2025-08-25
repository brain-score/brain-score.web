// Report Issue functionality for leaderboard

// Setup report issue functionality
function setupReportIssue() {
  const reportButton = document.getElementById('reportIssueText');
  const modal = document.getElementById('reportIssueModal');
  const closeButton = document.getElementById('closeReportModal');
  const cancelButton = document.getElementById('cancelReportModal');
  const form = document.getElementById('reportIssueForm');
  const systemInfoField = document.getElementById('systemInfo');
  
  if (!reportButton || !modal || !form) {
    console.warn('Report issue elements not found');
    return;
  }
  
  // Populate system info
  populateSystemInfo();
  
  // Event listeners
  reportButton.addEventListener('click', openReportModal);
  closeButton?.addEventListener('click', closeReportModal);
  cancelButton?.addEventListener('click', closeReportModal);
  form.addEventListener('submit', handleReportSubmission);
  
  // Close modal when clicking outside
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeReportModal();
    }
  });
}

// Open the report issue modal
function openReportModal() {
  const modal = document.getElementById('reportIssueModal');
  if (modal) {
    modal.style.display = 'flex';
    document.body.classList.add('modal-open');
    
    // Focus on the first input
    const firstInput = modal.querySelector('select, input, textarea');
    if (firstInput) {
      setTimeout(() => firstInput.focus(), 100);
    }
  }
}

// Close the report issue modal
function closeReportModal() {
  const modal = document.getElementById('reportIssueModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.classList.remove('modal-open');
    
    // Reset form
    const form = document.getElementById('reportIssueForm');
    if (form) {
      form.reset();
      populateSystemInfo(); // Repopulate system info after reset
    }
  }
}

// Handle form submission
async function handleReportSubmission(event) {
  event.preventDefault();
  
  const submitBtn = document.getElementById('submitIssueBtn');
  const originalBtnContent = submitBtn.innerHTML;
  
  try {
    // Show loading state
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="icon"><i class="fa-solid fa-spinner fa-spin"></i></span><span>Submitting...</span>';
    
    // Collect form data
    const formData = collectFormData();
    
    // Validate required fields
    if (!validateFormData(formData)) {
      throw new Error('Please fill in all required fields');
    }
    
    // Submit to backend
    const response = await submitIssueToBackend(formData);
    
    if (response.success) {
      showSuccessMessage(response.issue_url || 'Issue submitted successfully!');
      closeReportModal();
    } else {
      throw new Error(response.error || 'Failed to submit issue');
    }
    
  } catch (error) {
    console.error('Error submitting issue:', error);
    showErrorMessage(error.message || 'Failed to submit issue. Please try again.');
  } finally {
    // Reset button state
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnContent;
  }
}

// Collect form data
function collectFormData() {
  return {
    issue_type: document.getElementById('issueType').value,
    title: document.getElementById('issueTitle').value.trim(),
    description: document.getElementById('issueDescription').value.trim(),
    system_info: document.getElementById('systemInfo').value,
    contact_email: document.getElementById('contactEmail').value.trim(),
    page_url: window.location.href,
    user_agent: navigator.userAgent,
    timestamp: new Date().toISOString(),
    // Include current filter state for context
    filter_state: getCurrentFilterState()
  };
}

// Validate form data
function validateFormData(data) {
  if (!data.issue_type) {
    showFieldError('issueType', 'Please select an issue type');
    return false;
  }
  
  if (!data.title || data.title.length < 10) {
    showFieldError('issueTitle', 'Please provide a descriptive title (at least 10 characters)');
    return false;
  }
  
  if (!data.description || data.description.length < 20) {
    showFieldError('issueDescription', 'Please provide a detailed description (at least 20 characters)');
    return false;
  }
  
  return true;
}

// Show field-specific error
function showFieldError(fieldId, message) {
  const field = document.getElementById(fieldId);
  if (field) {
    field.classList.add('is-danger');
    
    // Remove existing error message
    const existingError = field.parentNode.querySelector('.help.is-danger');
    if (existingError) {
      existingError.remove();
    }
    
    // Add error message
    const errorElement = document.createElement('p');
    errorElement.className = 'help is-danger';
    errorElement.textContent = message;
    field.parentNode.appendChild(errorElement);
    
    // Remove error styling after user starts typing
    field.addEventListener('input', function clearError() {
      field.classList.remove('is-danger');
      const errorMsg = field.parentNode.querySelector('.help.is-danger');
      if (errorMsg) {
        errorMsg.remove();
      }
      field.removeEventListener('input', clearError);
    }, { once: true });
  }
}

// Submit issue to backend
async function submitIssueToBackend(formData) {
  try {
    const response = await fetch('/report-issue/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify(formData)
    });
    
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Backend submission error:', error);
    throw error;
  }
}

// Get CSRF token
function getCsrfToken() {
  const token = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                document.querySelector('meta[name=csrf-token]')?.getAttribute('content') ||
                getCsrfFromCookie();
  
  if (!token) {
    console.warn('CSRF token not found');
  }
  
  return token || '';
}

// Get CSRF token from cookie (Django default)
function getCsrfFromCookie() {
  const name = 'csrftoken';
  const cookies = document.cookie.split(';');
  
  for (let cookie of cookies) {
    const [key, value] = cookie.trim().split('=');
    if (key === name) {
      return decodeURIComponent(value);
    }
  }
  
  return null;
}

// Get current filter state for context
function getCurrentFilterState() {
  try {
    const activeFilters = window.activeFilters || {};
    const searchTerm = document.getElementById('modelSearchInput')?.value || '';
    
    return {
      search_term: searchTerm,
      active_filters: activeFilters,
      visible_rows: window.globalGridApi ? getVisibleRowCount() : 'unknown'
    };
  } catch (error) {
    console.warn('Could not collect filter state:', error);
    return { error: 'Could not collect filter state' };
  }
}

// Get count of visible rows in grid
function getVisibleRowCount() {
  if (!window.globalGridApi) return 'unknown';
  
  let count = 0;
  window.globalGridApi.forEachNodeAfterFilterAndSort(() => count++);
  return count;
}

// Populate system information
function populateSystemInfo() {
  const systemInfoField = document.getElementById('systemInfo');
  if (!systemInfoField) return;
  
  const info = [
    `Browser: ${navigator.userAgent}`,
    `Screen: ${screen.width}x${screen.height}`,
    `Viewport: ${window.innerWidth}x${window.innerHeight}`,
    `Platform: ${navigator.platform}`,
    `Language: ${navigator.language}`,
    `Timestamp: ${new Date().toISOString()}`
  ].join(' | ');
  
  systemInfoField.value = info;
}

// Show success message
function showSuccessMessage(message) {
  // Create success notification
  const notification = document.createElement('div');
  notification.className = 'notification is-success is-light';
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    max-width: 400px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  `;
  
  notification.innerHTML = `
    <button class="delete"></button>
    <strong>Success!</strong><br>
    ${typeof message === 'string' && message.startsWith('http') ? 
      `<a href="${message}" target="_blank" class="has-text-link">View issue on GitHub</a>` : 
      message}
  `;
  
  document.body.appendChild(notification);
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  }, 5000);
  
  // Manual close
  const deleteBtn = notification.querySelector('.delete');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    });
  }
}

// Show error message
function showErrorMessage(message) {
  // Create error notification
  const notification = document.createElement('div');
  notification.className = 'notification is-danger is-light';
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    max-width: 400px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  `;
  
  notification.innerHTML = `
    <button class="delete"></button>
    <strong>Error!</strong><br>
    ${message}
  `;
  
  document.body.appendChild(notification);
  
  // Auto-remove after 8 seconds (longer for errors)
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification);
    }
  }, 8000);
  
  // Manual close
  const deleteBtn = notification.querySelector('.delete');
  if (deleteBtn) {
    deleteBtn.addEventListener('click', () => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    });
  }
}



// Export functions for use by other modules
window.LeaderboardReportIssue = {
  setupReportIssue,
  openReportModal,
  closeReportModal,
  handleReportSubmission,
  collectFormData,
  validateFormData,
  submitIssueToBackend,
  showSuccessMessage,
  showErrorMessage
};
