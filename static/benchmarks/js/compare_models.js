$(document).ready(function () {
    // Guard: only run on the model compare page
    if (document.getElementById('scatter-plot') === null) {
        return;
    }

    var DOMAIN_COLORS = {
        'V1': '#e41a1c',
        'V2': '#ff7f00',
        'V4': '#4daf4a',
        'IT': '#377eb8',
        'Behavioral': '#984ea3',
        'Engineering': '#8c564b',
        'Neural': '#7f7f7f',
        'Average Vision': '#17becf'
    };

    var DOMAIN_ORDER = ['Average Vision', 'Neural', 'V1', 'V2', 'V4', 'IT', 'Behavioral', 'Engineering'];

    // ---- Extract unique model names from comparison_data ----
    function extractModelNames(data) {
        var names = [];
        for (var i = 0; i < data.length; i++) {
            if (data[i].model) {
                names.push(data[i].model);
            }
        }
        return names.sort();
    }

    // ---- Initialize Select2 dropdowns ----
    function initDropdowns(modelNames) {
        var selA = $('#model-x-select');
        var selB = $('#model-y-select');
        selA.empty();
        selB.empty();

        // Add empty placeholder option
        selA.append(new Option('', '', true, true));
        selB.append(new Option('', '', true, true));

        for (var i = 0; i < modelNames.length; i++) {
            selA.append(new Option(modelNames[i], modelNames[i], false, false));
            selB.append(new Option(modelNames[i], modelNames[i], false, false));
        }

        selA.select2({placeholder: 'Select Model A', allowClear: true});
        selB.select2({placeholder: 'Select Model B', allowClear: true});
    }

    // ---- Shorten benchmark name for display ----
    function shortName(benchId) {
        var name = benchId.replace(/_v\d+$/, '');
        var dotIdx = name.indexOf('.');
        if (dotIdx > 0) {
            var prefix = name.substring(0, dotIdx);
            if (prefix === prefix.toLowerCase()) {
                name = name.substring(dotIdx + 1);
            }
        }
        return name;
    }

    // ---- Get benchmarks with valid scores for both models ----
    function getCommonBenchmarks(nameA, nameB) {
        var rowA = null, rowB = null;
        for (var i = 0; i < comparison_data.length; i++) {
            if (comparison_data[i].model === nameA) rowA = comparison_data[i];
            if (comparison_data[i].model === nameB) rowB = comparison_data[i];
            if (rowA && rowB) break;
        }
        if (!rowA || !rowB) return [];

        var results = [];
        var keys = Object.keys(rowA);
        for (var k = 0; k < keys.length; k++) {
            var key = keys[k];
            if (!key.match(/-score$/)) continue;

            var benchId = key.replace(/-score$/, '');
            var completeKey = benchId + '-is_complete';

            if (rowA[completeKey] != 1 || rowB[completeKey] != 1) continue;

            var scoreA = parseFloat(rowA[key]);
            var scoreB = parseFloat(rowB[key]);
            if (isNaN(scoreA) || isNaN(scoreB)) continue;
            if (rowA[key] === '' || rowB[key] === '') continue;

            var domain = (typeof benchmark_domain_map !== 'undefined' && benchmark_domain_map[benchId])
                ? benchmark_domain_map[benchId]
                : 'Unknown';

            results.push({
                benchId: benchId,
                shortName: shortName(benchId),
                scoreA: scoreA,
                scoreB: scoreB,
                diff: scoreA - scoreB,
                domain: domain
            });
        }
        return results;
    }

    // ---- Rank array for Spearman ----
    function rankArray(arr) {
        var indexed = [];
        for (var i = 0; i < arr.length; i++) {
            indexed.push({v: arr[i], i: i});
        }
        indexed.sort(function (a, b) { return a.v - b.v; });
        var ranks = new Array(arr.length);
        var i = 0;
        while (i < indexed.length) {
            var j = i;
            while (j < indexed.length && indexed[j].v === indexed[i].v) j++;
            var avgRank = (i + j + 1) / 2;
            for (var k = i; k < j; k++) {
                ranks[indexed[k].i] = avgRank;
            }
            i = j;
        }
        return ranks;
    }

    // ---- Pearson correlation using jStat for p-value ----
    function pearsonCorrelation(x, y) {
        var n = x.length;
        var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0, sumY2 = 0;
        for (var i = 0; i < n; i++) {
            sumX += x[i];
            sumY += y[i];
            sumXY += x[i] * y[i];
            sumX2 += x[i] * x[i];
            sumY2 += y[i] * y[i];
        }
        var num = n * sumXY - sumX * sumY;
        var den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
        var r = den === 0 ? 0 : num / den;
        var r2 = r * r;
        var t = r * Math.sqrt((n - 2) / (1 - r2));
        var p = 2 * (1 - jStat.studentt.cdf(Math.abs(t), n - 2));
        return {r: r, r2: r2, p: p};
    }

    // ---- Spearman correlation ----
    function spearmanCorrelation(x, y) {
        return pearsonCorrelation(rankArray(x), rankArray(y));
    }

    // ---- Linear regression ----
    function linearRegression(x, y) {
        var n = x.length;
        var sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        for (var i = 0; i < n; i++) {
            sumX += x[i];
            sumY += y[i];
            sumXY += x[i] * y[i];
            sumX2 += x[i] * x[i];
        }
        var slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        var intercept = (sumY - slope * sumX) / n;
        return {slope: slope, intercept: intercept};
    }

    // ---- Compute all statistics ----
    function computeStatistics(data) {
        var x = [], y = [];
        for (var i = 0; i < data.length; i++) {
            x.push(data[i].scoreA);
            y.push(data[i].scoreB);
        }
        var pearson = pearsonCorrelation(x, y);
        var spearman = spearmanCorrelation(x, y);
        var reg = linearRegression(x, y);
        return {
            pearsonR: pearson.r,
            pearsonP: pearson.p,
            r2: pearson.r2,
            spearmanRho: spearman.r,
            spearmanP: spearman.p,
            slope: reg.slope,
            intercept: reg.intercept,
            n: data.length
        };
    }

    function formatPValue(p) {
        if (p < 0.001) return ' (p < 0.001)';
        return ' (p = ' + p.toFixed(3) + ')';
    }

    // ---- Update stats summary bar ----
    function updateStatsSummary(stats) {
        $('#stat-pearson').text(stats.pearsonR.toFixed(3) + formatPValue(stats.pearsonP));
        $('#stat-spearman').text(stats.spearmanRho.toFixed(3) + formatPValue(stats.spearmanP));
        $('#stat-r2').text(stats.r2.toFixed(3));
        $('#stat-n').text(stats.n);
        $('#stats-summary').show();
    }

    // ---- Chart 1: Scatter Plot ----
    function renderScatterPlot(data, stats, nameA, nameB) {
        // Group by domain
        var byDomain = {};
        for (var i = 0; i < data.length; i++) {
            var d = data[i];
            if (!byDomain[d.domain]) byDomain[d.domain] = [];
            byDomain[d.domain].push(d);
        }

        var traces = [];

        // Identity line (y = x)
        traces.push({
            x: [-0.05, 1.05],
            y: [-0.05, 1.05],
            mode: 'lines',
            type: 'scatter',
            name: 'y = x',
            line: {color: '#cccccc', dash: 'dot', width: 1},
            hoverinfo: 'skip',
            showlegend: false
        });

        // Regression line
        var xFit = [0, 1];
        traces.push({
            x: xFit,
            y: [stats.slope * xFit[0] + stats.intercept, stats.slope * xFit[1] + stats.intercept],
            mode: 'lines',
            type: 'scatter',
            name: 'Regression',
            line: {color: '#333333', width: 1.5},
            hoverinfo: 'skip',
            showlegend: false
        });

        // Data points per domain (in canonical order for consistent legend)
        for (var di = 0; di < DOMAIN_ORDER.length; di++) {
            var domain = DOMAIN_ORDER[di];
            var points = byDomain[domain];
            if (!points || points.length === 0) continue;

            traces.push({
                x: points.map(function (p) { return p.scoreA; }),
                y: points.map(function (p) { return p.scoreB; }),
                customdata: points.map(function (p) {
                    return [p.shortName, p.scoreA.toFixed(3), p.scoreB.toFixed(3),
                            (p.diff >= 0 ? '+' : '') + p.diff.toFixed(3)];
                }),
                hovertemplate:
                    '<b>%{customdata[0]}</b><br>' +
                    nameA + ': %{customdata[1]}<br>' +
                    nameB + ': %{customdata[2]}<br>' +
                    'Diff: %{customdata[3]}' +
                    '<extra>' + domain + '</extra>',
                mode: 'markers',
                type: 'scatter',
                name: domain,
                marker: {
                    color: DOMAIN_COLORS[domain] || '#333',
                    size: 8,
                    opacity: 0.8,
                    line: {color: 'white', width: 0.5}
                }
            });
        }

        // Handle any unknown domains
        var knownSet = {};
        for (var di = 0; di < DOMAIN_ORDER.length; di++) knownSet[DOMAIN_ORDER[di]] = true;
        for (var domain in byDomain) {
            if (knownSet[domain]) continue;
            var points = byDomain[domain];
            traces.push({
                x: points.map(function (p) { return p.scoreA; }),
                y: points.map(function (p) { return p.scoreB; }),
                customdata: points.map(function (p) {
                    return [p.shortName, p.scoreA.toFixed(3), p.scoreB.toFixed(3),
                            (p.diff >= 0 ? '+' : '') + p.diff.toFixed(3)];
                }),
                hovertemplate:
                    '<b>%{customdata[0]}</b><br>' +
                    nameA + ': %{customdata[1]}<br>' +
                    nameB + ': %{customdata[2]}<br>' +
                    'Diff: %{customdata[3]}' +
                    '<extra>' + domain + '</extra>',
                mode: 'markers',
                type: 'scatter',
                name: domain,
                marker: {color: '#999', size: 8, opacity: 0.8}
            });
        }

        var layout = {
            xaxis: {title: nameA, range: [-0.05, 1.05], constrain: 'domain'},
            yaxis: {title: nameB, range: [-0.05, 1.05], scaleanchor: 'x'},
            hovermode: 'closest',
            legend: {x: 0.98, y: 0.02, xanchor: 'right', yanchor: 'bottom', bgcolor: 'rgba(255,255,255,0.9)'},
            margin: {t: 10, r: 20},
            plot_bgcolor: 'white',
            annotations: [{
                x: 0.02, y: 0.98, xref: 'paper', yref: 'paper',
                text: 'Pearson r = ' + stats.pearsonR.toFixed(3) +
                      '<br>Spearman rho = ' + stats.spearmanRho.toFixed(3) +
                      '<br>n = ' + stats.n + ' benchmarks',
                showarrow: false,
                font: {family: 'monospace', size: 11},
                align: 'left',
                bgcolor: 'rgba(255,255,255,0.85)',
                bordercolor: '#cccccc', borderwidth: 1, borderpad: 6,
                xanchor: 'left', yanchor: 'top'
            }]
        };

        Plotly.newPlot('scatter-plot', traces, layout, {responsive: true});
    }

    // ---- Chart 2: Difference Bar Chart ----
    function renderDifferenceChart(data, nameA, nameB) {
        var sorted = data.slice().sort(function (a, b) {
            return Math.abs(b.diff) - Math.abs(a.diff);
        }).slice(0, 40).reverse();

        var trace = {
            y: sorted.map(function (d) { return d.shortName; }),
            x: sorted.map(function (d) { return d.diff; }),
            type: 'bar',
            orientation: 'h',
            marker: {
                color: sorted.map(function (d) {
                    return DOMAIN_COLORS[d.domain] || '#999';
                }),
                opacity: 0.85
            },
            customdata: sorted.map(function (d) {
                return [d.shortName, d.scoreA.toFixed(3), d.scoreB.toFixed(3),
                        (d.diff >= 0 ? '+' : '') + d.diff.toFixed(3), d.domain];
            }),
            hovertemplate:
                '<b>%{customdata[0]}</b> (%{customdata[4]})<br>' +
                nameA + ': %{customdata[1]}<br>' +
                nameB + ': %{customdata[2]}<br>' +
                'Diff: %{customdata[3]}' +
                '<extra></extra>'
        };

        var layout = {
            xaxis: {title: 'Score Difference (' + nameA + ' minus ' + nameB + ')', zeroline: true},
            yaxis: {automargin: true, tickfont: {size: 10}},
            margin: {l: 220, t: 30, r: 20, b: 50},
            plot_bgcolor: 'white',
            annotations: [
                {
                    x: 0, y: 1.02, xref: 'paper', yref: 'paper',
                    text: '<b>\u25C0 ' + nameB + ' scores higher</b>',
                    showarrow: false, font: {size: 11, color: '#555'},
                    xanchor: 'left'
                },
                {
                    x: 1, y: 1.02, xref: 'paper', yref: 'paper',
                    text: '<b>' + nameA + ' scores higher \u25B6</b>',
                    showarrow: false, font: {size: 11, color: '#555'},
                    xanchor: 'right'
                }
            ]
        };

        Plotly.newPlot('difference-bar-chart', [trace], layout, {responsive: true});
    }

    // ---- Chart 3: Domain Summary ----
    function renderDomainSummary(data, nameA, nameB) {
        var domainStats = {};
        for (var i = 0; i < data.length; i++) {
            var d = data[i];
            if (!domainStats[d.domain]) {
                domainStats[d.domain] = {scoresA: [], scoresB: []};
            }
            domainStats[d.domain].scoresA.push(d.scoreA);
            domainStats[d.domain].scoresB.push(d.scoreB);
        }

        // Sort domains by canonical order
        var domains = Object.keys(domainStats).sort(function (a, b) {
            var idxA = DOMAIN_ORDER.indexOf(a);
            var idxB = DOMAIN_ORDER.indexOf(b);
            if (idxA === -1) idxA = 99;
            if (idxB === -1) idxB = 99;
            return idxA - idxB;
        });

        function mean(arr) {
            var s = 0;
            for (var i = 0; i < arr.length; i++) s += arr[i];
            return s / arr.length;
        }

        function std(arr) {
            var m = mean(arr);
            var s = 0;
            for (var i = 0; i < arr.length; i++) s += (arr[i] - m) * (arr[i] - m);
            return Math.sqrt(s / arr.length);
        }

        var traceA = {
            x: domains,
            y: domains.map(function (d) { return mean(domainStats[d].scoresA); }),
            error_y: {
                type: 'data',
                array: domains.map(function (d) { return std(domainStats[d].scoresA); }),
                visible: true
            },
            name: nameA,
            type: 'bar',
            marker: {color: '#45C676', opacity: 0.85},
            text: domains.map(function (d) { return 'n=' + domainStats[d].scoresA.length; }),
            hovertemplate: '%{x}<br>Mean: %{y:.3f}<br>%{text}<extra>' + nameA + '</extra>'
        };

        var traceB = {
            x: domains,
            y: domains.map(function (d) { return mean(domainStats[d].scoresB); }),
            error_y: {
                type: 'data',
                array: domains.map(function (d) { return std(domainStats[d].scoresB); }),
                visible: true
            },
            name: nameB,
            type: 'bar',
            marker: {color: '#47B7DE', opacity: 0.85},
            text: domains.map(function (d) { return 'n=' + domainStats[d].scoresB.length; }),
            hovertemplate: '%{x}<br>Mean: %{y:.3f}<br>%{text}<extra>' + nameB + '</extra>'
        };

        var layout = {
            barmode: 'group',
            yaxis: {title: 'Mean Score', range: [0, 1.1]},
            xaxis: {title: ''},
            legend: {orientation: 'h', y: -0.15},
            margin: {t: 10, r: 20},
            plot_bgcolor: 'white'
        };

        Plotly.newPlot('domain-summary-chart', [traceA, traceB], layout, {responsive: true});
    }

    // ---- Main orchestrator ----
    function updateAllCharts() {
        var nameA = $('#model-x-select').val();
        var nameB = $('#model-y-select').val();

        if (!nameA || !nameB || nameA === nameB) {
            $('#stats-summary').hide();
            Plotly.purge('scatter-plot');
            Plotly.purge('difference-bar-chart');
            Plotly.purge('domain-summary-chart');
            return;
        }

        var data = getCommonBenchmarks(nameA, nameB);
        if (data.length < 3) {
            $('#stats-summary').hide();
            Plotly.purge('scatter-plot');
            Plotly.purge('difference-bar-chart');
            Plotly.purge('domain-summary-chart');
            return;
        }

        var stats = computeStatistics(data);
        updateStatsSummary(stats);
        renderScatterPlot(data, stats, nameA, nameB);
        renderDifferenceChart(data, nameA, nameB);
        renderDomainSummary(data, nameA, nameB);
    }

    // ---- CSV download ----
    function makeCSV(data, nameA, nameB) {
        var headers = ['benchmark', 'domain', nameA, nameB, 'difference'];
        var rows = [headers.join(',')];
        for (var i = 0; i < data.length; i++) {
            var d = data[i];
            rows.push([
                '"' + d.shortName + '"',
                d.domain,
                d.scoreA.toFixed(4),
                d.scoreB.toFixed(4),
                d.diff.toFixed(4)
            ].join(','));
        }
        return rows.join('\n');
    }

    $('#downloadModelCSVButton').click(function () {
        var nameA = $('#model-x-select').val();
        var nameB = $('#model-y-select').val();
        if (!nameA || !nameB) return;

        var data = getCommonBenchmarks(nameA, nameB);
        if (data.length === 0) return;

        var csv = makeCSV(data, nameA, nameB);
        var blob = new Blob([csv], {type: 'text/csv;charset=utf-8;'});
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = nameA + '_VS_' + nameB + '_model_compare.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    // ---- Initialize ----
    var DEFAULT_MODEL_A = 'convnext_large_mlp:clip_laion2b_augreg_ft_in1k_384';
    var DEFAULT_MODEL_B = 'vit_large_patch14_clip_224:openai_ft_in1k';

    var modelNames = extractModelNames(comparison_data);
    initDropdowns(modelNames);

    if (modelNames.indexOf(DEFAULT_MODEL_A) !== -1 && modelNames.indexOf(DEFAULT_MODEL_B) !== -1) {
        $('#model-x-select').val(DEFAULT_MODEL_A).trigger('change.select2');
        $('#model-y-select').val(DEFAULT_MODEL_B).trigger('change.select2');
        updateAllCharts();
    }

    $('#model-x-select, #model-y-select').on('change', updateAllCharts);
});
