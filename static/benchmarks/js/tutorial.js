/**
 * Tutorial page JavaScript functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    initHeadingPermalinks();
});

/**
 * Make headings clickable to copy permalink to clipboard
 */
function initHeadingPermalinks() {
    const headings = document.querySelectorAll('.tutorial-body h1[id], .tutorial-body h2[id], .tutorial-body h3[id], .tutorial-body h4[id]');
    
    headings.forEach(function(heading) {
        heading.addEventListener('click', function() {
            const id = this.getAttribute('id');
            const url = window.location.origin + window.location.pathname + '#' + id;
            
            // Copy to clipboard
            navigator.clipboard.writeText(url).then(function() {
                // Show feedback tooltip
                const tooltip = document.createElement('span');
                tooltip.className = 'copy-tooltip show';
                tooltip.textContent = 'Link copied!';
                heading.style.position = 'relative';
                heading.appendChild(tooltip);
                
                // Remove tooltip after delay
                setTimeout(function() {
                    tooltip.classList.remove('show');
                    setTimeout(function() {
                        tooltip.remove();
                    }, 300);
                }, 1500);
            }).catch(function(err) {
                console.error('Failed to copy permalink: ', err);
            });
        });
    });
}

