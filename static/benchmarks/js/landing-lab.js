// Landing page: the cohort builder on the benchmark map, and the toolbox tabs.
// Matching rules mirror leaderboard/filters/filter-coordinator.js so that a cohort
// counted here and the same cohort opened in the leaderboard agree.
(function () {
    'use strict';

    var LEADERBOARD_URL = '/vision/leaderboard/';
    var EXAMPLE_BENCHMARK = 'MajajHong2015public.IT-pls';
    var ARCHITECTURE_LABELS = {
        DCNN: 'Convolutional',
        Transformer: 'Transformer',
        RNN: 'Recurrent',
        SKIP_CONNECTIONS: 'Skip connections'
    };
    // Millions of parameters. min >= 1 because the leaderboard counts a missing
    // parameter count as 0; this keeps undocumented models out.
    var SIZES = [
        {key: 'small', label: '< 25 M', summary: 'under 25 M parameters', min: 1, max: 25},
        {key: 'medium', label: '25–100 M', summary: '25 to 100 M parameters', min: 25, max: 100},
        {key: 'large', label: '> 100 M', summary: 'over 100 M parameters', min: 100, max: null}
    ];
    // Cohorts the map shows in turn until the visitor interacts with the section.
    var PRESETS = [
        {architecture: ['Transformer']},
        {family: ['resnet']},
        {size: 'small'},
        {}
    ];
    var PRESET_INTERVAL_MS = 3500;

    function readJson(id) {
        var element = document.getElementById(id);
        if (!element) return null;
        try {
            return JSON.parse(element.textContent);
        } catch (error) {
            return null;
        }
    }

    function makeCriteria(values) {
        values = values || {};
        return {
            architecture: (values.architecture || []).slice(),
            family: (values.family || []).slice(),
            size: values.size || null
        };
    }

    function counts(pool, field) {
        var tally = {};
        pool.forEach(function (row) {
            row[field].forEach(function (value) { tally[value] = (tally[value] || 0) + 1; });
        });
        return Object.keys(tally)
            .map(function (value) { return {value: value, count: tally[value]}; })
            .sort(function (left, right) { return right.count - left.count; });
    }

    function sizeFor(key) {
        return SIZES.filter(function (size) { return size.key === key; })[0] || null;
    }

    function matches(row, criteria) {
        if (criteria.architecture.length && !row.architecture.some(function (value) {
            return criteria.architecture.indexOf(value) !== -1;
        })) return false;
        if (criteria.family.length && !row.family.some(function (value) {
            return criteria.family.indexOf(value) !== -1;
        })) return false;
        var size = sizeFor(criteria.size);
        if (size) {
            var parameters = row.parameters_m || 0;
            if (parameters < size.min) return false;
            if (size.max !== null && parameters > size.max) return false;
        }
        return true;
    }

    function missingRecord(row, criteria) {
        return (criteria.architecture.length && !row.architecture.length) ||
            (criteria.family.length && !row.family.length) ||
            (criteria.size && !row.parameters_m);
    }

    function describe(criteria) {
        var parts = [];
        if (criteria.architecture.length) {
            parts.push(criteria.architecture.map(function (value) {
                return ARCHITECTURE_LABELS[value] || value;
            }).join(' or '));
        }
        if (criteria.family.length) parts.push('family ' + criteria.family.join(' or '));
        if (criteria.size) parts.push(sizeFor(criteria.size).summary);
        return parts.join(' · ');
    }

    // The leaderboard needs an explicit maximum: with only a minimum in the URL its
    // maximum slider falls back to 100, which empties an "over 100 M" cohort.
    function leaderboardUrl(criteria, largestModel) {
        var params = new URLSearchParams();
        if (criteria.architecture.length) params.set('architecture', criteria.architecture.join(','));
        if (criteria.family.length) params.set('model_family', criteria.family.join(','));
        var size = sizeFor(criteria.size);
        if (size) {
            params.set('min_param_count', String(size.min));
            params.set('max_param_count', String(size.max !== null ? size.max : largestModel));
        }
        var query = params.toString();
        return LEADERBOARD_URL + (query ? '?' + query : '');
    }

    function pythonCode(cohort, criteria) {
        return [
            'import brainscore',
            '',
            '# Cohort: ' + (describe(criteria) || 'every public participant') +
                ' (' + cohort.length + ' participants)',
            'cohort = ['
        ].concat(cohort.map(function (row) { return "    '" + row.name + "',"; }), [
            ']',
            '',
            'for participant in cohort:',
            "    score = brainscore.score(participant, '" + EXAMPLE_BENCHMARK + "')"
        ]).join('\n');
    }

    function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            return navigator.clipboard.writeText(text);
        }
        var area = document.createElement('textarea');
        area.value = text;
        area.style.cssText = 'position:fixed;opacity:0';
        document.body.appendChild(area);
        area.select();
        try { document.execCommand('copy'); } finally { area.remove(); }
        return Promise.resolve();
    }

    function addOption(select, value, label, count) {
        var option = document.createElement('option');
        option.value = value;
        option.textContent = label + ' (' + count + ')';
        select.appendChild(option);
    }

    function leaderboardRow(row) {
        var anchor = document.createElement('a');
        anchor.className = 'landing-leaderboard-row';
        anchor.href = '/model/vision/' + row.id;
        var rank = document.createElement('span');
        rank.className = 'landing-leaderboard-row__rank';
        rank.textContent = row.rank || '–';
        var model = document.createElement('span');
        model.className = 'landing-leaderboard-row__model';
        var name = document.createElement('strong');
        name.textContent = row.name;
        var submitter = document.createElement('span');
        submitter.textContent = row.submitter || '';
        model.append(name, submitter);
        var score = document.createElement('span');
        score.className = 'landing-leaderboard-row__score';
        score.textContent = typeof row.score === 'number' ? row.score.toFixed(3) : '—';
        anchor.append(rank, model, score);
        return anchor;
    }

    function initCohortBuilder(pool) {
        var form = document.getElementById('landing-cohort-form');
        var section = document.getElementById('pool');
        if (!form || !section || !pool.length) return;

        var criteria = makeCriteria();
        var architectureSelect = document.getElementById('landing-cohort-architecture');
        var familySelect = document.getElementById('landing-cohort-family');
        var sizeSelect = document.getElementById('landing-cohort-size');
        var resetButton = form.querySelector('.landing-cohort__reset');
        var space = document.getElementById('landing-benchmark-space');
        var tag = document.getElementById('landing-cohort-tag');
        var title = document.getElementById('landing-leaderboard-title');
        var summary = document.getElementById('landing-cohort-summary');
        var list = document.getElementById('landing-cohort-list');
        var gap = document.getElementById('landing-cohort-gap');
        var link = document.getElementById('landing-cohort-leaderboard');
        var copyButton = document.getElementById('landing-cohort-copy');
        var copyLabel = copyButton.innerHTML;
        var largestModel = Math.ceil(Math.max.apply(null, pool.map(function (row) {
            return row.parameters_m || 0;
        })));
        var cohort = pool;

        counts(pool, 'architecture').forEach(function (item) {
            addOption(architectureSelect, item.value, ARCHITECTURE_LABELS[item.value] || item.value, item.count);
        });
        counts(pool, 'family').forEach(function (item) {
            addOption(familySelect, item.value, item.value, item.count);
        });
        SIZES.forEach(function (size) {
            var count = pool.filter(function (row) {
                return matches(row, makeCriteria({size: size.key}));
            }).length;
            addOption(sizeSelect, size.key, size.label, count);
        });
        // A native select is as wide as its longest option; fit it to the chosen one.
        function fitSelect(select) {
            var probe = document.createElement('span');
            probe.className = select.className;
            probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap';
            probe.textContent = select.options[select.selectedIndex].text;
            select.parentNode.appendChild(probe);
            select.style.width = Math.ceil(probe.getBoundingClientRect().width) + 'px';
            probe.remove();
        }
        architectureSelect.addEventListener('change', function () {
            criteria.architecture = architectureSelect.value ? [architectureSelect.value] : [];
            update();
        });
        familySelect.addEventListener('change', function () {
            criteria.family = familySelect.value ? [familySelect.value] : [];
            update();
        });
        sizeSelect.addEventListener('change', function () {
            criteria.size = sizeSelect.value || null;
            update();
        });

        form.addEventListener('reset', function (event) {
            event.preventDefault();
            criteria = makeCriteria();
            update();
        });

        copyButton.addEventListener('click', function () {
            copyText(pythonCode(cohort, criteria)).then(function () {
                copyButton.textContent = 'Copied ' + cohort.length + ' participants';
                setTimeout(function () { copyButton.innerHTML = copyLabel; }, 1800);
            });
        });

        function update() {
            var active = describe(criteria);
            cohort = pool.filter(function (row) { return matches(row, criteria); })
                .sort(function (left, right) { return (left.rank || 1e9) - (right.rank || 1e9); });
            var members = {};
            cohort.forEach(function (row) { members[row.id] = true; });

            architectureSelect.value = criteria.architecture[0] || '';
            familySelect.value = criteria.family[0] || '';
            sizeSelect.value = criteria.size || '';
            [architectureSelect, familySelect, sizeSelect].forEach(fitSelect);
            resetButton.hidden = !active;

            var onMap = 0;
            if (space) {
                space.classList.toggle('has-cohort', Boolean(active));
                space.querySelectorAll('.landing-space__point').forEach(function (circle) {
                    var included = Boolean(members[circle.dataset.modelId]);
                    circle.classList.toggle('is-in-cohort', included);
                    if (included) onMap += 1;
                });
            }

            tag.textContent = active ? 'Cohort' : 'Live ranking';
            title.textContent = active ? active.charAt(0).toUpperCase() + active.slice(1) : 'Top of the pool';
            summary.textContent = active
                ? cohort.length + ' of ' + pool.length + ' participants; ' + onMap + ' shown on the map.'
                : 'All ' + pool.length + ' public participants.';

            list.textContent = '';
            cohort.slice(0, 5).forEach(function (row) { list.appendChild(leaderboardRow(row)); });
            if (!cohort.length) {
                var empty = document.createElement('p');
                empty.className = 'landing-empty';
                empty.textContent = 'No participant matches these criteria.';
                list.appendChild(empty);
            }

            var missing = active ? pool.filter(function (row) { return missingRecord(row, criteria); }).length : 0;
            gap.textContent = missing
                ? missing + ' participants have no record for these criteria and are left out.'
                : '';
            link.href = leaderboardUrl(criteria, largestModel);
            link.textContent = active ? 'Open this cohort in the leaderboard' : 'Explore the full leaderboard';
            copyButton.disabled = cohort.length === 0;
        }

        update();

        // Show a few cohorts in turn while the section is on screen. The first time
        // the visitor points at, focuses or touches the section, the loop stops for good.
        var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reduceMotion || !('IntersectionObserver' in window)) return;
        var timer = null;
        var preset = 0;
        function showNextPreset() {
            if (document.hidden) return;
            criteria = makeCriteria(PRESETS[preset % PRESETS.length]);
            preset += 1;
            update();
        }
        var observer = new IntersectionObserver(function (entries) {
            if (entries[0].isIntersecting && !timer) {
                showNextPreset();
                timer = setInterval(showNextPreset, PRESET_INTERVAL_MS);
            } else if (!entries[0].isIntersecting && timer) {
                clearInterval(timer);
                timer = null;
            }
        }, {threshold: 0.35});
        observer.observe(section);
        function stop() {
            observer.disconnect();
            clearInterval(timer);
            timer = null;
            ['pointerenter', 'focusin', 'touchstart'].forEach(function (name) {
                section.removeEventListener(name, stop);
            });
        }
        ['pointerenter', 'focusin', 'touchstart'].forEach(function (name) {
            section.addEventListener(name, stop, {passive: true});
        });
    }

    function initToolTabs() {
        var tabs = Array.prototype.slice.call(document.querySelectorAll('.landing-tool-tabs [role="tab"]'));
        function select(tab) {
            tabs.forEach(function (other) {
                var selected = other === tab;
                other.setAttribute('aria-selected', String(selected));
                other.tabIndex = selected ? 0 : -1;
                document.getElementById(other.getAttribute('aria-controls')).hidden = !selected;
            });
        }
        tabs.forEach(function (tab, index) {
            tab.addEventListener('click', function () { select(tab); });
            tab.addEventListener('keydown', function (event) {
                var step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
                if (!step) return;
                var next = tabs[(index + step + tabs.length) % tabs.length];
                select(next);
                next.focus();
            });
        });
    }

    function init() {
        initCohortBuilder(readJson('landing-cohort-pool-data') || []);
        initToolTabs();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
