/**
 * Tutorial page JavaScript functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    initTableOfContents();
    initHeadingPermalinks();
    initInteractiveChecklists();
    initTocScrollSpy();
    initCodeBlockAnchors(); // Add IDs to code blocks for linking
    initAnchorScroll(); // Handle scrolling to anchors (e.g., from search results)
});

/**
 * Generate table of contents from headings in the tutorial content
 * Creates a nested structure where h3s are children of h2s, h4s are children of h3s
 * Only h2s are visible by default; children expand on hover
 */
function initTableOfContents() {
    const tocNav = document.getElementById('toc-nav');
    const tutorialBody = document.querySelector('.tutorial-body');
    
    if (!tocNav || !tutorialBody) return;
    
    // Get all h2, h3, h4 headings (whether they have IDs or not)
    const headings = Array.from(tutorialBody.querySelectorAll('h2, h3, h4'));
    
    if (headings.length === 0) {
        // Hide the TOC widget if no headings
        const tocWidget = tocNav.closest('.toc-widget');
        if (tocWidget) tocWidget.style.display = 'none';
        return;
    }
    
    // Ensure all headings have IDs
    headings.forEach(function(heading, index) {
        if (!heading.id) {
            heading.id = slugify(heading.textContent) || 'heading-' + index;
        }
    });
    
    // Build nested structure
    const tocList = document.createElement('ul');
    tocList.className = 'toc-list';
    
    let currentH2 = null;
    let currentH3 = null;
    let h3List = null;
    let h4List = null;
    
    headings.forEach(function(heading) {
        const li = createTocItem(heading);
        
        if (heading.tagName === 'H2') {
            // H2: Add to main list
            currentH2 = li;
            currentH3 = null;
            h3List = null;
            h4List = null;
            tocList.appendChild(li);
        } else if (heading.tagName === 'H3') {
            // H3: Add as child of current H2
            if (currentH2) {
                if (!h3List) {
                    h3List = document.createElement('ul');
                    h3List.className = 'toc-sublist toc-h3-list';
                    currentH2.appendChild(h3List);
                }
                currentH3 = li;
                h4List = null;
                h3List.appendChild(li);
            } else {
                // No parent H2, add to main list
                tocList.appendChild(li);
            }
        } else if (heading.tagName === 'H4') {
            // H4: Add as child of current H3
            if (currentH3) {
                if (!h4List) {
                    h4List = document.createElement('ul');
                    h4List.className = 'toc-sublist toc-h4-list';
                    currentH3.appendChild(h4List);
                }
                h4List.appendChild(li);
            } else if (currentH2) {
                // No parent H3, add under H2
                if (!h3List) {
                    h3List = document.createElement('ul');
                    h3List.className = 'toc-sublist toc-h3-list';
                    currentH2.appendChild(h3List);
                }
                h3List.appendChild(li);
            } else {
                // No parent, add to main list
                tocList.appendChild(li);
            }
        }
    });
    
    tocNav.appendChild(tocList);
}

/**
 * Create a TOC list item for a heading
 */
function createTocItem(heading) {
    const li = document.createElement('li');
    li.className = 'toc-item toc-' + heading.tagName.toLowerCase();
    
    const link = document.createElement('a');
    link.href = '#' + heading.id;
    link.className = 'toc-link';
    link.textContent = heading.textContent.replace(' 🔗', ''); // Remove link emoji if present
    
    // Smooth scroll on click
    link.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.getElementById(heading.id);
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // Update URL without triggering scroll
            history.pushState(null, null, '#' + heading.id);
        }
    });
    
    li.appendChild(link);
    return li;
}

/**
 * Convert text to URL-friendly slug
 */
function slugify(text) {
    return text
        .toString()
        .toLowerCase()
        .trim()
        .replace(/\s+/g, '-')           // Replace spaces with -
        .replace(/[^\w\-]+/g, '')       // Remove all non-word chars
        .replace(/\-\-+/g, '-')         // Replace multiple - with single -
        .replace(/^-+/, '')             // Trim - from start
        .replace(/-+$/, '');            // Trim - from end
}

/**
 * Highlight current section in TOC as user scrolls
 * Also highlights parent H2 when any child H3/H4 is active
 */
