$(document).ready(function () {
    const domain = location.pathname.split('/').filter(i => i)[0] || 'vision';
    const isRootIdentifier = (e) => e.currentTarget.dataset.benchmark === `average_${domain}`;

    if (document.querySelector('.leaderboard-table-component')) {
        $('th[data-benchmark]').click(onClickExpandCollapseBenchmark);
        
        // Get URL parameters immediately
        const benchmark = new URLSearchParams(window.location.search).get('benchmark');
        if (!benchmark) return;

        // Use requestAnimationFrame to wait for cache to load
        requestAnimationFrame(() => {
            const targetElement = document.querySelector(`[data-benchmark="${benchmark}"]`);
            if (targetElement) {
                onClickExpandCollapseBenchmark({
                    currentTarget: targetElement,
                    type: "initial-load"
                });
            }
        });
    }

    function onClickExpandCollapseBenchmark(event) {
        const benchmarkCount = event.currentTarget.querySelector('.benchmark-count');

        // If the user clicks on a benchmark without a count or the average column there are no children to expand, so do nothing.
        // If the user clicks on the breadcrumb link matching the root identifier execute.
        // And all other cases handle the click.
        if (!benchmarkCount || (event.type !== "breadcrumb-click" && isRootIdentifier(event))) { return; }

        // start by hiding everything
        $('[data-benchmark]').css('display','none');
        // reshow the element that was actually clicked
        event.currentTarget.style.display  = '';

        // toggle the open state
        if ((isClosed = !benchmarkCount.classList.contains('open'))) {
            !isRootIdentifier(event) && benchmarkCount.classList.add('open');
            expandChild(event);
        } else {
            benchmarkCount.classList.remove('open');
            expandParent(event);
        }

        let benchmark = event.currentTarget.dataset.benchmark;

        // If expanding, set the URL to the parent benchmark
        if (!isClosed) {
            const parentBenchmark = event.currentTarget.dataset.parent;
            if (parentBenchmark) {
                benchmark = parentBenchmark.replace('_v0', '');
            }
        }

        const newUrl = `/${domain}/leaderboard/?benchmark=${benchmark}`;
        updateUrl(newUrl);
    }

    function expandChild(event) {
        const benchmark = event.currentTarget.dataset.benchmark;
        // the `$=` attribute selector e.g. [attr$=val] matches a suffix
        $(`[data-benchmark$="${benchmark}_v0"],[data-parent="${benchmark}_v0"]`).css('display', '');

        if (isRootIdentifier(event)) {
             $('[data-parent="None"]').css('display', '');
        }
        setBreadCrumbs($(event.currentTarget));
    }

    function expandParent(event) {
        const benchmark = event.currentTarget.dataset.parent;
        // special case this so returning back to the main view expands the immediate children
        if (event.currentTarget.dataset.depth === '0' || event.currentTarget.dataset.parent === `average_${domain}_v0`) {
            $(`[data-parent="None"],[data-parent="average_${domain}_v0"]`).css('display', '');
        } else {
            $(`[data-benchmark="${benchmark.replace('_v0', '')}"],[data-benchmark$="${benchmark}"],[data-parent="${benchmark}"]`).css('display', '');
        }
        setBreadCrumbs($(`[data-benchmark="${benchmark.replace('_v0', '')}"]`))
    }

    function setBreadCrumbs(target) {
        if (!target.data() || target.data() && target.data().benchmark === `average_${domain}`) {
            $('.leaderboard-breadcrumb').html('');
            return;
        }

        let breadcrumb = `<span class="breadcrumb-link cursor--pointer">${target.data().benchmark}</span>`;

        if (target.data().benchmark === `engineering_${domain}`) {
            breadcrumb = `<span class="breadcrumb-link cursor--pointer">average_${domain}</span> > ` + breadcrumb;
        }
        while (target.data().parent !== 'None') {
            target = $(`[data-benchmark="${target.data().parent.replace('_v0', '')}"]`);
            breadcrumb = `<span class="breadcrumb-link cursor--pointer">${target.data().benchmark}</span> > ` + breadcrumb;

            if (target.data().benchmark === `engineering_${domain}`) {
                breadcrumb = `<span class="breadcrumb-link cursor--pointer">average_${domain}</span> > ` + breadcrumb;
            }
        }


        $('.leaderboard-breadcrumb').html(breadcrumb);

        // add click handlers to the newly created breadcrumbs
        $('.breadcrumb-link').click((event) => {
            // toggle all the open columns back to their closed state
            $('.benchmark-count').removeClass('open');

            onClickExpandCollapseBenchmark({
                type: 'breadcrumb-click',
                currentTarget: $(`[data-benchmark="${event.currentTarget.innerText}"]`)[0]
            });
        });
    }
    // Function to update the URL and send a pageview to Google Analytics
    function updateUrl(newUrl) {
        // Update the URL without reloading the page
        history.pushState(null, '', newUrl);

        // Send a pageview event to Google Analytics
        gtag('config', GTAG_ID, {
            'page_path': newUrl
        });
    }
});
