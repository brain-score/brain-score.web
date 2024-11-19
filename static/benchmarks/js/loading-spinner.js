/**
 * LoadingSpinner module handles displaying and hiding a loading spinner overlay
 * to indicate background processing to users. Currently only used for the
 * leaderboard page when loading model cards but can be used elsewhere.
 */
const LoadingSpinner = {
    /**
     * Shows the loading spinner overlay and adds beforeunload event listener
     * to handle page navigation attempts while loading.
     */
    show: function() {
        document.getElementById('loading-overlay').style.display = 'flex';
        window.addEventListener('beforeunload', this.handleCancel);
    },
    //Hides the loading spinner overlay and removes the beforeunload event listener.
    hide: function() {
        document.getElementById('loading-overlay').style.display = 'none'; 
        window.removeEventListener('beforeunload', this.handleCancel);
    },
    // Event handler that hides the spinner when user attempts to leave/reload page.
    handleCancel: function(event) {
        LoadingSpinner.hide();
    }
};

// Hide spinner when user navigates back/forward in browser history
window.addEventListener('popstate', function() {
    LoadingSpinner.hide();
});