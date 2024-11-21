document.addEventListener('DOMContentLoaded', function() {
    const element = document.querySelector('.last-updated-time');
    if (!element) return;
    
    const timestamp = element.dataset.timestamp;
    if (timestamp === 'Never') {
        element.textContent = 'Never';
        return;
    }

    try {
        const date = new Date(timestamp);
        // Convert Isoformat to readable local time format
        element.textContent = date.toLocaleString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
            timeZoneName: 'short'
        });
        element.title = date.toString();
    } catch (e) {
        // If there is an error, just show the isoformat timestamp
        element.textContent = timestamp;
        console.error('Error formatting date:', e);  // Log error for debugging
    }
});