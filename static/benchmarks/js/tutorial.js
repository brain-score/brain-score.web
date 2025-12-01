/**
 * Tutorial page JavaScript functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    initHeadingPermalinks();
    initInteractiveChecklists();
});

/**
 * Convert markdown-style checkboxes to interactive HTML checkboxes
 * Looks for [ ] and [x] patterns in list items
 */
function initInteractiveChecklists() {
    const tutorialBody = document.querySelector('.tutorial-body');
    if (!tutorialBody) return;
    
    // Find all list items
    const listItems = tutorialBody.querySelectorAll('li');
    
    listItems.forEach(function(li) {
        const text = li.innerHTML;
        
        // Check for unchecked box [ ]
        if (text.match(/^\s*\[ \]/)) {
            li.innerHTML = text.replace(/^\s*\[ \]/, 
                '<input type="checkbox" class="tutorial-checkbox"> ');
            li.classList.add('checklist-item');
        }
        // Check for checked box [x] or [X]
        else if (text.match(/^\s*\[[xX]\]/)) {
            li.innerHTML = text.replace(/^\s*\[[xX]\]/, 
                '<input type="checkbox" class="tutorial-checkbox" checked> ');
            li.classList.add('checklist-item');
        }
    });
    
    // Add click handler for the entire list item (better UX)
    document.querySelectorAll('.checklist-item').forEach(function(item) {
        item.addEventListener('click', function(e) {
            // Don't toggle if clicking the checkbox itself (it handles itself)
            if (e.target.type === 'checkbox') return;
            
            const checkbox = item.querySelector('.tutorial-checkbox');
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
            }
        });
    });
}

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

