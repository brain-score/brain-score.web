window.LoadingSpinner = {
    show: function() {
        console.log('Show function called');
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('visible');
        }
    },
    
    hide: function() {
        console.log('Hide called from:', new Error().stack);  // This will show us what's calling hide
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('visible');
        }
        window.removeEventListener('beforeunload', this.handleCancel);
    },
    
    handleCancel: function(event) {
        console.log('Cancel handler called');
        LoadingSpinner.hide();
    }
};

