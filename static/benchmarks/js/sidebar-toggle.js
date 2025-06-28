// Sidebar toggle functionality
document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.left-sidebar');
    const contentContainer = document.querySelector('.content-container');
    
    // Check for saved state in localStorage
    const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    
    // Apply saved state
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
        if (contentContainer) {
            contentContainer.classList.add('sidebar-collapsed');
        }
    }
    
    // Toggle functionality
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            const isCurrentlyCollapsed = sidebar.classList.contains('collapsed');
            
            if (isCurrentlyCollapsed) {
                // Expand sidebar
                sidebar.classList.remove('collapsed');
                if (contentContainer) {
                    contentContainer.classList.remove('sidebar-collapsed');
                }
                localStorage.setItem('sidebarCollapsed', 'false');
            } else {
                // Collapse sidebar
                sidebar.classList.add('collapsed');
                if (contentContainer) {
                    contentContainer.classList.add('sidebar-collapsed');
                }
                localStorage.setItem('sidebarCollapsed', 'true');
            }
        });
    }
}); 