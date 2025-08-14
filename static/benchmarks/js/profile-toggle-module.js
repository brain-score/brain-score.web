/**
 * Profile Toggle Module
 * Handles switching between user-only and user+public model views in profile pages
 */
const ProfileToggleModule = {
    
    /**
     * Initialize profile page progressive loading
     * @param {string} domain - The domain (vision/language)
     */
    initializeProfilePage: function(domain) {
        document.addEventListener('DOMContentLoaded', () => {
            this.showLoadingIndicator('Loading your models...');
            this.loadInitialContent(domain);
        });
    },
    
    /**
     * Initialize toggle functionality for profile content
     */
    initializeToggle: function() {
        const btn = document.getElementById('includePublicToggleBtn');
        if (!btn) return;
        
        btn.addEventListener('click', (event) => {
            this.handleToggleClick(event.target);
        });
    },
    
    /**
     * Load initial profile content
     * @param {string} domain - The domain (vision/language)
     */
    loadInitialContent: function(domain) {
        const currentUrl = new URL(window.location);
        const contentUrl = new URL(`/${domain}/leaderboard/content/`, currentUrl.origin);
        contentUrl.searchParams.set('user_view', 'true');
        
        // Check if include_public parameter is set in current URL
        const includePublic = currentUrl.searchParams.get('include_public');
        if (includePublic) {
            contentUrl.searchParams.set('include_public', includePublic);
        }
        
        this.loadContent(contentUrl.toString());
    },
    
    /**
     * Handle toggle button click
     * @param {HTMLElement} toggleBtn - The toggle button element
     */
    handleToggleClick: function(toggleBtn) {
        const isOn = toggleBtn.getAttribute('aria-pressed') === 'true';
        const nextOn = !isOn;
        
        // Show loading indicator
        const loadingMessage = nextOn ? 'Loading all models...' : 'Loading your models...';
        this.showLoadingIndicator(loadingMessage);
        
        // Build URL with parameters
        const domain = this.extractDomain();
        const contentUrl = this.buildContentUrl(domain, nextOn);
        
        // Load new content and update URL
        this.loadContent(contentUrl)
            .then(() => {
                this.updateBrowserUrl(nextOn);
            });
    },
    
    /**
     * Extract domain from template context or URL
     * @returns {string} The domain (vision/language)
     */
    extractDomain: function() {
        // Try to get domain from Django template context first
        const templateDomain = window.DJANGO_DOMAIN || null;
        if (templateDomain && templateDomain !== 'vision' && templateDomain !== 'language') {
            return templateDomain;
        }
        
        // Extract from URL as fallback
        const currentUrl = new URL(window.location);
        const domainMatch = currentUrl.pathname.match(/\/profile\/([^\/]+)\//);
        return domainMatch ? domainMatch[1] : 'vision';
    },
    
    /**
     * Build content URL with appropriate parameters
     * @param {string} domain - The domain
     * @param {boolean} includePublic - Whether to include public models
     * @returns {string} The content URL
     */
    buildContentUrl: function(domain, includePublic) {
        const currentUrl = new URL(window.location);
        const contentUrl = new URL(`/${domain}/leaderboard/content/`, currentUrl.origin);
        contentUrl.searchParams.set('user_view', 'true');
        
        if (includePublic) {
            contentUrl.searchParams.set('include_public', 'true');
        }
        
        return contentUrl.toString();
    },
    
    /**
     * Load content via AJAX
     * @param {string} url - The URL to load
     * @returns {Promise} Promise that resolves when content is loaded
     */
    loadContent: function(url) {
        return fetch(url)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.text();
            })
            .then(html => {
                this.injectContent(html);
                this.initializeLoadedContent();
            })
            .catch(error => {
                console.error('Error loading content:', error);
                this.showErrorMessage();
            });
    },
    
    /**
     * Inject HTML content into the container
     * @param {string} html - The HTML content
     */
    injectContent: function(html) {
        const container = document.querySelector('.leaderboard-container');
        if (container) {
            container.innerHTML = html;
            
            // Execute scripts in the loaded content
            const scripts = container.querySelectorAll('script');
            scripts.forEach(script => {
                const newScript = document.createElement('script');
                if (script.src) {
                    newScript.src = script.src;
                } else {
                    newScript.textContent = script.textContent;
                }
                document.head.appendChild(newScript);
            });
        }
    },
    
    /**
     * Initialize leaderboard after content is loaded
     */
    initializeLoadedContent: function() {
        setTimeout(() => {
            // Initialize leaderboard (this will reset all filters to defaults)
            if (typeof initializeLeaderboardFromTemplate === 'function') {
                initializeLeaderboardFromTemplate();
                
                // Reset filters after initialization
                setTimeout(() => {
                    this.resetAllFilters();
                }, 100);
            }
        }, 200);
    },
    
    /**
     * Reset all filters to default state
     */
    resetAllFilters: function() {
        // Reset any additional filter states that might persist
        if (typeof resetAllFilters === 'function') {
            resetAllFilters();
        }
        
        // Clear search input
        const searchInput = document.getElementById('modelSearchInput');
        if (searchInput) {
            searchInput.value = '';
        }
        
        // Reset dropdown filters
        const architectureFilter = document.querySelector('#architectureFilter .filter-input');
        const modelFamilyFilter = document.querySelector('#modelFamilyFilter .filter-input');
        if (architectureFilter) architectureFilter.value = '';
        if (modelFamilyFilter) modelFamilyFilter.value = '';
        
        // Ensure benchmark filters are reset to defaults
        const benchmarkCheckboxes = document.querySelectorAll('#benchmarkFilterPanel input[type="checkbox"]');
        benchmarkCheckboxes.forEach(cb => {
            cb.checked = true; // Default state is all benchmarks included
        });
        
        // Reset public data filter
        const publicDataFilter = document.getElementById('publicDataFilter');
        if (publicDataFilter) {
            publicDataFilter.checked = false;
        }
        
        // Update filter count badges
        if (typeof window.updateAllCountBadges === 'function') {
            window.updateAllCountBadges();
        }
    },
    
    /**
     * Update browser URL without reloading
     * @param {boolean} includePublic - Whether public models are included
     */
    updateBrowserUrl: function(includePublic) {
        const newUrl = new URL(window.location);
        
        // Clear all existing search parameters
        newUrl.search = '';
        
        // Only add the include_public parameter if needed
        if (includePublic) {
            newUrl.searchParams.set('include_public', 'true');
        }
        
        window.history.pushState({}, '', newUrl.toString());
    },
    
    /**
     * Show loading indicator
     * @param {string} message - Loading message to display
     */
    showLoadingIndicator: function(message) {
        const container = document.querySelector('.leaderboard-container');
        if (container) {
            container.innerHTML = `
                <div style="text-align: center; padding: 60px; color: #666;">
                    <div style="margin-bottom: 20px;">
                        <div style="width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #47B7DE; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                    </div>
                    <p>${message}</p>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            `;
        }
    },
    
    /**
     * Show error message
     */
    showErrorMessage: function() {
        const container = document.querySelector('.leaderboard-container');
        if (container) {
            container.innerHTML = '<div style="text-align: center; color: #e74c3c; padding: 40px;"><h3>Error loading models</h3><p>Please refresh the page to try again.</p></div>';
        }
    }
};

// Export for global access
window.ProfileToggleModule = ProfileToggleModule;
