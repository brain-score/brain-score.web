/**
 * LoadingAnimation module handles displaying and hiding a loading animation overlay
 * to indicate background processing to users. Used for the leaderboard page
 * during grid initialization and for model card loading.
 */
const LoadingAnimation = {
    fallbackTimeout: null,
    
    /**
     * Shows the loading animation overlay and adds beforeunload event listener
     * to handle page navigation attempts while loading.
     */
    show: function() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            window.addEventListener('beforeunload', this.handleCancel);
            
            // Set fallback timeout to prevent loader from staying forever
            this.fallbackTimeout = setTimeout(() => {
                console.warn('Loading animation fallback timeout reached - hiding animation');
                this.hide();
            }, 10000); // 10 second fallback
        }
    },
    
    /**
     * Hides the loading animation overlay and removes the beforeunload event listener.
     */
    hide: function() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'none'; 
            window.removeEventListener('beforeunload', this.handleCancel);
            
            // Clear fallback timeout
            if (this.fallbackTimeout) {
                clearTimeout(this.fallbackTimeout);
                this.fallbackTimeout = null;
            }
        }
    },
    
    /**
     * Event handler that hides the animation when user attempts to leave/reload page.
     */
    handleCancel: function(event) {
        LoadingAnimation.hide();
    }
};

// Hide animation when user navigates back/forward in browser history
window.addEventListener('popstate', function() {
    LoadingAnimation.hide();
});
