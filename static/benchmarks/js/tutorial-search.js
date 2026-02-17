/**
 * Tutorial Search Functionality
 * Provides search across all tutorial markdown documents
 */

(function() {
    'use strict';

    // Store tutorial search data
    let tutorialSearchData = [];
    let searchResultsContainer = null;
    let searchInput = null;
    let currentSearchQuery = '';

    /**
     * Initialize tutorial search functionality
     */
    function initTutorialSearch() {
        // Get search data from window (set by template)
        if (window.tutorialSearchData) {
            // Parse JSON if it's a string
            if (typeof window.tutorialSearchData === 'string') {
                try {
                    tutorialSearchData = JSON.parse(window.tutorialSearchData);
                } catch (e) {
                    console.error('Failed to parse tutorial search data:', e);
                    return;
                }
            } else {
                tutorialSearchData = window.tutorialSearchData;
            }
        } else {
            console.warn('Tutorial search data not found. Search functionality may not work.');
            return;
        }

        // Create search UI if it doesn't exist
        createSearchUI();

        // Setup event listeners
        setupSearchListeners();
    }

    /**
     * Create search bar UI component
     */
    function createSearchUI() {
        // Check if search UI already exists
        if (document.getElementById('tutorial-search-input')) {
            searchInput = document.getElementById('tutorial-search-input');
            searchResultsContainer = document.getElementById('tutorial-search-results');
            return; // Already exists
        }

        // Find the sidebar or content area
        const sidebar = document.querySelector('.tutorial-sidebar');
        const contentArea = document.querySelector('.content') || document.querySelector('main') || document.querySelector('.box') || document.body;
        
        if (!contentArea) {
            console.warn('Could not find content area for tutorial search. Search bar will not be displayed.');
            return;
        }
        
        // Create search container
        const searchContainer = document.createElement('div');
        searchContainer.className = 'tutorial-search-container';
        searchContainer.innerHTML = `
            <div class="tutorial-search-box">
                <input 
                    type="text" 
                    id="tutorial-search-input" 
                    class="tutorial-search-input" 
                    placeholder="Search tutorials..."
                    autocomplete="off"
                />
                <span class="tutorial-search-icon">🔍</span>
            </div>
            <div id="tutorial-search-results" class="tutorial-search-results" style="display: none;"></div>
        `;

        // Insert search in sidebar if it exists, otherwise at top of content
        if (sidebar) {
            const sidebarWidget = sidebar.querySelector('.sidebar-widget:first-child');
            if (sidebarWidget) {
                sidebar.insertBefore(searchContainer, sidebarWidget);
            } else {
                sidebar.insertBefore(searchContainer, sidebar.firstChild);
            }
        } else {
            // For list page, insert before first content box
            const firstBox = contentArea.querySelector('.box:first-child');
            if (firstBox && firstBox.parentNode) {
                firstBox.parentNode.insertBefore(searchContainer, firstBox);
            } else if (contentArea.firstChild) {
                contentArea.insertBefore(searchContainer, contentArea.firstChild);
            } else {
                contentArea.appendChild(searchContainer);
            }
        }

        searchInput = document.getElementById('tutorial-search-input');
        searchResultsContainer = document.getElementById('tutorial-search-results');
        
        if (!searchInput || !searchResultsContainer) {
            console.error('Failed to create tutorial search UI elements');
        }
    }

    /**
     * Setup search input event listeners
     */
    function setupSearchListeners() {
        if (!searchInput) return;

        // Search on input
        let searchTimeout;
        searchInput.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            const query = e.target.value.trim();
            currentSearchQuery = query;

            if (query.length === 0) {
                hideSearchResults();
                return;
            }

            // Debounce search
            searchTimeout = setTimeout(() => {
                performSearch(query);
            }, 150);
        });

        // Handle keyboard navigation
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                hideSearchResults();
                searchInput.blur();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                navigateResults(1);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                navigateResults(-1);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                selectFirstResult();
            }
        });

        // Close results when clicking outside
        document.addEventListener('click', function(e) {
            if (searchResultsContainer && 
                !searchResultsContainer.contains(e.target) && 
                e.target !== searchInput) {
                hideSearchResults();
            }
        });
    }

    /**
     * Perform search across all tutorials
     */
    function performSearch(query) {
        if (!query || query.length < 2) {
            hideSearchResults();
            return;
        }

        const results = [];
        const queryLower = query.toLowerCase();
        const queryTerms = queryLower.split(/\s+/).filter(term => term.length > 0);

        // Search through each tutorial
        tutorialSearchData.forEach(tutorial => {
            const matches = findMatchesInTutorial(tutorial, queryTerms);
            if (matches.length > 0) {
                results.push({
                    tutorial: tutorial,
                    matches: matches
                });
            }
        });

        displaySearchResults(results, query);
    }

    /**
     * Find matches in a single tutorial
     */
    function findMatchesInTutorial(tutorial, queryTerms) {
        const matches = [];
        const searchable = tutorial.searchable || {};
        const fullText = searchable.full_text || '';
        const codeBlocksRaw = searchable.code_blocks || [];
        const codeBlocks = codeBlocksRaw.map((cb, idx) => {
            if (typeof cb === 'string') {
                return { text: cb, index: idx };
            }
            return cb;
        });
        
        const allTermsMatchFullText = queryTerms.every(term => fullText.includes(term));
        const allTermsMatchCodeBlocks = codeBlocks.some(codeBlock => {
            if (!codeBlock) return false;
            const codeText = (codeBlock.text || codeBlock).toLowerCase();
            return queryTerms.every(term => codeText.includes(term));
        });
        
        // If neither full text nor code blocks match, return empty
        if (!allTermsMatchFullText && !allTermsMatchCodeBlocks) {
            return matches;
        }

        // Find matches in headings (higher priority)
        // Require ALL terms to match in headings
        const headings = searchable.headings || [];
        headings.forEach(heading => {
            const headingText = heading.text.toLowerCase();
            // Check if ALL terms match in this heading
            const allTermsMatchHeading = queryTerms.every(term => headingText.includes(term));
            if (allTermsMatchHeading) {
                matches.push({
                    type: 'heading',
                    heading: heading,
                    snippet: heading.text,
                    relevance: calculateRelevance(heading.text, queryTerms)
                });
            }
        });

        // Find matches in text content (extract snippets)
        // Require snippets to contain ALL terms
        const text = searchable.text || '';
        const snippets = extractTextSnippets(text, queryTerms);
        
        if (snippets.length > 0) {
            snippets.forEach(snippet => {
                // Double-check that snippet contains all terms
                const snippetLower = snippet.text.toLowerCase();
                const containsAllTerms = queryTerms.every(term => snippetLower.includes(term));
                if (containsAllTerms) {
                    matches.push({
                        type: 'content',
                        snippet: snippet.text,
                        relevance: snippet.relevance
                    });
                }
            });
        } else {
            const textLower = text.toLowerCase();
            const termPositions = {};
            queryTerms.forEach(term => {
                const index = textLower.indexOf(term);
                if (index !== -1) {
                    termPositions[term] = index;
                }
            });
            
            if (Object.keys(termPositions).length === queryTerms.length) {
                const positions = Object.values(termPositions).sort((a, b) => a - b);
                const firstPos = positions[0];
                const lastPos = positions[positions.length - 1];
                const span = lastPos - firstPos;
                
                const maxPadding = 80;
                const padding = Math.min(maxPadding, Math.max(40, span / 2 + 20));
                const start = Math.max(0, firstPos - padding);
                const end = Math.min(text.length, lastPos + padding);
                let snippet = text.substring(start, end).trim();
                
                if (snippet.length > 200) {
                    const center = (firstPos + lastPos) / 2;
                    const newStart = Math.max(0, Math.floor(center - 100));
                    const newEnd = Math.min(text.length, Math.floor(center + 100));
                    snippet = text.substring(newStart, newEnd).trim();
                    if (newStart > 0) snippet = '...' + snippet;
                    if (newEnd < text.length) snippet = snippet + '...';
                } else {
                    if (start > 0) snippet = '...' + snippet;
                    if (end < text.length) snippet = snippet + '...';
                }
                
                matches.push({
                    type: 'content',
                    snippet: snippet,
                    relevance: calculateRelevance(snippet, queryTerms) - 10
                });
            }
        }

        if (codeBlocks && codeBlocks.length > 0) {
            codeBlocks.forEach((codeBlock, blockIndex) => {
                if (!codeBlock) return;
                const codeBlockText = codeBlock.text || codeBlock;
                const codeBlockIndex = codeBlock.index !== undefined ? codeBlock.index : blockIndex;
                const codeText = String(codeBlockText).toLowerCase();
                
                const allTermsMatchCode = queryTerms.every(term => codeText.includes(term));
                
                if (allTermsMatchCode) {
                    const snippet = extractCodeSnippet(codeBlockText, queryTerms);
                    const snippetLower = snippet.toLowerCase();
                    const snippetContainsTerms = queryTerms.every(term => snippetLower.includes(term));
                    
                    if (snippetContainsTerms) {
                        matches.push({
                            type: 'code',
                            snippet: snippet,
                            relevance: calculateRelevance(codeBlockText, queryTerms) + 5,
                            blockIndex: codeBlockIndex
                        });
                    } else {
                        const fallbackSnippet = extractCodeSnippetFallback(codeBlockText, queryTerms);
                        if (fallbackSnippet) {
                            matches.push({
                                type: 'code',
                                snippet: fallbackSnippet,
                                relevance: calculateRelevance(codeBlockText, queryTerms) + 5,
                                blockIndex: codeBlockIndex
                            });
                        }
                    }
                }
            });
        }

        // Sort by relevance
        matches.sort((a, b) => b.relevance - a.relevance);

        // Return all matches (don't limit - show all code blocks and content matches)
        return matches;
    }

    /**
     * Extract text snippets containing ALL search terms
     */
    function extractTextSnippets(text, queryTerms) {
        const snippets = [];
        const textLower = text.toLowerCase();
        const snippetLength = 150;
        
        // First, verify ALL terms exist in the text
        const allTermsExist = queryTerms.every(term => textLower.includes(term));
        if (!allTermsExist) {
            return snippets; // Return empty if not all terms are present
        }
        
        // Find positions of ALL search terms
        const termPositions = {};
        queryTerms.forEach(term => {
            termPositions[term] = [];
            let index = textLower.indexOf(term);
            while (index !== -1) {
                termPositions[term].push(index);
                index = textLower.indexOf(term, index + 1);
            }
        });

        // Find regions that contain all terms
        // Strategy: Find the span that contains all terms, then extract a snippet around that span
        let minTermPos = Infinity;
        let maxTermPos = -Infinity;
        
        // Find the minimum and maximum positions of all terms
        queryTerms.forEach(term => {
            if (termPositions[term].length > 0) {
                // Use the first occurrence of each term to find a close grouping
                minTermPos = Math.min(minTermPos, termPositions[term][0]);
                maxTermPos = Math.max(maxTermPos, termPositions[term][0]);
            }
        });
        
        if (minTermPos !== Infinity && maxTermPos !== -Infinity) {
            // Calculate the center of the term positions
            const center = (minTermPos + maxTermPos) / 2;
            const start = Math.max(0, Math.floor(center - snippetLength / 2));
            const end = Math.min(text.length, Math.floor(center + snippetLength / 2));
            let snippet = text.substring(start, end).trim();
            
            // Verify the snippet actually contains all terms (double-check)
            const snippetLower = snippet.toLowerCase();
            const containsAllTerms = queryTerms.every(term => snippetLower.includes(term));
            
            if (containsAllTerms) {
                // Add ellipsis if needed
                if (start > 0) snippet = '...' + snippet;
                if (end < text.length) snippet = snippet + '...';
                
                snippets.push({
                    text: snippet,
                    relevance: calculateRelevance(snippet, queryTerms)
                });
            }
        }
        
        // If the first approach didn't work (terms might be far apart), try finding
        // snippets around each occurrence, ensuring all terms are within a larger window
        if (snippets.length === 0) {
            // Use a larger window to find terms that might be further apart
            const largeWindow = snippetLength * 3;
            
            queryTerms.forEach(term => {
                termPositions[term].forEach(pos => {
                    const windowStart = Math.max(0, pos - largeWindow / 2);
                    const windowEnd = Math.min(text.length, pos + largeWindow / 2);
                    const windowText = textLower.substring(windowStart, windowEnd);
                    
                    // Check if all terms are in this larger window
                    const allTermsInWindow = queryTerms.every(t => windowText.includes(t));
                    
                    if (allTermsInWindow) {
                        // Extract a snippet centered on this position
                        const snippetStart = Math.max(0, pos - snippetLength / 2);
                        const snippetEnd = Math.min(text.length, pos + snippetLength / 2);
                        let snippet = text.substring(snippetStart, snippetEnd).trim();
                        
                        // Verify it contains all terms
                        const snippetLower = snippet.toLowerCase();
                        if (queryTerms.every(t => snippetLower.includes(t))) {
                            if (snippetStart > 0) snippet = '...' + snippet;
                            if (snippetEnd < text.length) snippet = snippet + '...';
                            
                            // Avoid duplicates
                            const isDuplicate = snippets.some(s => {
                                const overlap = Math.abs(s.text.length - snippet.length) < 50 &&
                                              (s.text.toLowerCase().includes(snippet.substring(0, 30).toLowerCase()) ||
                                               snippet.toLowerCase().includes(s.text.substring(0, 30).toLowerCase()));
                                return overlap;
                            });
                            
                            if (!isDuplicate) {
                                snippets.push({
                                    text: snippet,
                                    relevance: calculateRelevance(snippet, queryTerms)
                                });
                                
                                if (snippets.length >= 3) return; // Limit to 3 snippets
                            }
                        }
                    }
                });
            });
        }

        return snippets.slice(0, 3); // Limit to 3 snippets
    }

    /**
     * Extract code snippet containing search terms
     */
    function extractCodeSnippet(codeBlock, queryTerms) {
        if (!codeBlock) return '';
        
        const codeStr = String(codeBlock); // Ensure it's a string
        const codeLower = codeStr.toLowerCase();
        const maxSnippetLength = 150; // Shorter, more focused snippets
        
        // Find positions of all terms
        const termPositions = {};
        queryTerms.forEach(term => {
            termPositions[term] = [];
            let index = codeLower.indexOf(term);
            while (index !== -1) {
                termPositions[term].push(index);
                index = codeLower.indexOf(term, index + 1);
            }
        });
        
        // Check if all terms exist
        const allTermsExist = queryTerms.every(term => termPositions[term].length > 0);
        if (!allTermsExist) {
            return ''; // Don't return snippet if terms don't exist
        }
        
        // Find the span containing all terms (use first occurrence of each)
        let minPos = Infinity;
        let maxPos = -Infinity;
        queryTerms.forEach(term => {
            if (termPositions[term].length > 0) {
                // Use first occurrence for more focused snippet
                minPos = Math.min(minPos, termPositions[term][0]);
                maxPos = Math.max(maxPos, termPositions[term][0] + term.length);
            }
        });
        
        if (minPos === Infinity || maxPos === -Infinity) {
            return '';
        }
        
        // Calculate padding to ensure snippet contains all terms
        // Start with 75 chars on each side, but ensure we capture all terms
        let padding = 75;
        let start = Math.max(0, minPos - padding);
        let end = Math.min(codeStr.length, maxPos + padding);
        let snippet = codeStr.substring(start, end).trim();
        
        // Verify snippet contains all terms - if not, expand
        let attempts = 0;
        while (attempts < 3) {
            const snippetLower = snippet.toLowerCase();
            const containsAllTerms = queryTerms.every(term => snippetLower.includes(term));
            if (containsAllTerms) break;
            
            // Expand snippet
            padding += 50;
            start = Math.max(0, minPos - padding);
            end = Math.min(codeStr.length, maxPos + padding);
            snippet = codeStr.substring(start, end).trim();
            attempts++;
        }
        
        // If snippet is too long, trim but ensure terms remain visible
        if (snippet.length > maxSnippetLength) {
            // Find relative positions of terms in current snippet
            const relativeMinPos = minPos - start;
            const relativeMaxPos = maxPos - start;
            
            // Center around terms, but ensure they're included
            const center = (relativeMinPos + relativeMaxPos) / 2;
            const halfLength = maxSnippetLength / 2;
            let newStart = Math.max(0, Math.floor(center - halfLength));
            let newEnd = Math.min(snippet.length, Math.floor(center + halfLength));
            
            // Ensure terms are included
            newStart = Math.min(newStart, relativeMinPos);
            newEnd = Math.max(newEnd, relativeMaxPos);
            
            snippet = snippet.substring(newStart, newEnd).trim();
        }
        
        // Add ellipsis if needed
        if (start > 0) snippet = '...' + snippet;
        if (end < codeStr.length) snippet = snippet + '...';
        
        // Final verification - snippet MUST contain all terms
        const finalSnippetLower = snippet.toLowerCase();
        if (!queryTerms.every(term => finalSnippetLower.includes(term))) {
            // Last resort: extract snippet directly around terms
            const finalStart = Math.max(0, minPos - 50);
            const finalEnd = Math.min(codeStr.length, maxPos + 50);
            snippet = codeStr.substring(finalStart, finalEnd).trim();
            if (finalStart > 0) snippet = '...' + snippet;
            if (finalEnd < codeStr.length) snippet = snippet + '...';
        }
        
        return snippet;
    }

    /**
     * Extract code snippet at a specific position
     */
    function extractCodeSnippetAtPosition(codeBlock, position, queryTerms) {
        if (!codeBlock || position === undefined) return '';
        
        const codeStr = String(codeBlock);
        const maxSnippetLength = 150;
        
        // Extract snippet centered around the position
        const start = Math.max(0, position - maxSnippetLength / 2);
        const end = Math.min(codeStr.length, position + maxSnippetLength / 2);
        let snippet = codeStr.substring(start, end).trim();
        
        if (start > 0) snippet = '...' + snippet;
        if (end < codeStr.length) snippet = snippet + '...';
        
        return snippet;
    }

    /**
     * Fallback code snippet extraction that guarantees terms are included
     */
    function extractCodeSnippetFallback(codeBlock, queryTerms) {
        if (!codeBlock) return '';
        
        const codeStr = String(codeBlock);
        const codeLower = codeStr.toLowerCase();
        
        // Find the first occurrence of the first search term
        const firstTerm = queryTerms[0];
        const firstTermPos = codeLower.indexOf(firstTerm);
        
        if (firstTermPos === -1) return '';
        
        // Extract snippet around the first term (100 chars before and after)
        const start = Math.max(0, firstTermPos - 100);
        const end = Math.min(codeStr.length, firstTermPos + firstTerm.length + 100);
        let snippet = codeStr.substring(start, end).trim();
        
        if (start > 0) snippet = '...' + snippet;
        if (end < codeStr.length) snippet = snippet + '...';
        
        return snippet;
    }

    /**
     * Calculate relevance score for a match
     */
    function calculateRelevance(text, queryTerms) {
        const textLower = text.toLowerCase();
        let score = 0;
        
        queryTerms.forEach(term => {
            // Exact match gets higher score
            if (textLower.includes(term)) {
                score += 10;
                // If term appears at start of word, bonus
                if (textLower.match(new RegExp(`\\b${term}`))) {
                    score += 5;
                }
            }
        });

        // Shorter text gets bonus (more specific)
        score += Math.max(0, 100 - text.length / 10);

        return score;
    }

    /**
     * Display search results
     */
    function displaySearchResults(results, query) {
        if (!searchResultsContainer) return;

        if (results.length === 0) {
            searchResultsContainer.innerHTML = `
                <div class="tutorial-search-no-results">
                    No results found for "${query}"
                </div>
            `;
            searchResultsContainer.style.display = 'block';
            return;
        }

        let html = '';
        // Show ALL code blocks, limit other matches
        const maxOtherMatchesPerTutorial = 3; // Limit non-code matches per tutorial
        const maxTotalResults = 100; // Increased to show all code blocks (we have ~20 code blocks)
        let totalResultsShown = 0;
        let totalCodeBlocksShown = 0;
        
        results.forEach((result, tutorialIndex) => {
            const tutorial = result.tutorial;
            const matches = result.matches;
            
            // Prioritize code blocks - show ALL of them, then limit other matches
            const codeMatches = matches.filter(m => m.type === 'code');
            const otherMatches = matches.filter(m => m.type !== 'code');
            
            // Filter code matches to ensure they contain the search terms
            const validCodeMatches = codeMatches.filter(match => {
                if (!match.snippet) return false;
                const snippetLower = match.snippet.toLowerCase();
                const queryLower = query.toLowerCase();
                const queryTerms = queryLower.split(/\s+/).filter(t => t.length > 0);
                return queryTerms.every(term => snippetLower.includes(term));
            });
            
            // Show all valid code matches (no limit), then limit other matches
            const matchesToShow = [...validCodeMatches, ...otherMatches.slice(0, maxOtherMatchesPerTutorial)];
            
            // Always show code blocks, even if we exceed the limit
            if (matchesToShow.length === 0) return;
            
            totalCodeBlocksShown += validCodeMatches.length;
            
            html += `
                <div class="tutorial-search-result-group">
                    <div class="tutorial-search-result-tutorial">
                        <a href="${tutorial.url}" class="tutorial-search-tutorial-link">
                            ${highlightText(tutorial.title, query)}
                        </a>
                        ${tutorial.description ? `<div class="tutorial-search-tutorial-desc">${tutorial.description}</div>` : ''}
                    </div>
                    <div class="tutorial-search-result-matches">
            `;

            matchesToShow.forEach((match, matchIndex) => {
                totalResultsShown++;
                if (totalResultsShown > maxTotalResults) return; // Stop if we've hit the limit
                if (match.type === 'heading') {
                    html += `
                        <a href="${tutorial.url}#${match.heading.slug || match.heading.id}" 
                           class="tutorial-search-result-item tutorial-search-result-heading"
                           data-tutorial-index="${tutorialIndex}"
                           data-match-index="${matchIndex}">
                            <span class="tutorial-search-result-icon">📑</span>
                            <span class="tutorial-search-result-text">${highlightText(match.snippet, query)}</span>
                        </a>
                    `;
                } else if (match.type === 'code') {
                    // Ensure snippet contains search terms before highlighting
                    const snippetLower = match.snippet.toLowerCase();
                    const queryLower = query.toLowerCase();
                    const queryTerms = queryLower.split(/\s+/).filter(t => t.length > 0);
                    const containsQuery = queryTerms.every(term => snippetLower.includes(term));
                    
                    // Only show if snippet actually contains the search terms
                    if (containsQuery) {
                        // Create link with anchor to specific code block
                        const blockIndex = match.blockIndex !== undefined ? match.blockIndex : matchIndex;
                        const codeBlockAnchor = `code-block-${blockIndex}`;
                        const url = `${tutorial.url}#${codeBlockAnchor}`;
                        
                        html += `
                            <a href="${url}" 
                               class="tutorial-search-result-item tutorial-search-result-code"
                               data-tutorial-index="${tutorialIndex}"
                               data-match-index="${matchIndex}"
                               data-code-block-index="${blockIndex}">
                                <span class="tutorial-search-result-icon">💻</span>
                                <span class="tutorial-search-result-text"><code>${highlightText(match.snippet, query)}</code></span>
                            </a>
                        `;
                    }
                } else {
                    html += `
                        <a href="${tutorial.url}" 
                           class="tutorial-search-result-item tutorial-search-result-content"
                           data-tutorial-index="${tutorialIndex}"
                           data-match-index="${matchIndex}">
                            <span class="tutorial-search-result-icon">📄</span>
                            <span class="tutorial-search-result-text">${highlightText(match.snippet, query)}</span>
                        </a>
                    `;
                }
            });

            html += `
                    </div>
                </div>
            `;
        });

        searchResultsContainer.innerHTML = html;
        searchResultsContainer.style.display = 'block';

        // Setup click handlers for results
        setupResultClickHandlers();
    }

    /**
     * Highlight search terms in text
     */
    function highlightText(text, query) {
        if (!query) return text;
        
        const queryTerms = query.toLowerCase().split(/\s+/).filter(term => term.length > 0);
        let highlighted = text;
        
        queryTerms.forEach(term => {
            const regex = new RegExp(`(${escapeRegex(term)})`, 'gi');
            highlighted = highlighted.replace(regex, '<mark>$1</mark>');
        });
        
        return highlighted;
    }

    /**
     * Escape special regex characters
     */
    function escapeRegex(str) {
        return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * Setup click handlers for search results
     */
    function setupResultClickHandlers() {
        const resultItems = searchResultsContainer.querySelectorAll('.tutorial-search-result-item');
        resultItems.forEach(item => {
            item.addEventListener('click', function(e) {
                // Let the link navigate naturally
                // The target page will handle scrolling to anchors
            });
        });
    }

    /**
     * Hide search results
     */
    function hideSearchResults() {
        if (searchResultsContainer) {
            searchResultsContainer.style.display = 'none';
        }
    }

    /**
     * Navigate search results with keyboard
     */
    function navigateResults(direction) {
        const items = searchResultsContainer.querySelectorAll('.tutorial-search-result-item');
        if (items.length === 0) return;

        let currentIndex = -1;
        items.forEach((item, index) => {
            if (item.classList.contains('active')) {
                currentIndex = index;
            }
        });

        const newIndex = Math.max(0, Math.min(items.length - 1, currentIndex + direction));
        items.forEach(item => item.classList.remove('active'));
        if (items[newIndex]) {
            items[newIndex].classList.add('active');
            items[newIndex].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    /**
     * Select first result
     */
    function selectFirstResult() {
        const firstItem = searchResultsContainer.querySelector('.tutorial-search-result-item');
        if (firstItem) {
            window.location.href = firstItem.href;
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTutorialSearch);
    } else {
        initTutorialSearch();
    }

    // Export for external use
    window.TutorialSearch = {
        init: initTutorialSearch,
        performSearch: performSearch
    };

})();

