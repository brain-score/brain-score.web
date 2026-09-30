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

// Empty metadata sections retain their original layout and use keyboard buttons.
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-metadata-toggle]').forEach(function (button) {
        const target = document.getElementById(button.getAttribute('aria-controls'));
        if (!target) return;
        function setExpanded(expanded) {
            target.hidden = !expanded;
            button.setAttribute('aria-expanded', String(expanded));
            button.classList.toggle('is_collapsible', expanded);
            button.classList.toggle('is_expandable', !expanded);
        }
        setExpanded(false);
        button.addEventListener('click', function () {
            setExpanded(button.getAttribute('aria-expanded') !== 'true');
        });
    });
});

// Native dialogs provide focus containment, Escape, and focus restoration.
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-schema-open]').forEach(function (button) {
        const dialog = document.getElementById(button.getAttribute('aria-controls'));
        if (!dialog) return;
        button.addEventListener('click', function () { dialog.showModal(); });
    });
});
