$(document).ready(function () {
    // Guard: only run on the model compare page
    if (document.getElementById('scatter-plot') === null) {
        return;
    }

    // Capture compare-benchmarks D3 SVG dimensions (panel is visible at load time)
    var refSvg = document.querySelector('#comparison-scatter svg');
    var REF_WIDTH = refSvg ? parseInt(refSvg.getAttribute('width')) : null;
    var REF_HEIGHT = refSvg ? parseInt(refSvg.getAttribute('height')) : null;

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

    // Domains shown by default (others start hidden via legendonly)
    var DEFAULT_VISIBLE = {'V1': true, 'V2': true, 'V4': true, 'IT': true, 'Behavioral': true};
    var DOMAIN_ORDER = ['V1', 'V2', 'V4', 'IT', 'Behavioral', 'Engineering', 'Neural', 'Average Vision'];

    // Shared font to match compare-benchmarks (D3) tab
    var PLOT_FONT = {family: "'Open Sans', Arial, sans-serif", size: 14, color: 'black'};

    // Consistent logo size: 120x28 px (same as D3 chart)
    var LOGO_PX = {w: 120, h: 28};

    function logoSize(plotWidth, plotHeight, margins) {
        var areaW = plotWidth - (margins.l || 0) - (margins.r || 0);
        var areaH = plotHeight - (margins.t || 0) - (margins.b || 0);
        return {
            sizex: LOGO_PX.w / areaW,
            sizey: LOGO_PX.h / areaH
        };
    }

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

    // ---- Fuzzy matcher for Select2 ----
    function fuzzyMatcher(params, data) {
        if ($.trim(params.term) === '') {
            return data;
        }
        if (typeof data.text === 'undefined') {
            return null;
        }
        // Normalize both query and option: lowercase, strip spaces/hyphens/underscores
        var normalize = function (s) {
            return s.toLowerCase().replace(/[\s\-_:.]/g, '');
        };
        var query = normalize(params.term);
        var text = normalize(data.text);

        if (text.indexOf(query) > -1) {
            return $.extend({}, data, true);
        }

        // Also try matching each query token independently
        var tokens = params.term.toLowerCase().split(/[\s]+/);
        var textLower = data.text.toLowerCase();
        var allMatch = true;
        for (var i = 0; i < tokens.length; i++) {
            if (tokens[i] && textLower.indexOf(tokens[i]) === -1 && text.indexOf(tokens[i].replace(/[\s\-_:.]/g, '')) === -1) {
                allMatch = false;
                break;
            }
        }
        if (allMatch) {
            return $.extend({}, data, true);
        }

        return null;
    }

    // ---- Initialize Select2 dropdowns with fuzzy search ----
    function initDropdowns(modelNames) {
        var selA = $('#model-x-select');
        var selB = $('#model-y-select');
        selA.empty();
        selB.empty();

        selA.append(new Option('', '', true, true));
        selB.append(new Option('', '', true, true));

        for (var i = 0; i < modelNames.length; i++) {
            selA.append(new Option(modelNames[i], modelNames[i], false, false));
            selB.append(new Option(modelNames[i], modelNames[i], false, false));
        }

        selA.select2({placeholder: 'Select Model A', allowClear: true, matcher: fuzzyMatcher});
        selB.select2({placeholder: 'Select Model B', allowClear: true, matcher: fuzzyMatcher});
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
        if (p < 0.01) return p.toExponential(1).replace(/^(\d)\.?\d*e/, '$1e');
        return p.toFixed(2);
    }

    // ---- Update model info cards ----
    function updateModelCards(nameA, nameB) {
        var metaA = (typeof model_metadata !== 'undefined') ? model_metadata[nameA] : null;
        var metaB = (typeof model_metadata !== 'undefined') ? model_metadata[nameB] : null;

        if (!nameA || !nameB) {
            $('#model-cards-row').hide();
            return;
        }

        if (metaA) {
            $('#card-a-name').text(nameA);
            $('#card-a-rank').text(metaA.rank != null ? 'Rank #' + metaA.rank : '');
            $('#card-a-contributor').text(metaA.contributor || 'Unknown');
            $('#card-a-link').attr('href', metaA.url || '#');
        } else {
            $('#card-a-name').text(nameA);
            $('#card-a-rank').text('');
            $('#card-a-contributor').text('Unknown');
            $('#card-a-link').attr('href', '#');
        }

        if (metaB) {
            $('#card-b-name').text(nameB);
            $('#card-b-rank').text(metaB.rank != null ? 'Rank #' + metaB.rank : '');
            $('#card-b-contributor').text(metaB.contributor || 'Unknown');
            $('#card-b-link').attr('href', metaB.url || '#');
        } else {
            $('#card-b-name').text(nameB);
            $('#card-b-rank').text('');
            $('#card-b-contributor').text('Unknown');
            $('#card-b-link').attr('href', '#');
        }

        $('#model-cards-row').show();
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
            line: {color: 'lightgrey', width: 2, dash: 'dash'},
            hoverinfo: 'skip',
            showlegend: false
        });

        // Data points per domain (in canonical order for consistent legend)
        for (var di = 0; di < DOMAIN_ORDER.length; di++) {
            var domain = DOMAIN_ORDER[di];
            var points = byDomain[domain];
            if (!points || points.length === 0) continue;

            var isDefault = DEFAULT_VISIBLE[domain] === true;
            traces.push({
                x: points.map(function (p) { return p.scoreA; }),
                y: points.map(function (p) { return p.scoreB; }),
                customdata: points.map(function (p) {
                    return [p.shortName, p.scoreA.toFixed(3), p.scoreB.toFixed(3),
                            (p.diff >= 0 ? '+' : '') + p.diff.toFixed(3), p.benchId];
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
                visible: isDefault ? true : 'legendonly',
                marker: {
                    color: DOMAIN_COLORS[domain] || '#333',
                    size: 8,
                    opacity: 0.5,
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
                            (p.diff >= 0 ? '+' : '') + p.diff.toFixed(3), p.benchId];
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
                visible: 'legendonly',
                marker: {color: '#999', size: 8, opacity: 0.5}
            });
        }

        // Stats annotation text matching compare-benchmarks style
        var statsText = 'Pearson R: ' + stats.pearsonR.toFixed(2) +
            '    R\u00B2: ' + stats.r2.toFixed(2) +
            '    p-value: ' + formatPValue(stats.pearsonP) +
            '    n=' + stats.n + ' benchmarks';

        // Use exact same dimensions as the compare-benchmarks D3 chart
        var chartWidth = REF_WIDTH || 600;
        var chartHeight = REF_HEIGHT || Math.round(chartWidth * 2 / 3);

        var scatterMargins = {t: 40, r: 20, l: 60, b: 50};
        var scatterLogo = logoSize(chartWidth, chartHeight, scatterMargins);

        var layout = {
            font: PLOT_FONT,
            width: chartWidth,
            height: chartHeight,
            xaxis: {title: {text: nameA, font: {size: 14}}, range: [-0.05, 1.05], tickfont: {size: 12}},
            yaxis: {title: {text: nameB, font: {size: 14}}, range: [-0.05, 1.05], tickfont: {size: 12}},
            hovermode: 'closest',
            showlegend: false,
            margin: scatterMargins,
            plot_bgcolor: 'white',
            annotations: [{
                x: 0.5, y: 1, xref: 'paper', yref: 'paper',
                text: statsText,
                showarrow: false,
                font: {size: 14, family: PLOT_FONT.family, color: 'black'},
                align: 'center',
                xanchor: 'center', yanchor: 'bottom'
            }],
            images: [{
                source: logo_url,
                xref: 'paper', yref: 'paper',
                x: 0.98, y: 0.08,
                sizex: scatterLogo.sizex, sizey: scatterLogo.sizey,
                xanchor: 'right', yanchor: 'bottom',
                layer: 'above'
            }]
        };

        Plotly.newPlot('scatter-plot', traces, layout);

        // Build HTML legend in the sidebar
        var legendEl = document.getElementById('scatter-legend');
        var plotDiv = document.getElementById('scatter-plot');
        if (legendEl) {
            var html = '';
            for (var ti = 0; ti < traces.length; ti++) {
                var tr = traces[ti];
                if (!tr.name || tr.showlegend === false) continue;
                var vis = tr.visible === 'legendonly' ? 0.4 : 1.0;
                var mColor = (tr.marker && tr.marker.color) || '#999';
                html += '<div class="scatter-legend-item" data-trace-idx="' + ti + '" '
                    + 'style="cursor:pointer;padding:3px 0;opacity:' + vis + ';">'
                    + '<span style="display:inline-block;width:12px;height:12px;border-radius:50%;'
                    + 'background:' + mColor + ';margin-right:6px;vertical-align:middle;"></span>'
                    + '<span style="font-size:13px;font-family:' + PLOT_FONT.family + ';vertical-align:middle;">'
                    + tr.name + '</span></div>';
            }
            legendEl.innerHTML = html;

            // Click to toggle, double-click to focus
            legendEl.querySelectorAll('.scatter-legend-item').forEach(function (item) {
                var idx = parseInt(item.getAttribute('data-trace-idx'));
                var clickTimer = null;
                item.addEventListener('click', function (e) {
                    if (clickTimer) { clearTimeout(clickTimer); clickTimer = null; return; }
                    clickTimer = setTimeout(function () {
                        clickTimer = null;
                        var curVis = plotDiv.data[idx].visible;
                        var newVis = (curVis === 'legendonly') ? true : 'legendonly';
                        Plotly.restyle(plotDiv, {visible: newVis}, [idx]);
                        item.style.opacity = newVis === 'legendonly' ? '0.4' : '1';
                    }, 300);
                });
                item.addEventListener('dblclick', function (e) {
                    // Focus: show only this trace, hide all others
                    var allVis = [];
                    var allIdx = [];
                    for (var j = 0; j < plotDiv.data.length; j++) {
                        if (plotDiv.data[j].showlegend === false) continue;
                        allVis.push(j === idx ? true : 'legendonly');
                        allIdx.push(j);
                    }
                    Plotly.restyle(plotDiv, {visible: allVis}, allIdx);
                    legendEl.querySelectorAll('.scatter-legend-item').forEach(function (li) {
                        li.style.opacity = parseInt(li.getAttribute('data-trace-idx')) === idx ? '1' : '0.4';
                    });
                });
            });
        }

        // Click handler: navigate to benchmark page
        document.getElementById('scatter-plot').on('plotly_click', function (eventData) {
            if (eventData && eventData.points && eventData.points.length > 0) {
                var pt = eventData.points[0];
                if (pt.customdata && pt.customdata[4]) {
                    var benchId = pt.customdata[4];
                    var url = (typeof benchmark_url_map !== 'undefined') ? benchmark_url_map[benchId] : null;
                    if (url) {
                        window.open(url, '_blank');
                    }
                }
            }
        });
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
                        (d.diff >= 0 ? '+' : '') + d.diff.toFixed(3), d.domain, d.benchId];
            }),
            hovertemplate:
                '<b>%{customdata[0]}</b> (%{customdata[4]})<br>' +
                nameA + ': %{customdata[1]}<br>' +
                nameB + ': %{customdata[2]}<br>' +
                'Diff: %{customdata[3]}' +
                '<extra></extra>'
        };

        var barMargins = {l: 220, t: 50, r: 20, b: 50};
        var barEl = document.getElementById('difference-bar-chart');
        var barLogo = logoSize(barEl.offsetWidth || 800, 650, barMargins);

        var layout = {
            font: PLOT_FONT,
            xaxis: {title: {text: 'Score Difference (' + nameA + ' minus ' + nameB + ')', font: {size: 14}}, zeroline: true, tickfont: {size: 12}},
            yaxis: {automargin: true, tickfont: {size: 10}},
            margin: barMargins,
            plot_bgcolor: 'white',
            annotations: [
                {
                    x: 0, y: 1.05, xref: 'paper', yref: 'paper',
                    text: '<b>\u25C0 ' + nameB + ' scores higher</b>',
                    showarrow: false, font: {size: 11, color: '#555'},
                    xanchor: 'left'
                },
                {
                    x: 1, y: 1.05, xref: 'paper', yref: 'paper',
                    text: '<b>' + nameA + ' scores higher \u25B6</b>',
                    showarrow: false, font: {size: 11, color: '#555'},
                    xanchor: 'right'
                }
            ],
            images: [{
                source: logo_url,
                xref: 'paper', yref: 'paper',
                x: 1, y: 0,
                sizex: barLogo.sizex, sizey: barLogo.sizey,
                xanchor: 'right', yanchor: 'bottom',
                layer: 'above'
            }]
        };

        Plotly.newPlot('difference-bar-chart', [trace], layout, {responsive: true});

        // Click handler: navigate to benchmark page
        document.getElementById('difference-bar-chart').on('plotly_click', function (eventData) {
            if (eventData && eventData.points && eventData.points.length > 0) {
                var pt = eventData.points[0];
                if (pt.customdata && pt.customdata[5]) {
                    var benchId = pt.customdata[5];
                    var url = (typeof benchmark_url_map !== 'undefined') ? benchmark_url_map[benchId] : null;
                    if (url) {
                        window.open(url, '_blank');
                    }
                }
            }
        });
    }

    // ---- Chart 3: Domain Summary (split violin plot) ----
    function renderDomainSummary(data, nameA, nameB) {
        var domainStats = {};
        for (var i = 0; i < data.length; i++) {
            var d = data[i];
            if (!domainStats[d.domain]) {
                domainStats[d.domain] = {scoresA: [], scoresB: [], names: []};
            }
            domainStats[d.domain].scoresA.push(d.scoreA);
            domainStats[d.domain].scoresB.push(d.scoreB);
            domainStats[d.domain].names.push(d.shortName);
        }

        // Only show default-visible domains
        var domains = [];
        for (var di = 0; di < DOMAIN_ORDER.length; di++) {
            var dom = DOMAIN_ORDER[di];
            if (DEFAULT_VISIBLE[dom] && domainStats[dom]) {
                domains.push(dom);
            }
        }

        var traces = [];

        // Split violin: Model A on the negative (left) side, Model B on the positive (right) side
        for (var di = 0; di < domains.length; di++) {
            var dom = domains[di];
            var ds = domainStats[dom];

            traces.push({
                y: ds.scoresA,
                x: ds.scoresA.map(function () { return dom; }),
                text: ds.names,
                type: 'violin',
                name: nameA,
                legendgroup: nameA,
                showlegend: di === 0,
                side: 'negative',
                line: {color: '#45C676'},
                fillcolor: 'rgba(69,198,118,0.35)',
                meanline: {visible: true},
                points: 'all',
                jitter: 0.05,
                pointpos: -0.6,
                marker: {color: '#45C676', size: 4, opacity: 0.6},
                scalemode: 'width',
                width: 0.7,
                hovertemplate: '<b>%{text}</b><br>Score: %{y:.3f}<extra>' + nameA + '</extra>'
            });

            traces.push({
                y: ds.scoresB,
                x: ds.scoresB.map(function () { return dom; }),
                text: ds.names,
                type: 'violin',
                name: nameB,
                legendgroup: nameB,
                showlegend: di === 0,
                side: 'positive',
                line: {color: '#47B7DE'},
                fillcolor: 'rgba(71,183,222,0.35)',
                meanline: {visible: true},
                points: 'all',
                jitter: 0.05,
                pointpos: 0.6,
                marker: {color: '#47B7DE', size: 4, opacity: 0.6},
                scalemode: 'width',
                width: 0.7,
                hovertemplate: '<b>%{text}</b><br>Score: %{y:.3f}<extra>' + nameB + '</extra>'
            });
        }

        var violinMargins = {t: 35, r: 20, l: 80, b: 50};
        var violinEl = document.getElementById('domain-summary-chart');
        var violinLogo = logoSize(violinEl.offsetWidth || 700, 400, violinMargins);

        var layout = {
            font: PLOT_FONT,
            violinmode: 'overlay',
            yaxis: {title: {text: 'Score', font: {size: 14}}, range: [0, 1.05], tickfont: {size: 12}},
            xaxis: {title: '', tickfont: {size: 12}},
            legend: {orientation: 'h', y: -0.15},
            margin: violinMargins,
            plot_bgcolor: 'white',
            images: [{
                source: logo_url,
                xref: 'paper', yref: 'paper',
                x: 1, y: 0,
                sizex: violinLogo.sizex, sizey: violinLogo.sizey,
                xanchor: 'right', yanchor: 'bottom',
                layer: 'above'
            }]
        };

        Plotly.newPlot('domain-summary-chart', traces, layout, {responsive: true});
    }

    // ---- Main orchestrator ----
    function updateAllCharts() {
        var nameA = $('#model-x-select').val();
        var nameB = $('#model-y-select').val();

        updateModelCards(nameA, nameB);

        if (!nameA || !nameB || nameA === nameB) {
            Plotly.purge('scatter-plot');
            Plotly.purge('difference-bar-chart');
            Plotly.purge('domain-summary-chart');
            return;
        }

        var data = getCommonBenchmarks(nameA, nameB);
        if (data.length < 3) {
            Plotly.purge('scatter-plot');
            Plotly.purge('difference-bar-chart');
            Plotly.purge('domain-summary-chart');
            return;
        }

        var stats = computeStatistics(data);
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
