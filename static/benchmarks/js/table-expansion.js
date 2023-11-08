$(document).ready(function () {
    // If this element is present we know we're on the updated view
    // TODO - we can remove this condition once we're sure we no longer need the old leaderboard view
    if (document.querySelector('.leaderboard-table-component')) {
        $('th[data-benchmark]').click(handleToggleBenchmarkDisplay);
        return;
    }

    function handleToggleBenchmarkDisplay(event) {
        const benchmarkCount = event.currentTarget.querySelector('.benchmark-count');

        // the column has no children or the user clicked the average column so do nothing
        if (!benchmarkCount || (event.type !== "breadcrumb-click" && event.currentTarget.dataset.benchmark === 'average_vision')) { return; }

        // start by hiding everything
        $('[data-benchmark]').css('display','none');
        // reshow the element that was actually clicked
        event.currentTarget.style.display  = '';

        // toggle the open state
        if ((isClosed = !benchmarkCount.classList.contains('open'))) {
            event.currentTarget.dataset.benchmark !== 'average_vision' && benchmarkCount.classList.add('open');
            stepDown(event);
        } else {
            benchmarkCount.classList.remove('open');
            stepUp(event);
        }

    }

    function stepDown(event) {
        const benchmark = event.currentTarget.dataset.benchmark;
        // the `$=` attribute selector e.g. [attr$=val] matches a suffix
        $(`[data-benchmark$="${benchmark}_v0"],[data-parent="${benchmark}_v0"]`).css('display', '');

        if (event.currentTarget.dataset.benchmark === "average_vision") {
             $('[data-parent="None"]').css('display', '');
        }
        setBreadCrumbs($(event.currentTarget));
    }

    function stepUp(event) {
        const benchmark = event.currentTarget.dataset.parent;
        // special case this so returning back to the main view also expands neural and behavioral columns
        if (event.currentTarget.dataset.depth === '0' || event.currentTarget.dataset.parent === 'average_vision_v0') {
            $('[data-parent="None"],[data-parent="average_vision_v0"]').css('display', '');
        } else {
            $(`[data-benchmark="${benchmark.replace('_v0', '')}"],[data-benchmark$="${benchmark}"],[data-parent="${benchmark}"]`).css('display', '');
        }
        setBreadCrumbs($(`[data-benchmark="${benchmark.replace('_v0', '')}"]`))
    }

    function setBreadCrumbs(target) {
        if (target.data() && (target.data().benchmark === "average_vision")) {
            $('.leaderboard-breadcrumb').html('');
            return;
        }

        let breadcrumb = `<span class="breadcrumb-link cursor--pointer">${target.data().benchmark}</span>`;

        if (target.data().benchmark === "engineering_vision") {
            breadcrumb = `<span class="breadcrumb-link cursor--pointer">average_vision</span> > ` + breadcrumb;
        }
        while (target.data().parent !== 'None') {
            target = $(`[data-benchmark="${target.data().parent.replace('_v0', '')}"]`);
            breadcrumb = `<span class="breadcrumb-link cursor--pointer">${target.data().benchmark}</span> > ` + breadcrumb;

            if (target.data().benchmark === "engineering_vision") {
                breadcrumb = `<span class="breadcrumb-link cursor--pointer">average_vision</span> > ` + breadcrumb;
            }
        }


        $('.leaderboard-breadcrumb').html(breadcrumb);

        $('.breadcrumb-link').click((event) => {
            // toggle all the open columns back to their closed state
            $('.benchmark-count').removeClass('open');

            handleToggleBenchmarkDisplay({
                type: 'breadcrumb-click',
                currentTarget: $(`[data-benchmark="${event.currentTarget.innerText}"]`)[0]
            });
        });
    }

    // TODO - This can all be removed once we're sure we're ready to rip out the old leaderboard

    // This script functions by finding all the elements whose parents the benchmark that is clicked and setting them to
    // visible or invisible. (And doing it recursively for all of its children)
    var coll = document.getElementsByClassName("clicker");
    var i;

    for (i = 0; i < coll.length; i++) {
        // This allows the current value of i to be saved to the assigned function.
        assignFunction(coll, i)
    }

    function recursiveChildren(all_coll) {
        // Performs recursiveChildren on the current benchmark and checking for all of its children and
        // then setting each child's benchmark to be the current benchmark. (Making them invisible in the meantime).
        var used_set = new Set();
        for (var i = 0; i < all_coll.length; i++) {
            const benchmark = all_coll[i].dataset.benchmark;
            if (!used_set.has(benchmark)) {
                used_set.add(all_coll[i].dataset.benchmark)
                changeChildSymbol(benchmark)
                child_coll = document.querySelectorAll(`[data-parent=${CSS.escape(benchmark)}]`);
                for (j = 0; j < child_coll.length; j++) {
                    if (child_coll[j].style.display === "") {
                        child_coll[j].style.display = "none";
                    }
                }
                recursiveChildren(child_coll)
            }
        }
    }

    function assignFunction(coll, i) {
        // Simple hide/show function onClick(). Determines what to show by finding all elements with their
        // data-parent value == the current benchmark.

        coll[i].onclick = function () {
            var j;
            let benchmark = coll[i].dataset.benchmark;
            var all_coll = document.querySelectorAll(`[data-parent=${CSS.escape(benchmark + '_v0')}]`);
            changeParentSymbol(benchmark)
            recursiveChildren(all_coll);
            for (j = 0; j < all_coll.length; j++) {
                if (all_coll[j].style.display === "none") {
                    all_coll[j].style.display = "";
                } else {
                    all_coll[j].style.display = "none";
                }
            }
            var table = document.getElementById("leaderboard");
            table.style.margin = "auto";
        };
    }

    function changeParentSymbol(parentName) {
        // Changes the plus to a minus and a minus to a plus upon clicking the column
        var allParentsExpand = document.getElementsByClassName("headerExpand");
        var allParentContract = document.getElementsByClassName("headerContract");

        for (var i = 0; i < allParentsExpand.length; i++) {
            if (allParentsExpand[i].dataset.benchmark == parentName) {
                allParentsExpand[i].className = "headerContract clicker";
                return null
            }
        }
        for (var i = 0; i < allParentContract.length; i++) {
            if (allParentContract[i].dataset.benchmark == parentName) {
                allParentContract[i].className = "headerExpand clicker";
                return null
            }
        }
    }

    function changeChildSymbol(childName) {
        // Only changes the minus to a plus for the children (since the children shouldn't automatically expand.)
        var allParentContract = document.getElementsByClassName("headerContract");
        for (var i = 0; i < allParentContract.length; i++) {
            if (allParentContract[i].dataset.benchmark == childName) {
                allParentContract[i].className = "headerExpand clicker";
                return null
            }
        }
    }

});
