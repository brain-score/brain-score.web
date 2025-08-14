/**
 * Progressive Loader for Leaderboard
 * Handles loading the heavy leaderboard content via AJAX after the shell loads
 */

const ProgressiveLoader = {
    /**
     * Initialize progressive loading for leaderboard content
     * @param {string} domain - The domain (e.g., 'vision', 'language')
     */
    initializeLeaderboard: function(domain) {
        document.addEventListener('DOMContentLoaded', function() {
            // Show the loader immediately
            if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.show) {
                LoadingAnimation.show();
            }
            
            // Load the heavy content via AJAX
            fetch(`/${domain}/leaderboard/content/`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.text();
                })
                .then(html => {
                    ProgressiveLoader.injectContent(html);
                })
                .catch(error => {
                    ProgressiveLoader.handleError(error);
                });
        });
    },

    /**
     * Inject the loaded content and execute scripts
     * @param {string} html - The HTML content to inject
     */
    injectContent: function(html) {
        // Replace the entire main content with the loaded content
        const mainContent = document.querySelector('.leaderboard-container');
        if (mainContent) {
            mainContent.innerHTML = html;
            
            // Execute any scripts in the loaded content
            const scripts = mainContent.querySelectorAll('script');
            let scriptsLoaded = 0;
            const totalScripts = scripts.length;
            
            if (totalScripts === 0) {
                // No scripts to load, initialize immediately
                ProgressiveLoader.initializeAfterLoad();
            } else {
                scripts.forEach(script => {
                    const newScript = document.createElement('script');
                    
                    if (script.src) {
                        newScript.src = script.src;
                        newScript.onload = () => {
                            scriptsLoaded++;
                            if (scriptsLoaded === totalScripts) {
                                ProgressiveLoader.initializeAfterLoad();
                            }
                        };
                    } else {
                        newScript.textContent = script.textContent;
                        scriptsLoaded++;
                    }
                    
                    document.head.appendChild(newScript);
                    
                    // For inline scripts, check if we're done
                    if (scriptsLoaded === totalScripts) {
                        ProgressiveLoader.initializeAfterLoad();
                    }
                });
            }
        }
    },

    /**
     * Initialize the leaderboard after all content is loaded
     */
    initializeAfterLoad: function() {
        // Wait a bit for all scripts to settle
        setTimeout(() => {
            if (typeof initializeLeaderboardFromTemplate === 'function') {
                initializeLeaderboardFromTemplate();
            } else {
                console.warn('initializeLeaderboardFromTemplate not found, hiding loader');
                if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.hide) {
                    LoadingAnimation.hide();
                }
            }
        }, 200);
    },

    /**
     * Handle errors during content loading
     * @param {Error} error - The error that occurred
     */
    handleError: function(error) {
        console.error('Error loading leaderboard content:', error);
        
        // Hide loader on error
        if (typeof LoadingAnimation !== 'undefined' && LoadingAnimation.hide) {
            LoadingAnimation.hide();
        }
        
        // Show error message
        const container = document.querySelector('.leaderboard-container');
        if (container) {
            container.innerHTML = '<div style="text-align: center; color: #e74c3c; padding: 40px;"><h3>Error loading leaderboard</h3><p>Please refresh the page to try again.</p></div>';
        }
    }
};

// Export for global access
window.ProgressiveLoader = ProgressiveLoader;
