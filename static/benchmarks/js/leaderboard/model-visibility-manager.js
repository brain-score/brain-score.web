/**
 * Model Visibility Manager
 * Handles individual model visibility toggling in profile views
 */
const ModelVisibilityManager = {
    
    /**
     * Initialize model visibility management
     */
    initialize: function() {
        if (!window.DJANGO_DATA || !window.DJANGO_DATA.row_data) {
            console.warn('ModelVisibilityManager: No row data available');
            return;
        }
        
        this.parseRowData();
        this.renderUserModels();
        this.bindEvents();
    },
    
    /**
     * Parse row data to extract user models
     */
    parseRowData: function() {
        try {
            this.rowData = JSON.parse(window.DJANGO_DATA.row_data);
            this.userModels = [];
            this.originalVisibility = {};
            
            // Extract all models in profile view
            this.rowData.forEach(row => {
                if (row.model && row.id) {
                    // In profile view, show all models - the backend will verify ownership
                    this.userModels.push({
                        id: row.id, // Use row.id as the model ID for the database
                        name: row.model.name,
                        public: row.public !== undefined ? row.public : false,
                        submitter: row.model.submitter || 'Unknown'
                    });
                    // Store original visibility state
                    this.originalVisibility[row.id] = row.public !== undefined ? row.public : false;
                }
            });
            
            console.log(`Found ${this.userModels.length} user models`);
            if (this.userModels.length === 0) {
                console.log('No user models found. Sample row data:', this.rowData.slice(0, 2));
                console.log('Available DJANGO_DATA keys:', Object.keys(window.DJANGO_DATA || {}));
            }
        } catch (error) {
            console.error('Error parsing row data:', error);
            this.userModels = [];
        }
    },
    
    /**
     * Render user models with checkboxes
     */
    renderUserModels: function() {
        const container = document.getElementById('userModelsList');
        if (!container) return;
        
        if (this.userModels.length === 0) {
            container.innerHTML = '<p class="no-models">No models found for your account.</p>';
            return;
        }
        
        let html = '<div class="models-grid">';
        
        this.userModels.forEach(model => {
            const isChecked = model.public ? 'checked' : '';
            const statusClass = model.public ? 'public' : 'private';
            const statusText = model.public ? 'Public' : 'Private';
            
            html += `
                <div class="model-item" data-model-id="${model.id}">
                    <div class="model-info">
                        <div class="model-name">${this.escapeHtml(model.name)}</div>
                        <div class="model-submitter">by ${this.escapeHtml(model.submitter)}</div>
                        <div class="model-status status-${statusClass}">${statusText}</div>
                    </div>
                    <div class="model-controls">
                        <label class="checkbox-container">
                            <input type="checkbox" 
                                   class="model-visibility-checkbox" 
                                   data-model-id="${model.id}" 
                                   ${isChecked}>
                            <span class="checkmark"></span>
                            <span class="checkbox-label">Make Public</span>
                        </label>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    },
    
    /**
     * Bind event handlers
     */
    bindEvents: function() {
        // Handle checkbox changes
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('model-visibility-checkbox')) {
                this.handleCheckboxChange(e.target);
            }
        });
        
        // Handle apply button
        const applyButton = document.getElementById('applyVisibilityChanges');
        if (applyButton) {
            applyButton.addEventListener('click', () => {
                this.applyChanges();
            });
        }
    },
    
    /**
     * Handle individual checkbox change
     */
    handleCheckboxChange: function(checkbox) {
        const modelId = parseInt(checkbox.dataset.modelId);
        const isChecked = checkbox.checked;
        
        // Update model status display
        const modelItem = checkbox.closest('.model-item');
        const statusElement = modelItem.querySelector('.model-status');
        
        if (isChecked) {
            statusElement.textContent = 'Public (pending)';
            statusElement.className = 'model-status status-pending';
        } else {
            statusElement.textContent = 'Private';
            statusElement.className = 'model-status status-private';
        }
        
        // Check if any changes were made
        this.updateApplyButton();
    },
    
    /**
     * Update apply button state based on changes
     */
    updateApplyButton: function() {
        const applyButton = document.getElementById('applyVisibilityChanges');
        if (!applyButton) return;
        
        const hasChanges = this.getChangedModels().length > 0;
        applyButton.disabled = !hasChanges;
        
        if (hasChanges) {
            const changeCount = this.getChangedModels().length;
            applyButton.textContent = `Apply Changes (${changeCount})`;
        } else {
            applyButton.textContent = 'Apply Changes';
        }
    },
    
    /**
     * Get list of models with changed visibility
     */
    getChangedModels: function() {
        const changes = [];
        const checkboxes = document.querySelectorAll('.model-visibility-checkbox');
        
        checkboxes.forEach(checkbox => {
            const modelId = parseInt(checkbox.dataset.modelId);
            const currentState = checkbox.checked;
            const originalState = this.originalVisibility[modelId];
            
            if (currentState !== originalState) {
                changes.push({
                    id: modelId,
                    public: currentState,
                    originalState: originalState
                });
            }
        });
        
        return changes;
    },
    
    /**
     * Apply visibility changes via AJAX
     */
    applyChanges: function() {
        const changes = this.getChangedModels();
        if (changes.length === 0) return;
        
        this.showStatus('Processing changes...', 'info');
        this.setApplyButtonLoading(true);
        
        // Process changes sequentially to avoid overwhelming the server
        this.processChangesSequentially(changes, 0);
    },
    
    /**
     * Process changes one by one
     */
    processChangesSequentially: function(changes, index) {
        if (index >= changes.length) {
            // All changes processed
            this.showStatus(`Successfully updated ${changes.length} model(s)`, 'success');
            this.setApplyButtonLoading(false);
            this.updateOriginalVisibility(changes);
            this.updateApplyButton();
            return;
        }
        
        const change = changes[index];
        this.sendVisibilityChange(change)
            .then(() => {
                // Process next change
                this.processChangesSequentially(changes, index + 1);
            })
            .catch(error => {
                console.error('Error updating model visibility:', error);
                this.showStatus(`Error updating model visibility: ${error.message}`, 'error');
                this.setApplyButtonLoading(false);
            });
    },
    
    /**
     * Send individual visibility change to server
     */
    sendVisibilityChange: function(change) {
        return new Promise((resolve, reject) => {
            const payload = JSON.stringify({
                id: change.id,
                public: change.public
            });
            
            fetch('../public-ajax/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: payload
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data === "success" || (data && data.status === "success")) {
                    resolve(data);
                } else {
                    reject(new Error('Server returned error'));
                }
            })
            .catch(error => {
                reject(error);
            });
        });
    },
    
    /**
     * Update original visibility state after successful changes
     */
    updateOriginalVisibility: function(changes) {
        changes.forEach(change => {
            this.originalVisibility[change.id] = change.public;
            
            // Update the model status display
            const modelItem = document.querySelector(`[data-model-id="${change.id}"]`);
            if (modelItem) {
                const statusElement = modelItem.querySelector('.model-status');
                if (change.public) {
                    statusElement.textContent = 'Public';
                    statusElement.className = 'model-status status-public';
                } else {
                    statusElement.textContent = 'Private';
                    statusElement.className = 'model-status status-private';
                }
            }
        });
    },
    
    /**
     * Show status message
     */
    showStatus: function(message, type = 'info') {
        const statusDiv = document.getElementById('visibilityStatus');
        const messageSpan = statusDiv.querySelector('.status-message');
        
        if (statusDiv && messageSpan) {
            messageSpan.textContent = message;
            statusDiv.className = `visibility-status status-${type}`;
            statusDiv.style.display = 'block';
            
            // Auto-hide success messages after 5 seconds
            if (type === 'success') {
                setTimeout(() => {
                    statusDiv.style.display = 'none';
                }, 5000);
            }
        }
    },
    
    /**
     * Set apply button loading state
     */
    setApplyButtonLoading: function(loading) {
        const applyButton = document.getElementById('applyVisibilityChanges');
        if (!applyButton) return;
        
        if (loading) {
            applyButton.disabled = true;
            applyButton.textContent = 'Processing...';
        } else {
            applyButton.disabled = false;
        }
    },
    
    /**
     * Get CSRF token from cookie
     */
    getCsrfToken: function() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml: function(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize when the template loads
console.log('ModelVisibilityManager script loaded');

// Try multiple initialization strategies
function tryInitialize() {
    console.log('Trying to initialize ModelVisibilityManager...');
    console.log('modelVisibilitySection exists:', !!document.getElementById('modelVisibilitySection'));
    console.log('DJANGO_DATA exists:', !!window.DJANGO_DATA);
    console.log('row_data exists:', !!(window.DJANGO_DATA && window.DJANGO_DATA.row_data));
    
    if (document.getElementById('modelVisibilitySection')) {
        console.log('Found modelVisibilitySection, initializing...');
        ModelVisibilityManager.initialize();
        return true;
    }
    return false;
}

// Try immediately
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryInitialize);
} else {
    tryInitialize();
}

// Also try after a delay in case the content is loaded dynamically
setTimeout(function() {
    if (!tryInitialize()) {
        console.log('Still waiting for modelVisibilitySection...');
        setTimeout(tryInitialize, 1000);
    }
}, 500);
