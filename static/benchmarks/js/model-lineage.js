(function () {
    const initialVisibleCount = 3;
    const revealCount = 3;

    document.querySelectorAll('[data-model-lineage]').forEach((lineage) => {
        const variants = Array.from(lineage.querySelectorAll('[data-related-variant]'));
        const toggle = lineage.querySelector('[data-lineage-toggle]');
        const label = toggle && toggle.querySelector('[data-lineage-toggle-label]');
        const icon = toggle && toggle.querySelector('i');

        if (!toggle || !label) {
            return;
        }

        const updateToggle = () => {
            const visibleCount = variants.filter((variant) => !variant.hidden).length;
            const remainingCount = variants.length - visibleCount;
            const expanded = visibleCount > initialVisibleCount;

            toggle.setAttribute('aria-expanded', String(expanded));
            if (remainingCount > 0) {
                label.textContent = `+${remainingCount} more metadata-covered variants`;
                icon.classList.remove('fa-chevron-up');
                icon.classList.add('fa-chevron-down');
            } else {
                label.textContent = 'Show fewer variants';
                icon.classList.remove('fa-chevron-down');
                icon.classList.add('fa-chevron-up');
            }
        };

        toggle.addEventListener('click', () => {
            const visibleCount = variants.filter((variant) => !variant.hidden).length;
            if (visibleCount === variants.length) {
                variants.forEach((variant, index) => {
                    variant.hidden = index >= initialVisibleCount;
                });
            } else {
                variants.slice(visibleCount, visibleCount + revealCount).forEach((variant) => {
                    variant.hidden = false;
                });
            }
            updateToggle();
        });

        updateToggle();
    });
}());
