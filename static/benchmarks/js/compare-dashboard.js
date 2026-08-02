(function (root, factory) {
    'use strict';

    var core = factory();
    if (typeof module === 'object' && module.exports) {
        module.exports = core;
    }
    root.CompareDashboardCore = core;

    if (root.document && root.compare_dashboard_data) {
        root.CompareDashboard = core.createDashboard(root.compare_dashboard_data, root);
        core.initializeDashboardUi(root);
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function parseTimestamp(value) {
        if (!value) return null;
        var timestamp = new Date(value).getTime();
        return Number.isFinite(timestamp) ? timestamp : null;
    }

    function endOfUtcDay(value) {
        if (!value) return null;
        var dateOnly = String(value).slice(0, 10);
        var timestamp = new Date(dateOnly + 'T23:59:59.999Z').getTime();
        return Number.isFinite(timestamp) ? timestamp : null;
    }

    function dateToUtcDay(value) {
        if (!value) return null;
        var dateOnly = String(value).slice(0, 10);
        var timestamp = new Date(dateOnly + 'T00:00:00.000Z').getTime();
        return Number.isFinite(timestamp) ? Math.floor(timestamp / 86400000) : null;
    }

    function utcDayToDate(value) {
        var day = Number(value);
        if (!Number.isFinite(day)) return '';
        return new Date(day * 86400000).toISOString().slice(0, 10);
    }

    function numericScore(value) {
        if (value === null || value === undefined || value === '') return null;
        if (typeof value === 'string' && value.trim().toLowerCase() === 'x') return null;
        var number = Number(value);
        return Number.isFinite(number) ? number : null;
    }

    function defaultComparisonBenchmarkTypes(domain) {
        var normalizedDomain = String(domain || '').trim();
        if (!normalizedDomain) return [];
        return ['neural_' + normalizedDomain, 'behavior_' + normalizedDomain];
    }

    function activeVersionAt(benchmark, cutoffMs) {
        var versions = (benchmark.versions || []).slice().sort(function (a, b) {
            return Number(b.version) - Number(a.version);
        });
        if (!versions.length) return null;
        var starts = versions.map(function (version) {
            return parseTimestamp(version.valid_from);
        }).filter(function (timestamp) {
            return timestamp !== null;
        });
        var firstStart = starts.length ? Math.min.apply(null, starts) : null;
        if (firstStart !== null && cutoffMs < firstStart) return null;
        return versions[0];
    }

    function benchmarkDepth(benchmark, benchmarkById) {
        var depth = 0;
        var current = benchmark;
        var visited = {};
        while (current && current.parent_id && !visited[current.id]) {
            visited[current.id] = true;
            depth += 1;
            current = benchmarkById[current.parent_id];
        }
        return depth;
    }

    function median(values) {
        if (!values.length) return null;
        var sorted = values.slice().sort(function (a, b) { return a - b; });
        var middle = Math.floor(sorted.length / 2);
        if (sorted.length % 2) return sorted[middle];
        return (sorted[middle - 1] + sorted[middle]) / 2;
    }

    function filterRowsByCompleteness(rows, minimumCompleteness) {
        var minimum = Math.max(0, Math.min(100, Number(minimumCompleteness) || 0));
        return (rows || []).filter(function (row) {
            return Number(row.completeness) >= minimum;
        });
    }

    function topRankedModelIds(rows, limit) {
        var maximum = Math.max(0, Number(limit) || 0);
        return (rows || []).filter(function (row) {
            var rank = Number(row.rank);
            return Number.isFinite(rank) && rank > 0;
        }).sort(function (left, right) {
            return Number(left.rank) - Number(right.rank) ||
                String(left.model).localeCompare(String(right.model)) ||
                String(left.model_id).localeCompare(String(right.model_id));
        }).slice(0, maximum).map(function (row) {
            return row.model_id;
        });
    }

    function completenessLeavesForSelection(
        benchmarks,
        benchmarkById,
        childrenById,
        activeBenchmarkIds,
        comparisonBenchmarkIds
    ) {
        var selectedIds = Array.isArray(comparisonBenchmarkIds)
            ? comparisonBenchmarkIds.filter(function (benchmarkId) { return !!benchmarkId; })
            : [];
        if (!selectedIds.length) {
            return benchmarks.filter(function (benchmark) {
                return benchmark.is_leaf && !benchmark.is_engineering && activeBenchmarkIds[benchmark.id];
            });
        }

        var selectedLeafIds = {};
        function addActiveLeaves(benchmarkId, visited) {
            var benchmark = benchmarkById[benchmarkId];
            if (!benchmark || !activeBenchmarkIds[benchmarkId] || visited[benchmarkId]) return;
            visited[benchmarkId] = true;
            if (benchmark.is_leaf) {
                if (!benchmark.is_engineering) selectedLeafIds[benchmarkId] = true;
                return;
            }
            (childrenById[benchmarkId] || []).forEach(function (childId) {
                addActiveLeaves(childId, visited);
            });
        }
        selectedIds.forEach(function (benchmarkId) {
            addActiveLeaves(benchmarkId, {});
        });
        return benchmarks.filter(function (benchmark) {
            return !!selectedLeafIds[benchmark.id];
        });
    }

    function resolveCohort(payload, state) {
        payload = payload || {benchmarks: [], models: []};
        state = state || {};
        var cutoffMs = endOfUtcDay(state.asOfDate);
        if (cutoffMs === null) {
            cutoffMs = Number(payload.datetime_range && payload.datetime_range.max_unix) * 1000;
        }
        var minimumCompleteness = Math.max(0, Math.min(100, Number(state.minimumCompleteness) || 0));
        var benchmarks = payload.benchmarks || [];
        var benchmarkById = {};
        var childrenById = {};
        benchmarks.forEach(function (benchmark) {
            benchmarkById[benchmark.id] = benchmark;
            childrenById[benchmark.id] = [];
        });
        benchmarks.forEach(function (benchmark) {
            if (benchmark.parent_id && childrenById[benchmark.parent_id]) {
                childrenById[benchmark.parent_id].push(benchmark.id);
            }
        });

        var activeVersionById = {};
        var activeBenchmarkIds = {};
        benchmarks.forEach(function (benchmark) {
            if (!benchmark.is_leaf) return;
            var version = activeVersionAt(benchmark, cutoffMs);
            if (!version) return;
            activeVersionById[benchmark.id] = version;
            activeBenchmarkIds[benchmark.id] = true;
        });

        var parentsByDepth = benchmarks.filter(function (benchmark) {
            return !benchmark.is_leaf;
        }).sort(function (a, b) {
            return benchmarkDepth(b, benchmarkById) - benchmarkDepth(a, benchmarkById);
        });
        parentsByDepth.forEach(function (benchmark) {
            var hasActiveChild = (childrenById[benchmark.id] || []).some(function (childId) {
                return !!activeBenchmarkIds[childId];
            });
            if (hasActiveChild) activeBenchmarkIds[benchmark.id] = true;
        });

        var completenessLeaves = completenessLeavesForSelection(
            benchmarks,
            benchmarkById,
            childrenById,
            activeBenchmarkIds,
            state.comparisonBenchmarkIds
        );

        var availableRows = [];
        (payload.models || []).forEach(function (model) {
            var submittedAt = parseTimestamp(model.submission_timestamp);
            if (submittedAt !== null && submittedAt > cutoffMs) return;

            var row = {
                model_id: model.id,
                model: model.name,
                rank: model.rank,
                submission_timestamp: model.submission_timestamp
            };

            benchmarks.forEach(function (benchmark) {
                if (!benchmark.is_leaf || !activeBenchmarkIds[benchmark.id]) return;
                var activeVersion = activeVersionById[benchmark.id];
                var versions = (model.scores && model.scores[benchmark.type_id]) || [];
                var score = null;
                for (var i = 0; i < versions.length; i++) {
                    if (Number(versions[i].version) === Number(activeVersion.version)) {
                        score = versions[i];
                        break;
                    }
                }

                var value = score ? numericScore(score.value) : null;
                var scoredVersions = versions.filter(function (versionScore) {
                    return numericScore(versionScore.value) !== null;
                });
                var hasUnknownTimestamp = scoredVersions.some(function (versionScore) {
                    return parseTimestamp(versionScore.timestamp) === null;
                });
                var scoreTimestamps = scoredVersions.map(function (versionScore) {
                    return parseTimestamp(versionScore.timestamp);
                }).filter(function (timestamp) {
                    return timestamp !== null;
                });
                var recordedAt = hasUnknownTimestamp || !scoreTimestamps.length
                    ? null
                    : Math.min.apply(null, scoreTimestamps);
                if (recordedAt !== null && recordedAt > cutoffMs) value = null;

                row[benchmark.id + '-score'] = value === null ? '' : value;
                row[benchmark.id + '-error'] = score ? score.error : null;
                row[benchmark.id + '-is_complete'] = value === null ? 0 : 1;
                row[benchmark.id + '-active_version'] = activeVersion.version;
            });

            parentsByDepth.forEach(function (benchmark) {
                if (!activeBenchmarkIds[benchmark.id]) return;
                var activeChildren = (childrenById[benchmark.id] || []).filter(function (childId) {
                    return !!activeBenchmarkIds[childId];
                });
                var values = activeChildren.map(function (childId) {
                    return numericScore(row[childId + '-score']);
                });
                var hasValidValue = values.some(function (value) { return value !== null; });
                if (!hasValidValue || !activeChildren.length) {
                    row[benchmark.id + '-score'] = '';
                    row[benchmark.id + '-error'] = null;
                    row[benchmark.id + '-is_complete'] = 0;
                    return;
                }
                var total = values.reduce(function (sum, value) {
                    return sum + (value === null ? 0 : value);
                }, 0);
                row[benchmark.id + '-score'] = total / activeChildren.length;
                row[benchmark.id + '-error'] = null;
                row[benchmark.id + '-is_complete'] = 1;
            });

            var completed = completenessLeaves.reduce(function (count, benchmark) {
                var value = numericScore(row[benchmark.id + '-score']);
                return count + (value !== null && value > 0 ? 1 : 0);
            }, 0);
            row.completeness = completenessLeaves.length
                ? Math.round((completed / completenessLeaves.length) * 1000) / 10
                : 0;
            availableRows.push(row);
        });

        var rows = filterRowsByCompleteness(availableRows, minimumCompleteness);
        var aggregateBenchmark = benchmarks.find(function (benchmark) {
            return benchmark.type_id === 'average_' + payload.domain;
        });
        if (aggregateBenchmark) {
            var rankable = rows.slice().sort(function (left, right) {
                var leftScore = numericScore(left[aggregateBenchmark.id + '-score']);
                var rightScore = numericScore(right[aggregateBenchmark.id + '-score']);
                if (leftScore === null && rightScore === null) return String(left.model).localeCompare(String(right.model));
                if (leftScore === null) return 1;
                if (rightScore === null) return -1;
                return rightScore - leftScore || String(left.model).localeCompare(String(right.model));
            });
            var lastScore = null;
            var lastRank = 0;
            rankable.forEach(function (row, index) {
                var score = numericScore(row[aggregateBenchmark.id + '-score']);
                if (score === null) {
                    row.rank = null;
                } else if (lastScore !== null && score === lastScore) {
                    row.rank = lastRank;
                } else {
                    row.rank = index + 1;
                    lastRank = row.rank;
                    lastScore = score;
                }
            });
        }
        var eligibleIds = {};
        rows.forEach(function (row) { eligibleIds[String(row.model_id)] = true; });

        return {
            cutoffMs: cutoffMs,
            minimumCompleteness: minimumCompleteness,
            rows: rows,
            availableRows: availableRows,
            eligibleIds: eligibleIds,
            activeBenchmarkIds: activeBenchmarkIds,
            activeVersionById: activeVersionById,
            benchmarkById: benchmarkById,
            completenessBenchmarkIds: completenessLeaves.map(function (benchmark) { return benchmark.id; }),
            completenessBenchmarkCount: completenessLeaves.length,
            activeLeafCount: Object.keys(activeVersionById).length,
            medianCompleteness: median(rows.map(function (row) { return row.completeness; }))
        };
    }

    function dateFromUnix(seconds) {
        if (!seconds) return '';
        return new Date(Number(seconds) * 1000).toISOString().slice(0, 10);
    }

    function clampDate(dateValue, minimum, maximum) {
        if (!dateValue) return maximum;
        return dateValue < minimum ? minimum : (dateValue > maximum ? maximum : dateValue);
    }

    function createDashboard(payload, browserRoot) {
        var range = payload.datetime_range || {};
        var minimumDate = String(range.min || dateFromUnix(range.min_unix)).slice(0, 10);
        var maximumDate = String(range.max || dateFromUnix(range.max_unix)).slice(0, 10);
        var params = new browserRoot.URLSearchParams(browserRoot.location.search);
        var state = {
            asOfDate: clampDate(params.get('as_of'), minimumDate, maximumDate),
            minimumCompleteness: 0,
            comparisonBenchmarkIds: []
        };
        var resolved = resolveCohort(payload, state);
        var latestResolved = state.asOfDate === maximumDate && state.minimumCompleteness === 0
            ? resolved
            : resolveCohort(payload, {
                asOfDate: maximumDate,
                minimumCompleteness: 0
            });
        var subscribers = [];

        function updateUrl() {
            var current = new browserRoot.URL(browserRoot.location.href);
            if (state.asOfDate === maximumDate) current.searchParams.delete('as_of');
            else current.searchParams.set('as_of', state.asOfDate);
            current.searchParams.delete('min_complete');
            browserRoot.history.replaceState({}, '', current.pathname + current.search + current.hash);
        }

        function notify() {
            resolved = resolveCohort(payload, state);
            browserRoot.comparison_data = resolved.rows;
            updateUrl();
            subscribers.slice().forEach(function (subscriber) {
                subscriber(resolved, getState());
            });
            if (browserRoot.document && typeof browserRoot.CustomEvent === 'function') {
                browserRoot.document.dispatchEvent(new browserRoot.CustomEvent(
                    'compare-dashboard:change',
                    {detail: {resolved: resolved, state: getState()}}
                ));
            }
        }

        function getState() {
            return {
                asOfDate: state.asOfDate,
                minimumCompleteness: state.minimumCompleteness,
                comparisonBenchmarkIds: state.comparisonBenchmarkIds.slice(),
                cutoffMs: resolved.cutoffMs
            };
        }

        var api = {
            getState: getState,
            getResolved: function () { return resolved; },
            getComparisonData: function () { return resolved.rows; },
            getLatestComparisonData: function () { return latestResolved.rows; },
            getTopRankedModelIds: function (limit) {
                return topRankedModelIds(latestResolved.rows, limit);
            },
            getAvailableData: function () { return resolved.availableRows; },
            getEligibleModels: function () {
                return resolved.rows.map(function (row) {
                    return {id: row.model_id, name: row.model, completeness: row.completeness};
                });
            },
            getRow: function (modelId) {
                var wanted = String(modelId);
                for (var i = 0; i < resolved.rows.length; i++) {
                    if (String(resolved.rows[i].model_id) === wanted) return resolved.rows[i];
                }
                return null;
            },
            getLatestRow: function (modelId) {
                var wanted = String(modelId);
                for (var i = 0; i < latestResolved.rows.length; i++) {
                    if (String(latestResolved.rows[i].model_id) === wanted) return latestResolved.rows[i];
                }
                return null;
            },
            isBenchmarkActive: function (benchmarkId) {
                return !!resolved.activeBenchmarkIds[benchmarkId];
            },
            getBenchmarkTypeId: function (benchmarkId) {
                var benchmark = resolved.benchmarkById[benchmarkId];
                return benchmark ? benchmark.type_id : null;
            },
            getBenchmarkIdByTypeId: function (typeId) {
                var benchmarkIds = Object.keys(resolved.benchmarkById);
                for (var i = 0; i < benchmarkIds.length; i++) {
                    var benchmark = resolved.benchmarkById[benchmarkIds[i]];
                    if (benchmark.type_id === typeId) return benchmark.id;
                }
                return null;
            },
            isLeafBenchmark: function (benchmarkId) {
                var benchmark = resolved.benchmarkById[benchmarkId];
                return !!(benchmark && benchmark.is_leaf);
            },
            getActiveVersion: function (benchmarkId) {
                var version = resolved.activeVersionById[benchmarkId];
                return version ? version.version : null;
            },
            setAsOfDate: function (dateValue) {
                var next = clampDate(String(dateValue || '').slice(0, 10), minimumDate, maximumDate);
                if (next === state.asOfDate) return;
                state.asOfDate = next;
                notify();
            },
            setMinimumCompleteness: function (value) {
                var next = Math.max(0, Math.min(100, Number(value) || 0));
                if (next === state.minimumCompleteness) return;
                state.minimumCompleteness = next;
                notify();
            },
            setComparisonBenchmarks: function (firstBenchmarkId, secondBenchmarkId) {
                var requested = Array.isArray(firstBenchmarkId)
                    ? firstBenchmarkId
                    : [firstBenchmarkId, secondBenchmarkId];
                var seen = {};
                var next = requested.filter(function (benchmarkId) {
                    if (!benchmarkId || seen[benchmarkId]) return false;
                    seen[benchmarkId] = true;
                    return true;
                });
                var unchanged = next.length === state.comparisonBenchmarkIds.length && next.every(function (benchmarkId, index) {
                    return benchmarkId === state.comparisonBenchmarkIds[index];
                });
                if (unchanged) return;
                state.comparisonBenchmarkIds = next;
                notify();
            },
            reset: function () {
                state.asOfDate = maximumDate;
                state.minimumCompleteness = 0;
                notify();
            },
            subscribe: function (subscriber) {
                subscribers.push(subscriber);
                subscriber(resolved, getState());
                return function () {
                    subscribers = subscribers.filter(function (item) { return item !== subscriber; });
                };
            },
            setUrlParam: function (key, value) {
                var current = new browserRoot.URL(browserRoot.location.href);
                if (value === null || value === undefined || value === '') current.searchParams.delete(key);
                else current.searchParams.set(key, String(value));
                browserRoot.history.replaceState({}, '', current.pathname + current.search + current.hash);
            },
            getUrlParam: function (key) { return params.get(key); },
            minimumDate: minimumDate,
            maximumDate: maximumDate
        };

        browserRoot.comparison_data = resolved.rows;
        updateUrl();
        return api;
    }

    function renderHistogram(container, rows) {
        if (!container) return;
        var bins = [
            {label: '0-24%', min: 0, max: 25},
            {label: '25-49%', min: 25, max: 50},
            {label: '50-74%', min: 50, max: 75},
            {label: '75-99%', min: 75, max: 100},
            {label: '100%', min: 100, max: 101}
        ];
        var counts = bins.map(function (bin) {
            return rows.filter(function (row) {
                return row.completeness >= bin.min && row.completeness < bin.max;
            }).length;
        });
        var maximum = Math.max.apply(null, counts.concat([1]));
        container.innerHTML = bins.map(function (bin, index) {
            var width = Math.round((counts[index] / maximum) * 100);
            return '<div class="compare-completeness-bin">' +
                '<span class="compare-completeness-label">' + bin.label + '</span>' +
                '<span class="compare-completeness-track"><span style="width:' + width + '%"></span></span>' +
                '<span class="compare-completeness-count">' + counts[index] + '</span>' +
                '</div>';
        }).join('');
    }

    function initializeDashboardUi(browserRoot) {
        var dashboard = browserRoot.CompareDashboard;
        var document = browserRoot.document;
        if (!dashboard || !document.getElementById('compare-dashboard')) return;

        var waybackRange = document.getElementById('compare-wayback-range');
        var waybackValue = document.getElementById('compare-wayback-value');
        var waybackMinLabel = document.getElementById('compare-wayback-min-label');
        var completenessRange = document.getElementById('compare-completeness-range');
        var completenessNumber = document.getElementById('compare-completeness-number');
        var resetButton = document.getElementById('compare-dashboard-reset');

        var minimumDay = dateToUtcDay(dashboard.minimumDate);
        var maximumDay = dateToUtcDay(dashboard.maximumDate);
        function renderWaybackValue(day) {
            var date = utcDayToDate(day);
            if (waybackValue) waybackValue.textContent = date;
            if (waybackRange) waybackRange.setAttribute('aria-valuetext', date);
            return date;
        }
        var waybackTimer = null;
        if (waybackRange && minimumDay !== null && maximumDay !== null) {
            waybackRange.min = String(minimumDay);
            waybackRange.max = String(maximumDay);
            waybackRange.step = '1';
            waybackRange.addEventListener('input', function () {
                renderWaybackValue(waybackRange.value);
                clearTimeout(waybackTimer);
                waybackTimer = setTimeout(function () {
                    dashboard.setAsOfDate(utcDayToDate(waybackRange.value));
                }, 120);
            });
            waybackRange.addEventListener('change', function () {
                clearTimeout(waybackTimer);
                dashboard.setAsOfDate(renderWaybackValue(waybackRange.value));
            });
        }
        if (waybackMinLabel) waybackMinLabel.textContent = dashboard.minimumDate;
        var completenessTimer = null;
        if (completenessRange) completenessRange.addEventListener('input', function () {
            if (completenessNumber) completenessNumber.value = completenessRange.value;
            clearTimeout(completenessTimer);
            completenessTimer = setTimeout(function () {
                dashboard.setMinimumCompleteness(completenessRange.value);
            }, 120);
        });
        if (completenessRange) completenessRange.addEventListener('change', function () {
            clearTimeout(completenessTimer);
            dashboard.setMinimumCompleteness(completenessRange.value);
        });
        if (completenessNumber) completenessNumber.addEventListener('change', function () {
            clearTimeout(completenessTimer);
            dashboard.setMinimumCompleteness(completenessNumber.value);
        });
        if (resetButton) resetButton.addEventListener('click', function () { dashboard.reset(); });

        dashboard.subscribe(function (resolved, state) {
            if (waybackRange) waybackRange.value = String(dateToUtcDay(state.asOfDate));
            renderWaybackValue(dateToUtcDay(state.asOfDate));
            if (completenessRange) completenessRange.value = state.minimumCompleteness;
            if (completenessNumber) completenessNumber.value = state.minimumCompleteness;
            var modelCount = document.getElementById('compare-kpi-models');
            var benchmarkCount = document.getElementById('compare-kpi-benchmarks');
            var dateValue = document.getElementById('compare-kpi-date');
            var medianValue = document.getElementById('compare-kpi-median');
            if (modelCount) modelCount.textContent = String(resolved.rows.length);
            if (benchmarkCount) benchmarkCount.textContent = String(resolved.completenessBenchmarkCount);
            if (dateValue) dateValue.textContent = state.asOfDate;
            if (medianValue) {
                medianValue.textContent = resolved.medianCompleteness === null
                    ? 'Not available'
                    : resolved.medianCompleteness.toFixed(1) + '%';
            }

            renderHistogram(
                document.getElementById('compare-completeness-histogram'),
                resolved.availableRows
            );

            var empty = document.getElementById('compare-dashboard-empty');
            if (empty) empty.style.display = resolved.rows.length ? 'none' : '';
        });
    }

    return {
        activeVersionAt: activeVersionAt,
        completenessLeavesForSelection: completenessLeavesForSelection,
        dateToUtcDay: dateToUtcDay,
        defaultComparisonBenchmarkTypes: defaultComparisonBenchmarkTypes,
        endOfUtcDay: endOfUtcDay,
        filterRowsByCompleteness: filterRowsByCompleteness,
        topRankedModelIds: topRankedModelIds,
        numericScore: numericScore,
        resolveCohort: resolveCohort,
        createDashboard: createDashboard,
        initializeDashboardUi: initializeDashboardUi,
        utcDayToDate: utcDayToDate
    };
}));
