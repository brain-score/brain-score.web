(function (root, factory) {
    'use strict';

    var core = factory();
    if (typeof module === 'object' && module.exports) module.exports = core;
    root.CompareModelDifferenceTreeCore = core;

    function initialize() {
        if (!root.document || !root.compare_dashboard_data) return;
        if (!root.document.getElementById('model-difference-tree-panel')) return;
        root.CompareModelDifferenceTree = core.createDifferenceTree(
            root.compare_dashboard_data,
            root.document
        );
    }

    if (root.document) {
        if (root.document.readyState === 'loading') {
            root.document.addEventListener('DOMContentLoaded', initialize);
        } else {
            initialize();
        }
    }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';

    function displayLabel(benchmark) {
        var labels = {
            average_vision: 'Vision',
            neural_vision: 'Neural',
            behavior_vision: 'Behavioral',
            average_language: 'Language',
            neural_language: 'Neural',
            behavior_language: 'Behavioral'
        };
        return labels[benchmark.type_id] || benchmark.label || benchmark.type_id;
    }

    function buildDifferenceTree(benchmarks, sharedScores) {
        var byId = {};
        var childrenById = {};
        var parentById = {};
        var scoreById = {};
        (benchmarks || []).forEach(function (benchmark) {
            byId[benchmark.id] = benchmark;
            childrenById[benchmark.id] = [];
        });
        (benchmarks || []).forEach(function (benchmark) {
            if (benchmark.parent_id && childrenById[benchmark.parent_id]) {
                childrenById[benchmark.parent_id].push(benchmark.id);
                parentById[benchmark.id] = benchmark.parent_id;
            }
        });
        (sharedScores || []).forEach(function (score) { scoreById[score.benchId] = score; });

        function buildNode(benchmarkId, depth) {
            var benchmark = byId[benchmarkId];
            if (!benchmark || benchmark.is_engineering) return null;
            var childNodes = (childrenById[benchmarkId] || []).map(function (childId) {
                return buildNode(childId, depth + 1);
            }).filter(function (node) { return node !== null; });
            var scoreA;
            var scoreB;
            var leafCount;
            if (benchmark.is_leaf) {
                var score = scoreById[benchmark.id];
                if (!score) return null;
                scoreA = Number(score.scoreA);
                scoreB = Number(score.scoreB);
                leafCount = 1;
            } else {
                if (!childNodes.length) return null;
                scoreA = childNodes.reduce(function (sum, child) { return sum + child.scoreA; }, 0) / childNodes.length;
                scoreB = childNodes.reduce(function (sum, child) { return sum + child.scoreB; }, 0) / childNodes.length;
                leafCount = childNodes.reduce(function (sum, child) { return sum + child.leafCount; }, 0);
            }
            return {
                id: benchmark.id,
                label: displayLabel(benchmark),
                typeId: benchmark.type_id,
                depth: depth,
                isLeaf: !!benchmark.is_leaf,
                scoreA: scoreA,
                scoreB: scoreB,
                diff: scoreA - scoreB,
                leafCount: leafCount,
                children: childNodes
            };
        }

        return (benchmarks || []).filter(function (benchmark) {
            return !parentById[benchmark.id] && !benchmark.is_engineering;
        }).map(function (benchmark) {
            return buildNode(benchmark.id, 0);
        }).filter(function (node) { return node !== null; });
    }

    function flattenTree(nodes) {
        var flattened = [];
        function visit(node, parentLabel) {
            flattened.push({
                benchmark: node.label,
                parent: parentLabel || '',
                level: node.depth,
                sharedLeaves: node.leafCount,
                scoreA: node.scoreA,
                scoreB: node.scoreB,
                difference: node.diff
            });
            node.children.forEach(function (child) { visit(child, node.label); });
        }
        (nodes || []).forEach(function (node) { visit(node, ''); });
        return flattened;
    }

    function defaultCollapsed(node) {
        return node.depth >= 2 || String(node.typeId).indexOf('behavior_') === 0;
    }

    function escapeCsv(value) {
        var text = String(value === null || value === undefined ? '' : value);
        return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    }

    function differenceTreeToCsv(nodes, modelA, modelB) {
        var rows = [[
            'benchmark', 'parent', 'tree_level', 'shared_leaves',
            modelA || 'model_a', modelB || 'model_b', 'difference'
        ]];
        flattenTree(nodes).forEach(function (row) {
            rows.push([
                row.benchmark, row.parent, row.level, row.sharedLeaves,
                row.scoreA, row.scoreB, row.difference
            ]);
        });
        return rows.map(function (row) { return row.map(escapeCsv).join(','); }).join('\n');
    }

    function createElement(document, tagName, className, text) {
        var element = document.createElement(tagName);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function downloadCsv(document, csv) {
        var browserRoot = document.defaultView || {};
        var blob = new browserRoot.Blob([csv], {type: 'text/csv;charset=utf-8'});
        var url = browserRoot.URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'brain-score-model-difference-tree.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        browserRoot.URL.revokeObjectURL(url);
    }

    function createDifferenceTree(payload, document) {
        var container = document.getElementById('model-difference-tree');
        var empty = document.getElementById('model-difference-tree-empty');
        var summary = document.getElementById('model-difference-tree-summary');
        var modelALabel = document.getElementById('model-difference-tree-a-label');
        var modelBLabel = document.getElementById('model-difference-tree-b-label');
        var download = document.getElementById('model-difference-tree-download-csv');
        var latestTree = [];
        var latestDetail = {};

        function render(detail) {
            latestDetail = detail || {};
            latestTree = buildDifferenceTree(payload.benchmarks, latestDetail.data || []);
            container.innerHTML = '';
            var hasData = latestTree.length > 0;
            var sharedLeaves = latestTree.reduce(function (sum, node) {
                return sum + node.leafCount;
            }, 0);
            container.style.display = hasData ? '' : 'none';
            if (empty) empty.style.display = hasData ? 'none' : '';
            if (summary) {
                summary.textContent = hasData
                    ? sharedLeaves + ' shared non-engineering benchmark leaves; parent scores use equal-weighted child aggregation.'
                    : '';
            }
            if (modelALabel) modelALabel.textContent = latestDetail.nameA || 'Model A';
            if (modelBLabel) modelBLabel.textContent = latestDetail.nameB || 'Model B';
            if (!hasData) return;

            var allNodes = flattenTree(latestTree);
            var maximumDifference = Math.max.apply(null, allNodes.map(function (node) {
                return Math.abs(node.difference);
            }).concat([0.001]));

            function renderNode(node) {
                var item = createElement(document, 'li', 'model-difference-node');
                var row = createElement(document, 'div', 'model-difference-node-row');
                var childrenList = null;
                if (node.children.length) {
                    var toggle = createElement(document, 'button', 'model-difference-toggle', '\u25bc');
                    toggle.type = 'button';
                    toggle.setAttribute('aria-expanded', 'true');
                    toggle.setAttribute('aria-label', 'Collapse ' + node.label);
                    row.appendChild(toggle);
                    childrenList = createElement(document, 'ul', 'model-difference-tree-list');
                    node.children.forEach(function (child) { childrenList.appendChild(renderNode(child)); });
                    if (defaultCollapsed(node)) {
                        childrenList.style.display = 'none';
                        toggle.textContent = '\u25b6';
                        toggle.setAttribute('aria-expanded', 'false');
                        toggle.setAttribute('aria-label', 'Expand ' + node.label);
                    }
                    toggle.addEventListener('click', function () {
                        var collapsed = childrenList.style.display !== 'none';
                        childrenList.style.display = collapsed ? 'none' : '';
                        toggle.textContent = collapsed ? '\u25b6' : '\u25bc';
                        toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                        toggle.setAttribute('aria-label', (collapsed ? 'Expand ' : 'Collapse ') + node.label);
                    });
                } else {
                    row.appendChild(createElement(document, 'span', 'model-difference-toggle-spacer'));
                }

                var label = createElement(document, 'span', 'model-difference-node-label', node.label);
                label.title = node.label;
                row.appendChild(label);
                row.appendChild(createElement(
                    document,
                    'span',
                    'model-difference-leaf-count',
                    node.leafCount + (node.leafCount === 1 ? ' leaf' : ' leaves')
                ));

                var track = createElement(document, 'span', 'model-difference-track');
                track.appendChild(createElement(document, 'span', 'model-difference-center-line'));
                var magnitude = Math.abs(node.diff) / maximumDifference * 50;
                var barClass = node.diff >= 0 ? 'is-model-a' : 'is-model-b';
                var bar = createElement(document, 'span', 'model-difference-bar ' + barClass);
                bar.style.width = magnitude + '%';
                if (node.diff >= 0) bar.style.left = '50%';
                else bar.style.right = '50%';
                track.appendChild(bar);
                row.appendChild(track);

                var value = createElement(
                    document,
                    'span',
                    'model-difference-value ' + barClass,
                    (node.diff >= 0 ? '+' : '') + node.diff.toFixed(3)
                );
                value.title = (latestDetail.nameA || 'Model A') + ': ' + node.scoreA.toFixed(3) +
                    '; ' + (latestDetail.nameB || 'Model B') + ': ' + node.scoreB.toFixed(3);
                row.appendChild(value);
                item.appendChild(row);
                if (childrenList) item.appendChild(childrenList);
                return item;
            }

            var list = createElement(document, 'ul', 'model-difference-tree-list is-root');
            latestTree.forEach(function (node) { list.appendChild(renderNode(node)); });
            container.appendChild(list);
        }

        document.addEventListener('compare-models:change', function (event) {
            render(event.detail || {});
        });
        if (download) download.addEventListener('click', function () {
            if (!latestTree.length) return;
            downloadCsv(document, differenceTreeToCsv(
                latestTree,
                latestDetail.nameA,
                latestDetail.nameB
            ));
        });
        var browserRoot = document.defaultView || {};
        if (browserRoot.CompareModelsCurrent) render(browserRoot.CompareModelsCurrent);

        return {getTree: function () { return latestTree.slice(); }};
    }

    return {
        buildDifferenceTree: buildDifferenceTree,
        createDifferenceTree: createDifferenceTree,
        defaultCollapsed: defaultCollapsed,
        differenceTreeToCsv: differenceTreeToCsv,
        displayLabel: displayLabel,
        flattenTree: flattenTree
    };
}));
