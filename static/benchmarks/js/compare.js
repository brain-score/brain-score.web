$(document).ready(function () {
    // adapted from http://bl.ocks.org/peterssonjonas/4a0e7cb8d23231243e0e

    const container_selector = "div#comparison-scatter";
    const xlabel_selector = '#xlabel';
    const ylabel_selector = '#ylabel';

    // make sure we have a container to work with, otherwise abort
    if ($(container_selector).length < 1) {
        return;
    }

    const margin = {top: 25, right: 0, bottom: 40, left: 60};
    let outerWidth = $(container_selector).width(),
        outerHeight = $(container_selector).width() * 2 / 3,
        width = outerWidth - margin.left - margin.right,
        height = outerHeight - margin.top - margin.bottom;

    const dot_size = 8,
        color = '#078930';

    let idKey = "model",
        xKey = null,
        yKey = null;

    let g = null,
        xAxis = null,
        yAxis = null;

    let x = null,
        y = null;

    const svg = d3.select(container_selector)
        .append("svg")
        .attr("width", outerWidth)
        .attr("height", outerHeight)
        .attr("fill", "white");

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

    function updateRegressionLine() {
        const [filtered_data, xValues, yValues] = getDeduplicatedValues();

        const {slope, intercept} = calculateLinearRegression(xValues, yValues);

        // Calculate line endpoints within the current x-axis range
        const xStart = x.domain()[0];
        const xEnd = x.domain()[1];
        const yStart = slope * xStart + intercept;
        const yEnd = slope * xEnd + intercept;

        // Update the regression line with the new start and end points
        svg.select("#regression-line")
            .attr("x1", x(xStart))
            .attr("y1", y(yStart))
            .attr("x2", x(xEnd))
            .attr("y2", y(yEnd));
    }

    function transform(d) {
        return "translate(" + x(d[xKey]) + "," + y(d[yKey]) + ")";
    }

    function zoom() {
        svg.select(".x.axis").call(xAxis);
        svg.select(".y.axis").call(yAxis);

        svg.selectAll(".dot")
            .attr("transform", transform)
            .attr("r", dot_size);
        // Update the regression line based on zoom
        updateRegressionLine();
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
        svg.style('display', isEmpty ? 'none' : null);
    }

    function updatePlot() {
        xKey = $(xlabel_selector).prop('value') + "-score";
        yKey = $(ylabel_selector).prop('value') + "-score";

        const xName = $(xlabel_selector).find('option:selected').text();
        const yName = $(ylabel_selector).find('option:selected').text();

        svg.selectAll("*").remove();

        // tip
        var tip = d3.tip()
            .attr("class", "d3-tip")
            .offset([-10, 0])
            .html(function (d) {
                return "<strong>" + d[idKey] + "</strong><br>" +
                    xName + ": " + d[xKey] + "<br>" +
                    yName + ": " + d[yKey];
            });

        svg.call(tip);

        const [filtered_data, xValues, yValues] = getDeduplicatedValues();
        if (filtered_data.length < 2) {
            setEmpty(true);
            return;
        }
        setEmpty(false);
        const {correlation, rSquared, pValue} = calculateCorrelation(xValues, yValues);
        const spearman = calculateCorrelation(rankArray(xValues), rankArray(yValues));

        // Calculate regression line
        const {slope, intercept} = calculateLinearRegression(xValues, yValues);
        // Define the endpoints for the line
        const xStart = d3.min(xValues);
        const xEnd = d3.max(xValues);
        const yStart = slope * xStart + intercept;
        const yEnd = slope * xEnd + intercept;

        const xMax = d3.max(filtered_data, function (d) {
                return d[xKey];
            }) * 1.05,
            xMin = d3.min(filtered_data, function (d) {
                return d[xKey];
            }) * .95,
            yMax = d3.max(filtered_data, function (d) {
                return d[yKey];
            }) * 1.05,
            yMin = d3.min(filtered_data, function (d) {
                return d[yKey];
            }) * .95;

        x = d3.scale.linear()
            .range([0, width]).nice();

        y = d3.scale.linear()
            .range([height, 0]).nice();

        x.domain([xMin, xMax]);
        y.domain([yMin, yMax]);

        const zoomBeh = d3.behavior.zoom()
            .x(x)
            .y(y)
            .scaleExtent([0, 500])
            .on("zoom", zoom);

        g = svg
            .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
            .call(zoomBeh);

        xAxis = d3.svg.axis()
            .scale(x)
            .ticks(5)
            .orient("bottom")
            .tickSize(-height);

        yAxis = d3.svg.axis()
            .scale(y)
            .ticks(3)
            .orient("left")
            .tickSize(-width);

        g.append("rect")
            .attr("width", width)
            .attr("height", height);

        g.append("g")
            .classed("x axis", true)
            .attr("transform", "translate(0," + height + ")")
            .call(xAxis)
            .append("text")
            .attr("class", "label")
            .attr("x", width / 2)
            .attr("y", 35)
            .style("text-anchor", "middle")
            .style("fill", "black")
            .style("font-size", "14px")
            .style("font-family", "'Open Sans', Arial, sans-serif")
            .style("font-weight", "400")
            .text(xName);

        svg.selectAll(".x.axis text")
            .style("fill", "black")
            .style("font-family", "'Open Sans', Arial, sans-serif")
            .style("font-weight", "400")
            .style("font-size", "12px");

        // Restore axis label size (selectAll above set ticks to 12px)
        svg.select(".x.axis .label")
            .style("font-size", "14px");

        g.append("g")
            .classed("y axis", true)
            .call(yAxis)
            .append("text")
            .attr("class", "label")
            .attr("transform", "rotate(-90)")
            .attr("x", -height / 2)
            .attr("y", -50)
            .attr("dy", ".71em")
            .style("text-anchor", "middle")
            .style("fill", "black")
            .style("font-size", "14px")
            .style("font-family", "'Open Sans', Arial, sans-serif")
            .style("font-weight", "400")
            .text(yName);

        svg.selectAll(".y.axis text")
            .style("fill", "black")
            .style("font-family", "'Open Sans', Arial, sans-serif")
            .style("font-weight", "400")
            .style("font-size", "12px");

        svg.select(".y.axis .label")
            .style("font-size", "14px");

        // Correlation stats -- centered above the plot
        var statsFont = "'Open Sans', Arial, sans-serif";
        var pValueStr = pValue === null ? 'p-value: N/A' : (pValue >= 0.01
            ? `p-value: ${pValue.toFixed(2)}`
            : `p-value: ${pValue.toExponential(1).replace(/^(\d)\.?\d*e/, '$1e')}`);
        var statsText = "Pearson R: " + (correlation === null ? 'N/A' : correlation.toFixed(2))
            + "    Spearman rho: " + (spearman.correlation === null ? 'N/A' : spearman.correlation.toFixed(2))
            + "    R\u00B2: " + (rSquared === null ? 'N/A' : rSquared.toFixed(2))
            + "    " + pValueStr
            + "    n=" + filtered_data.length + " paired models";

        g.append("text")
            .attr("class", "stats-text")
            .attr("x", width / 2)
            .attr("y", -8)
            .attr("fill", "black")
            .style("font-size", "14px")
            .style("font-family", statsFont)
            .style("font-weight", "400")
            .style("text-anchor", "middle")
            .text(statsText);

        // plot regression line
        g.append("line")
            .attr("id", "regression-line")
            .attr("x1", x(xStart))
            .attr("y1", y(yStart))
            .attr("x2", x(xEnd))
            .attr("y2", y(yEnd))
            .attr("stroke-width", 2)
            .attr("stroke", "lightgrey")
            .attr("stroke-dasharray", "4,4");


        const objects = g.append("svg")
            .classed("objects", true)
            .attr("width", width)
            .attr("height", height);

        objects.selectAll(".dot")
            .data(filtered_data)
            .enter().append("circle")
            .classed("dot", true)
            .attr("r", dot_size)
            .attr("transform", transform)
            .style("fill", color)
            .on("mouseover", tip.show)
            .on("mouseout", tip.hide);

        // add Brain-Score logo (bottom-right corner)
        g.append("svg:image")
            .attr('x', width - 125)
            .attr('y', height - 33)
            .attr('width', 120)
            .attr('height', 28)
            .attr("xlink:href", logo_url);
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
        const requestedX = window.CompareDashboard.getUrlParam('benchmark_x');
        const requestedY = window.CompareDashboard.getUrlParam('benchmark_y');
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

    // Redraw at the container's current width on resize so the chart tracks the
    // layout instead of freezing at load-time size. Skip while the panel is
    // hidden (width 0) to avoid collapsing the chart.
    let _cmpResizeTimer = null;
    $(window).on('resize', function () {
        clearTimeout(_cmpResizeTimer);
        _cmpResizeTimer = setTimeout(function () {
            const w = $(container_selector).width();
            if (!w || w < 50) return;
            outerWidth = w;
            outerHeight = w * 2 / 3;
            width = outerWidth - margin.left - margin.right;
            height = outerHeight - margin.top - margin.bottom;
            svg.attr("width", outerWidth).attr("height", outerHeight);
            updatePlot();
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

    function inlineStyles(element) {
        const cssStyles = window.getComputedStyle(element);
        for (let i = 0; i < cssStyles.length; i++) {
            const styleName = cssStyles[i];
            element.style[styleName] = cssStyles.getPropertyValue(styleName);
        }

        Array.from(element.children).forEach(child => inlineStyles(child));
    }

    function getFileName(extension) {
        let xlabel = $(xlabel_selector).find('option:selected').text();
        let ylabel = $(ylabel_selector).find('option:selected').text();
        return xlabel + "_VS_" + ylabel + extension
    }

    $("#downloadSVGButton").click(function () {
        const svgNode = d3.select('svg').node();
        const clonedSvg = svgNode.cloneNode(true);
        inlineStyles(clonedSvg);
        let svgData = clonedSvg.outerHTML;
        svgData = svgData.replace('xlink:href="/static/benchmarks/img/logo.png"',
            'xlink:href="' + window.location.origin + '/static/benchmarks/img/logo.png"')
        const svgBlob = new Blob([svgData], {type: "image/svg+xml;charset=utf-8"});

        const downloadLink = document.createElement("a");
        downloadLink.href = URL.createObjectURL(svgBlob);
        downloadLink.download = getFileName(".svg");
        document.body.appendChild(downloadLink);
        downloadLink.click();
        document.body.removeChild(downloadLink);
    });

    function makeCSV() {
        // only data for selected benchmarks
        [filtered_data, x, y] = getDeduplicatedValues();
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
});