function initTocScrollSpy() {
    const tocLinks = document.querySelectorAll('.toc-link');
    const tocItems = document.querySelectorAll('.toc-item');
    const tutorialBody = document.querySelector('.tutorial-body');
    
    if (tocLinks.length === 0 || !tutorialBody) return;
    
    // Get all heading elements that are in the TOC
    const headingIds = Array.from(tocLinks).map(link => link.getAttribute('href').slice(1));
    const headings = headingIds.map(id => document.getElementById(id)).filter(el => el);
    
    function updateActiveLink() {
        const scrollPosition = window.scrollY + 100; // Offset for header
        
        let currentHeading = null;
        
        // Find the current heading (last one that's above the scroll position)
        headings.forEach(function(heading) {
            if (heading.offsetTop <= scrollPosition) {
                currentHeading = heading;
            }
        });
        
        // Remove all active states
        tocLinks.forEach(function(link) {
            link.classList.remove('active');
        });
        tocItems.forEach(function(item) {
            item.classList.remove('has-active-child');
        });
        
        if (currentHeading) {
            // Find and activate the current link
            const currentLink = document.querySelector('.toc-link[href="#' + currentHeading.id + '"]');
            if (currentLink) {
                currentLink.classList.add('active');
                
                // If this is an H3 or H4, also highlight the parent H2
                const currentItem = currentLink.closest('.toc-item');
                if (currentItem) {
                    // Walk up to find parent H2 item
                    let parent = currentItem.parentElement;
                    while (parent) {
                        if (parent.classList && parent.classList.contains('toc-item') && parent.classList.contains('toc-h2')) {
                            parent.classList.add('has-active-child');
                            // Also highlight the H2 link
                            const parentLink = parent.querySelector(':scope > .toc-link');
                            if (parentLink) {
                                parentLink.classList.add('active');
                            }
                            break;
                        }
                        parent = parent.parentElement;
                    }
                }
            }
        }
    }
    
    // Throttle scroll events for performance
    let ticking = false;
    window.addEventListener('scroll', function() {
        if (!ticking) {
            window.requestAnimationFrame(function() {
                updateActiveLink();
                ticking = false;
            });
            ticking = true;
        }
    });
    
    // Initial update
    updateActiveLink();
}

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

/**
 * Handle scrolling to anchor on page load (e.g., from search results)
 */
function initAnchorScroll() {
    // Check if there's a hash in the URL
    if (window.location.hash) {
        // Wait for content to be fully rendered
        setTimeout(function() {
            const hash = window.location.hash.substring(1); // Remove #
            let target = document.getElementById(hash);
            
            // If it's a code block anchor (code-block-N), find the Nth code block
            if (!target && hash.startsWith('code-block-')) {
                const blockIndex = parseInt(hash.replace('code-block-', ''));
                
                // Try to find by ID first (in case anchors were already added)
                target = document.getElementById(hash);
                
                // If not found, find by index
                if (!target) {
                    // Prioritize .codehilite divs
                    let codeBlocks = document.querySelectorAll('.tutorial-body .codehilite');
                    if (codeBlocks.length === 0) {
                        codeBlocks = document.querySelectorAll('.tutorial-body pre');
                    }
                    
                    // Filter out pre elements inside codehilite
                    const filteredBlocks = Array.from(codeBlocks).filter(function(block) {
                        if (block.tagName === 'PRE') {
                            return !block.closest('.codehilite');
                        }
                        return true;
                    });
                    
                    if (filteredBlocks.length > blockIndex) {
                        target = filteredBlocks[blockIndex];
                        // Add ID if it doesn't have one
                        if (!target.id) {
                            target.id = hash;
                        }
                    }
                }
            }
            
            if (target) {
                // Scroll to the target with offset for fixed header
                const offset = 100; // Adjust based on your header height
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - offset;
                
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
                
                // Highlight the target briefly
                target.style.transition = 'background-color 0.3s';
                target.style.backgroundColor = 'rgba(71, 183, 222, 0.2)';
                setTimeout(function() {
                    target.style.backgroundColor = '';
                    setTimeout(function() {
                        target.style.transition = '';
                    }, 300);
                }, 2000);
            }
        }, 100);
    }
}

/**
 * Add IDs to code blocks for linking from search results
 */
function initCodeBlockAnchors() {
    const tutorialBody = document.querySelector('.tutorial-body');
    if (!tutorialBody) return;
    
    // Find all code blocks - prioritize .codehilite divs (they wrap pre>code)
    // If no .codehilite, fall back to direct <pre> elements
    let codeBlocks = tutorialBody.querySelectorAll('.codehilite');
    
    // If no codehilite blocks, look for direct pre elements
    if (codeBlocks.length === 0) {
        codeBlocks = tutorialBody.querySelectorAll('pre');
    }
    
    // Filter out pre elements that are inside codehilite (to avoid double counting)
    const filteredBlocks = Array.from(codeBlocks).filter(function(block) {
        // If it's a pre element, check if it's inside a codehilite
        if (block.tagName === 'PRE') {
            return !block.closest('.codehilite');
        }
        return true; // Keep codehilite divs
    });
    
    filteredBlocks.forEach(function(block, index) {
        // Only add ID if it doesn't already have one
        if (!block.id) {
            block.id = `code-block-${index}`;
        }
    });
    
}

