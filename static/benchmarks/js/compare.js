function initializeBenchmarkComparison() {
    // adapted from http://bl.ocks.org/peterssonjonas/4a0e7cb8d23231243e0e

    const container_selector = "div#comparison-scatter";
    const xlabel_selector = '#xlabel';
    const ylabel_selector = '#ylabel';

    // make sure we have a container to work with, otherwise abort
    if ($(container_selector).length < 1) {
        return;
    }

    let idKey = "model",
        xKey = null,
        yKey = null;
    const scatterElement = document.querySelector(container_selector);
    const scatterPanel = document.getElementById('benchmark-scatter-panel');

    function scatterIsExpanded() {
        return !!(scatterPanel && scatterPanel.classList.contains('is-expanded-plot'));
    }

    function currentScatterHeight() {
        const expandCore = window.CompareAnalysisExpandCore;
        if (scatterIsExpanded() && expandCore) {
            return expandCore.expandedPlotHeight(window.innerHeight);
        }
        return window.CompareCorrelationCore.responsiveScatterHeight(
            $(container_selector).width()
        );
    }

    function rememberCollapsedScatterSize(height) {
        const expandCore = window.CompareAnalysisExpandCore;
        if (!scatterIsExpanded() && expandCore && scatterElement) {
            expandCore.rememberCollapsedPlotSize(scatterElement, {
                height: height,
                width: null,
                autosize: true
            });
        }
    }

    function currentComparisonData() {
        if (window.CompareDashboard) return window.CompareDashboard.getComparisonData();
        return comparison_data;
    }

    function validScore(value) {
        if (window.CompareCorrelationCore) {
            return window.CompareCorrelationCore.validMatrixScore(value) !== null;
        }
        return value !== null && value !== undefined && value !== '' &&
            Number.isFinite(Number(value));
    }

    function getDeduplicatedValues() {
        // Filter data to guard against empty "" or "X" scores turning into NaNs
        const filtered_data = currentComparisonData().filter(row =>
            row[xKey.replace('-score', '-is_complete')] == 1 && validScore(row[xKey]) &&
            row[yKey.replace('-score', '-is_complete')] == 1 && validScore(row[yKey]));

        // Calculate the correlation
        const xValues = filtered_data.map(d => +d[xKey]);
        const yValues = filtered_data.map(d => +d[yKey]);
        return [filtered_data, xValues, yValues];
    }

    // Calculate Pearson correlation coefficient, R^2, and p-value
    function calculateCorrelation(xArr, yArr) {
        const n = xArr.length;
        if (n < 2) return {correlation: null, rSquared: null, pValue: null};
        const sharedResult = window.CompareCorrelationCore
            ? window.CompareCorrelationCore.pearsonCorrelation(xArr, yArr, 2)
            : null;
        const meanX = xArr.reduce((sum, value) => sum + value, 0) / n;
        const meanY = yArr.reduce((sum, value) => sum + value, 0) / n;
        const numerator = xArr.reduce((sum, value, index) =>
            sum + (value - meanX) * (yArr[index] - meanY), 0);
        const denominator = Math.sqrt(
            xArr.reduce((sum, value) => sum + Math.pow(value - meanX, 2), 0) *
            yArr.reduce((sum, value) => sum + Math.pow(value - meanY, 2), 0)
        );
        const fallbackCorrelation = denominator === 0 ? null : numerator / denominator;
        const correlation = sharedResult ? sharedResult.r : fallbackCorrelation;
        if (correlation === null) return {correlation: null, rSquared: null, pValue: null};
        const rSquared = correlation * correlation;  // Calculate R^2

        let pValue = null;
        if (n > 2 && rSquared < 1) {
            const tStatistic = correlation * Math.sqrt((n - 2) / (1 - rSquared));
            pValue = 2 * (1 - jStat.studentt.cdf(Math.abs(tStatistic), n - 2));
        }

        return {correlation, rSquared, pValue};  // Return correlation, R^2, and p-value
    }

    function rankArray(values) {
        const indexed = values.map((value, index) => ({value, index}))
            .sort((a, b) => a.value - b.value);
        const ranks = new Array(values.length);
        let i = 0;
        while (i < indexed.length) {
            let j = i + 1;
            while (j < indexed.length && indexed[j].value === indexed[i].value) j++;
            const averageRank = (i + j + 1) / 2;
            for (let k = i; k < j; k++) ranks[indexed[k].index] = averageRank;
            i = j;
        }
        return ranks;
    }


    // Calculate Linear Regression Slope and Intercept
    function calculateLinearRegression(xArr, yArr) {
        const n = xArr.length;
        const sumX = xArr.reduce((a, b) => a + b, 0);
        const sumY = yArr.reduce((a, b) => a + b, 0);
        const sumXY = xArr.map((xi, i) => xi * yArr[i]).reduce((a, b) => a + b, 0);
        const sumX2 = xArr.map(xi => xi * xi).reduce((a, b) => a + b, 0);
        const denominator = n * sumX2 - sumX * sumX;
        const slope = denominator === 0 ? 0 : (n * sumXY - sumX * sumY) / denominator;
        const intercept = (sumY - slope * sumX) / n;
        return {slope, intercept};
    }

    function setEmpty(isEmpty) {
        $('#benchmark-compare-empty').toggle(isEmpty);
        $(container_selector).toggle(!isEmpty);
        if (isEmpty && window.Plotly && scatterElement) window.Plotly.purge(scatterElement);
    }

    function updatePlot() {
        xKey = $(xlabel_selector).prop('value') + "-score";
        yKey = $(ylabel_selector).prop('value') + "-score";

        const xName = $(xlabel_selector).find('option:selected').text();
        const yName = $(ylabel_selector).find('option:selected').text();

        const [filtered_data, xValues, yValues] = getDeduplicatedValues();
        if (filtered_data.length < 2) {
            setEmpty(true);
            return;
        }
        setEmpty(false);
        const {correlation, rSquared, pValue} = calculateCorrelation(xValues, yValues);
        const spearman = calculateCorrelation(rankArray(xValues), rankArray(yValues));

        const {slope, intercept} = calculateLinearRegression(xValues, yValues);
        var pValueStr = pValue === null ? 'p-value: N/A' : (pValue >= 0.01
            ? `p-value: ${pValue.toFixed(2)}`
            : `p-value: ${pValue.toExponential(1).replace(/^(\d)\.?\d*e/, '$1e')}`);
        var statsText = "Pearson R: " + (correlation === null ? 'N/A' : correlation.toFixed(2))
            + "    Spearman rho: " + (spearman.correlation === null ? 'N/A' : spearman.correlation.toFixed(2))
            + "    R\u00B2: " + (rSquared === null ? 'N/A' : rSquared.toFixed(2))
            + "    " + pValueStr
            + "    n=" + filtered_data.length + " paired models";
        if (!window.Plotly || !window.CompareCorrelationCore) return;
        const plot = window.CompareCorrelationCore.buildPlotlyBenchmarkScatter(
            filtered_data.map(function (row) {
                return {model: row[idKey], x: Number(row[xKey]), y: Number(row[yKey])};
            }),
            {
                xLabel: xName,
                yLabel: yName,
                statsText: statsText,
                regression: {slope: slope, intercept: intercept},
                logoSource: window.logo_url || '/static/benchmarks/img/logo.png',
                height: currentScatterHeight()
            }
        );
        Promise.resolve(window.Plotly.react(scatterElement, plot.data, plot.layout, plot.config))
            .then(function () {
                rememberCollapsedScatterSize(plot.layout.height);
            });
    }

    function syncComparisonBenchmarks() {
        if (!window.CompareDashboard) return;
        window.CompareDashboard.setComparisonBenchmarks(
            $(xlabel_selector).val(),
            $(ylabel_selector).val()
        );
    }

    $(xlabel_selector + ', ' + ylabel_selector)
        .on("change", function () {
            if (window.CompareDashboard) {
                window.CompareDashboard.setUrlParam(
                    'benchmark_x',
                    window.CompareDashboard.getBenchmarkTypeId($(xlabel_selector).val())
                );
                window.CompareDashboard.setUrlParam(
                    'benchmark_y',
                    window.CompareDashboard.getBenchmarkTypeId($(ylabel_selector).val())
                );
                syncComparisonBenchmarks();
            }
            updatePlot();
        });

    if (window.CompareDashboard) {
        const defaultBenchmarkTypes = window.CompareDashboardCore
            ? window.CompareDashboardCore.defaultComparisonBenchmarkTypes(
                window.compare_dashboard_data && window.compare_dashboard_data.domain
            )
            : [];
        const requestedX = window.CompareDashboard.getUrlParam('benchmark_x') ||
            defaultBenchmarkTypes[0];
        const requestedY = window.CompareDashboard.getUrlParam('benchmark_y') ||
            defaultBenchmarkTypes[1];
        const requestedXId = $(xlabel_selector + ' option[value="' + requestedX + '"]').length
            ? requestedX
            : window.CompareDashboard.getBenchmarkIdByTypeId(requestedX);
        const requestedYId = $(ylabel_selector + ' option[value="' + requestedY + '"]').length
            ? requestedY
            : window.CompareDashboard.getBenchmarkIdByTypeId(requestedY);
        if (requestedXId) {
            $(xlabel_selector).val(requestedXId);
        }
        if (requestedYId) {
            $(ylabel_selector).val(requestedYId);
        }
        syncComparisonBenchmarks();
    }

    updatePlot();

    let _cmpResizeTimer = null;
    let _cmpResizeGeneration = 0;
    $(window).on('resize', function () {
        clearTimeout(_cmpResizeTimer);
        _cmpResizeTimer = setTimeout(function () {
            if (!window.Plotly || !scatterElement || !scatterElement.layout) return;
            const generation = ++_cmpResizeGeneration;
            const height = currentScatterHeight();
            Promise.resolve(window.Plotly.relayout(scatterElement, {
                height: height,
                width: null,
                autosize: true
            })).then(function () {
                if (generation !== _cmpResizeGeneration) return;
                rememberCollapsedScatterSize(height);
                if (window.Plotly.Plots && window.Plotly.Plots.resize) {
                    window.Plotly.Plots.resize(scatterElement);
                }
            });
        }, 200);
    });

    // typing functionality in select dropdowns
    $('#xlabel').select2({
        placeholder: "Select or type",
        tags: true,
        allowClear: true
    });
    $('#ylabel').select2({
        placeholder: "Select or type",
        tags: true,
        allowClear: true
    });

    function refreshBenchmarkOptions() {
        if (!window.CompareDashboard) return;
        [xlabel_selector, ylabel_selector].forEach(function (selector) {
            const select = $(selector);
            select.find('option').each(function () {
                const option = $(this);
                if (!option.data('base-label')) option.data('base-label', option.text());
                const active = window.CompareDashboard.isBenchmarkActive(this.value);
                option.prop('disabled', !active);
                option.text(option.data('base-label'));
            });
            if (!window.CompareDashboard.isBenchmarkActive(select.val())) {
                const fallback = select.find('option:not(:disabled)').first().val();
                select.val(fallback || '').trigger('change.select2');
            }
            select.trigger('change.select2');
        });
        syncComparisonBenchmarks();
        updatePlot();
    }

    if (window.CompareDashboard) {
        window.CompareDashboard.subscribe(refreshBenchmarkOptions);
    }

    // download functionality

    function getFileName(extension) {
        let xlabel = $(xlabel_selector).find('option:selected').text();
        let ylabel = $(ylabel_selector).find('option:selected').text();
        return xlabel + "_VS_" + ylabel + extension
    }

    $("#downloadSVGButton").click(function () {
        if (!window.Plotly || !scatterElement) return;
        window.Plotly.downloadImage(scatterElement, {
            format: 'svg',
            filename: getFileName('')
        });
    });

    function makeCSV() {
        // only data for selected benchmarks
        const [filtered_data] = getDeduplicatedValues();
        const fields = ['model', xKey, yKey];
        const headers = [
            'model',
            $(xlabel_selector).find('option:selected').text(),
            $(ylabel_selector).find('option:selected').text()
        ];
        const rows = filtered_data.map(row => fields.map(field => JSON.stringify(row[field])).join(','));
        return [headers.join(','), ...rows].join('\n');
    }

    $("#downloadCSVButton").click(function () {
        const csvData = makeCSV();
        // Create a Blob from the CSV string
        const blob = new Blob([csvData], {type: 'text/csv;charset=utf-8;'});
        const url = URL.createObjectURL(blob);

        // Create a temporary anchor element
        const a = document.createElement('a');
        a.href = url;
        a.download = getFileName(".csv"); // Set the download attribute with a filename

        // Append anchor to body
        document.body.appendChild(a);

        // Trigger download
        a.click();

        // Remove anchor from body
        document.body.removeChild(a);
    });

    function syncComparisonExampleSelection() {
        const selectedX = $(xlabel_selector).val();
        const selectedY = $(ylabel_selector).val();
        $('.comparison_selector').each(function () {
            const item = $(this);
            const isActive = item.attr('data-benchmark-x') === selectedX &&
                item.attr('data-benchmark-y') === selectedY;
            item.toggleClass('is-active', isActive);
            item.find('.benchmark-scatter-example-button').attr('aria-expanded', isActive);
            item.find('.benchmark-scatter-example-detail').toggle(isActive);
        });
    }

    // Example selections for correlations in literature.
    $('.benchmark-scatter-example-button').click(function () {
        const item = $(this).closest('.comparison_selector');
        const x = item.attr('data-benchmark-x');
        const y = item.attr('data-benchmark-y');
        $("#xlabel").val(x).trigger('change');
        $("#ylabel").val(y).trigger('change');
    });
    $(xlabel_selector + ', ' + ylabel_selector).on('change', syncComparisonExampleSelection);
    syncComparisonExampleSelection();
}

$(document).ready(function () {
    if (window.CompareDashboard) initializeBenchmarkComparison();
    else document.addEventListener('compare-dashboard:ready', initializeBenchmarkComparison, {once: true});
});
