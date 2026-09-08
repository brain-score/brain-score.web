// Model-card behaviors (sections that collapsible.js doesn't cover).
// Currently: the lineage "Related variants" show-more toggle, which uses
// `hidden` attributes + aria-expanded rather than collapsible.js's
// display-based convention.
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-lineage-toggle]').forEach(function (button) {
        const list = document.getElementById(button.getAttribute('aria-controls'));
        if (!list) return;
        const extras = Array.from(list.querySelectorAll('[data-related-variant][hidden]'));
        const label = button.querySelector('[data-lineage-toggle-label]');
        const chevron = button.querySelector('i');
        const collapsedLabel = label ? label.textContent : '';

        button.addEventListener('click', function () {
            const expand = button.getAttribute('aria-expanded') !== 'true';
            extras.forEach(function (item) { item.hidden = !expand; });
            button.setAttribute('aria-expanded', String(expand));
            if (label) label.textContent = expand ? 'Show fewer variants' : collapsedLabel;
            if (chevron) {
                chevron.classList.toggle('fa-chevron-up', expand);
                chevron.classList.toggle('fa-chevron-down', !expand);
            }
        });
    });
});
