/**
 * Generic link click tracking for Google Analytics (gtag).
 *
 * Usage:
 *   trackLinks({
 *       // Track a single element by ID
 *       ids: {
 *           'berg-link': { category: 'BERG', label: 'main_link' }
 *       },
 *       // Track elements matching a CSS selector, reading the label from a data attribute
 *       selectors: {
 *           '.berg-box-link': { category: 'BERG', labelAttr: 'data-berg-label' }
 *       },
 *       // Delegated tracking: clicks inside a container, mapped by URL substring
 *       delegated: {
 *           '.tooltip-multiline a': {
 *               category: 'BERG',
 *               urlMap: {
 *                   'gifale95.github.io/BERG': 'tooltip_berg',
 *                   'readthedocs': 'tooltip_documentation',
 *                   'drive.google.com': 'tooltip_tutorial'
 *               },
 *               fallbackLabel: 'unknown'
 *           }
 *       }
 *   });
 */
function trackLinks(config) {
    if (typeof gtag === 'undefined') return;

    // Track by element ID
    if (config.ids) {
        Object.keys(config.ids).forEach(function(id) {
            var el = document.getElementById(id);
            if (!el) return;
            var opts = config.ids[id];
            el.addEventListener('click', function() {
                gtag('event', 'click', {
                    event_category: opts.category,
                    event_label: opts.label,
                    transport_type: 'beacon'
                });
            });
        });
    }

    // Track by CSS selector, with label from a data attribute or a fixed string
    if (config.selectors) {
        Object.keys(config.selectors).forEach(function(selector) {
            var opts = config.selectors[selector];
            document.querySelectorAll(selector).forEach(function(el) {
                el.addEventListener('click', function() {
                    var label = opts.labelAttr
                        ? this.getAttribute(opts.labelAttr)
                        : opts.label;
                    gtag('event', 'click', {
                        event_category: opts.category,
                        event_label: label,
                        transport_type: 'beacon'
                    });
                });
            });
        });
    }

    // Delegated click tracking: match clicked links by URL substring
    if (config.delegated) {
        Object.keys(config.delegated).forEach(function(selector) {
            var opts = config.delegated[selector];
            document.addEventListener('click', function(e) {
                var link = e.target.closest(selector);
                if (!link) return;
                var href = link.getAttribute('href') || '';
                var label = opts.fallbackLabel || 'unknown';
                var urls = Object.keys(opts.urlMap);
                for (var i = 0; i < urls.length; i++) {
                    if (href.indexOf(urls[i]) !== -1) {
                        label = opts.urlMap[urls[i]];
                        break;
                    }
                }
                gtag('event', 'click', {
                    event_category: opts.category,
                    event_label: label,
                    transport_type: 'beacon'
                });
            });
        });
    }
}
