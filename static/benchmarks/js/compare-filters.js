/**
 * Compare page filter module.
 * Manages wayback timestamp slider and benchmark tree for the compare page.
 * Self-contained -- does NOT depend on any leaderboard filter JS.
 *
 * Exposes: window.CompareFilters
 */
$(document).ready(function () {
    if (!document.getElementById('compare-filters-panel')) return;

    // ================================================================
    // STATE
    // ================================================================
    var datetimeRange = window.compare_datetime_range || null;
    var benchmarkTree = window.compare_benchmark_tree || [];

    if (!datetimeRange) return;

    var state = {
        minTimestamp: datetimeRange.min_unix,
        maxTimestamp: datetimeRange.max_unix,
        excludedBenchmarks: {},  // object used as Set (keys = benchmark IDs)
        callbacks: []
    };

    // ================================================================
    // PUBLIC API
    // ================================================================
    function onFilterChange(fn) {
        state.callbacks.push(fn);
    }

    function getFilterState() {
        var excluded = {};
        for (var k in state.excludedBenchmarks) {
            if (state.excludedBenchmarks.hasOwnProperty(k)) {
                excluded[k] = true;
            }
        }
        return {
            maxTimestamp: state.maxTimestamp,
            isWaybackActive: state.maxTimestamp < datetimeRange.max_unix,
            excludedBenchmarks: excluded
        };
    }

    function notifyListeners() {
        var filterState = getFilterState();
        updateFilterBadge(filterState);
        for (var i = 0; i < state.callbacks.length; i++) {
            state.callbacks[i](filterState);
        }
    }

    var debounceTimer = null;
    function debounceNotify() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(notifyListeners, 200);
    }

    // ================================================================
    // FILTER BADGE
    // ================================================================
    function updateFilterBadge(filterState) {
        var badge = document.getElementById('compare-active-filter-count');
        if (!badge) return;

        var count = 0;
        if (filterState.isWaybackActive) count++;
        var excludedCount = 0;
        for (var k in filterState.excludedBenchmarks) {
            if (filterState.excludedBenchmarks.hasOwnProperty(k)) excludedCount++;
        }
        if (excludedCount > 0) count++;

        if (count > 0) {
            badge.textContent = count + ' active';
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }

    // ================================================================
    // WAYBACK SLIDER
    // ================================================================
    function initWaybackSlider() {
        var container = document.getElementById('compareWaybackSlider');
        var dateInput = document.getElementById('compareWaybackDate');
        if (!container || !dateInput) return;

        var min = datetimeRange.min_unix;
        var max = datetimeRange.max_unix;
        var handle = container.querySelector('.handle-max');
        var range = container.querySelector('.slider-range');

        container.dataset.min = min;
        container.dataset.max = max;
        handle.dataset.value = max;

        var minDateStr = new Date(min * 1000).toISOString().split('T')[0];
        var maxDateStr = new Date(max * 1000).toISOString().split('T')[0];
        dateInput.min = minDateStr;
        dateInput.max = maxDateStr;
        dateInput.value = maxDateStr;

        function updateSliderVisual(value) {
            var percent = ((value - min) / (max - min)) * 100;
            handle.style.left = percent + '%';
            range.style.left = '0%';
            range.style.width = percent + '%';
            var d = new Date(value * 1000);
            dateInput.value = d.toISOString().split('T')[0];
        }

        var isDragging = false;

        handle.addEventListener('mousedown', function (e) {
            isDragging = true;
            e.preventDefault();
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });

        function onMouseMove(e) {
            if (!isDragging) return;
            var rect = container.getBoundingClientRect();
            var percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            var value = Math.round(min + percent * (max - min));
            state.maxTimestamp = value;
            handle.dataset.value = value;
            updateSliderVisual(value);
            debounceNotify();
        }

        function onMouseUp() {
            isDragging = false;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }

        dateInput.addEventListener('change', function () {
            var ts = Math.floor(new Date(dateInput.value + 'T23:59:59').getTime() / 1000);
            if (!isNaN(ts)) {
                ts = Math.max(min, Math.min(ts, max));
                state.maxTimestamp = ts;
                handle.dataset.value = ts;
                updateSliderVisual(ts);
                notifyListeners();
            }
        });

        updateSliderVisual(max);
    }

    // ================================================================
    // BENCHMARK TREE
    // ================================================================
    function initBenchmarkTree() {
        var container = document.getElementById('compareBenchmarkTreePanel');
        if (!container || !benchmarkTree.length) return;

        var ul = document.createElement('ul');
        ul.classList.add('compare-benchmark-tree');

        for (var i = 0; i < benchmarkTree.length; i++) {
            ul.appendChild(createNode(benchmarkTree[i]));
        }

        container.appendChild(ul);
    }

    function createNode(node) {
        var li = document.createElement('li');
        li.classList.add('compare-bm-node');

        var header = document.createElement('div');
        header.classList.add('compare-bm-header');

        var hasChildren = node.children && node.children.length > 0;

        if (hasChildren) {
            var toggle = document.createElement('span');
            toggle.classList.add('compare-bm-toggle');
            toggle.textContent = '\u25B6';
            li.classList.add('collapsed');

            toggle.addEventListener('click', (function (liRef, toggleRef) {
                return function (e) {
                    e.stopPropagation();
                    liRef.classList.toggle('collapsed');
                    toggleRef.textContent = liRef.classList.contains('collapsed') ? '\u25B6' : '\u25BC';
                };
            })(li, toggle));

            header.appendChild(toggle);
        } else {
            var spacer = document.createElement('span');
            spacer.classList.add('compare-bm-toggle');
            spacer.innerHTML = '&nbsp;';
            header.appendChild(spacer);
        }

        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = node.id;
        checkbox.checked = true;

        checkbox.addEventListener('change', (function (cbRef, liRef) {
            return function () {
                if (cbRef.checked) {
                    autoSelectAncestors(liRef);
                    checkDescendants(liRef, true);
                } else {
                    checkDescendants(liRef, false);
                }
                rebuildExclusionSet();
                notifyListeners();
            };
        })(checkbox, li));

        var label = document.createElement('label');
        label.appendChild(checkbox);
        var textSpan = document.createElement('span');
        textSpan.textContent = ' ' + node.label;
        label.appendChild(textSpan);
        header.appendChild(label);

        li.appendChild(header);

        if (hasChildren) {
            var childUl = document.createElement('ul');
            childUl.classList.add('compare-benchmark-tree');
            for (var i = 0; i < node.children.length; i++) {
                childUl.appendChild(createNode(node.children[i]));
            }
            li.appendChild(childUl);
        }

        return li;
    }

    function autoSelectAncestors(liElement) {
        var current = liElement;
        while (current) {
            var parentUl = current.parentElement;
            if (!parentUl) break;
            var parentLi = parentUl.parentElement;
            if (!parentLi || !parentLi.classList.contains('compare-bm-node')) break;

            var parentCb = parentLi.querySelector(':scope > .compare-bm-header input[type="checkbox"]');
            if (parentCb && !parentCb.checked) {
                parentCb.checked = true;
            }
            current = parentLi;
        }
    }

    function checkDescendants(liElement, checked) {
        var checkboxes = liElement.querySelectorAll('input[type="checkbox"]');
        for (var i = 0; i < checkboxes.length; i++) {
            checkboxes[i].checked = checked;
        }
    }

    function rebuildExclusionSet() {
        state.excludedBenchmarks = {};
        var checkboxes = document.querySelectorAll('#compareBenchmarkTreePanel input[type="checkbox"]');
        for (var i = 0; i < checkboxes.length; i++) {
            if (!checkboxes[i].checked) {
                state.excludedBenchmarks[checkboxes[i].value] = true;
            }
        }
    }

    // ================================================================
    // RESET
    // ================================================================
    var resetLink = document.getElementById('resetBenchmarkTree');
    if (resetLink) {
        resetLink.addEventListener('click', function (e) {
            e.preventDefault();
            var checkboxes = document.querySelectorAll('#compareBenchmarkTreePanel input[type="checkbox"]');
            for (var i = 0; i < checkboxes.length; i++) {
                checkboxes[i].checked = true;
            }
            state.excludedBenchmarks = {};
            notifyListeners();
        });
    }

    // ================================================================
    // TOGGLE PANEL
    // ================================================================
    var toggleBtn = document.getElementById('toggleCompareFilters');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function () {
            var panel = document.getElementById('compare-filters-panel');
            if (panel) {
                var isHidden = panel.style.display === 'none';
                panel.style.display = isHidden ? '' : 'none';
            }
        });
    }

    // ================================================================
    // INITIALIZATION
    // ================================================================
    initWaybackSlider();
    initBenchmarkTree();

    // ================================================================
    // EXPORT
    // ================================================================
    window.CompareFilters = {
        onFilterChange: onFilterChange,
        getFilterState: getFilterState
    };
});
