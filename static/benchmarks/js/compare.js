$(document).ready(function () {
    // adapted from http://bl.ocks.org/peterssonjonas/4a0e7cb8d23231243e0e

    const container_selector = "div#comparison-scatter";
    const xlabel_selector = '#xlabel';
    const ylabel_selector = '#ylabel';

    // make sure we have a container to work with, otherwise abort
    if ($(container_selector).length < 1) {
        return;
    }

    const margin = {top: 0, right: 0, bottom: 40, left: 60},
        outerWidth = $(container_selector).width(),
        outerHeight = $(container_selector).width() * 2/3,
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

    function getDeduplicatedValues() {
        // Filter data to guard against empty "" or "X" scores turning into NaNs
        const filtered_data = comparison_data.filter(row =>
            row[xKey].length > 0 && !isNaN(row[xKey]) &&
            row[yKey].length > 0 && !isNaN(row[yKey]));

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
        svg.select(".regression-line")
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
        const sumX = xArr.reduce((a, b) => a + b, 0);
        const sumY = yArr.reduce((a, b) => a + b, 0);
        const sumXY = xArr.map((xi, i) => xi * yArr[i]).reduce((a, b) => a + b, 0);
        const sumX2 = xArr.map(xi => xi * xi).reduce((a, b) => a + b, 0);
        const sumY2 = yArr.map(yi => yi * yi).reduce((a, b) => a + b, 0);

        const numerator = (n * sumXY) - (sumX * sumY);
        const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

        const correlation = denominator === 0 ? 0 : numerator / denominator;
        const rSquared = correlation * correlation;  // Calculate R^2

        // // Calculate the t-statistic
        const tStatistic = correlation * Math.sqrt((n - 2) / (1 - rSquared));
        // // Calculate the p-value (2-tailed) using jStat's cumulative distribution function
        const pValue = 2 * (1 - jStat.studentt.cdf(Math.abs(tStatistic), n - 2));

        return {correlation, rSquared, pValue};  // Return correlation, R^2, and p-value
    }


    // Calculate Linear Regression Slope and Intercept
    function calculateLinearRegression(xArr, yArr) {
        const n = xArr.length;
        const sumX = xArr.reduce((a, b) => a + b, 0);
        const sumY = yArr.reduce((a, b) => a + b, 0);
        const sumXY = xArr.map((xi, i) => xi * yArr[i]).reduce((a, b) => a + b, 0);
        const sumX2 = xArr.map(xi => xi * xi).reduce((a, b) => a + b, 0);
        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        const intercept = (sumY - slope * sumX) / n;
        return {slope, intercept};
    }


    // Define the SVG and clip path
    svg.append("defs")
        .append("clipPath")
        .attr("id", "clip")
        .append("rect")
        .attr("x", margin.left)
        .attr("y", margin.top)
        .attr("width", width)
        .attr("height", height);

    function updatePlot() {
        xKey = $(xlabel_selector).prop('value') + "-score";
        yKey = $(ylabel_selector).prop('value') + "-score";

        const xName = $(xlabel_selector).find('option:selected').text();
        const yName = $(ylabel_selector).find('option:selected').text();

        d3.selectAll("svg > *").remove();

        // tip
        var tip = d3.tip()
            .attr("class", "d3-tip")
            .offset([-10, 0])
            .html(function (d) {
                return "<strong>" + d[idKey] + "</strong><br>" +
                    xKey + ": " + d[xKey] + "<br>" +
                    yKey + ": " + d[yKey];
            });

        svg.call(tip);

        const [filtered_data, xValues, yValues] = getDeduplicatedValues();
        const {correlation, rSquared, pValue} = calculateCorrelation(xValues, yValues);

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
            .attr("clip-path", "url(#clip)")  // Apply clip path here
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
            .text(xName);  // Use the human-readable xName here

        svg.selectAll(".x.axis text")
            .style("fill", "black");

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
            .text(yName);  // Use the human-readable yName here

        svg.selectAll(".y.axis text")
            .style("fill", "black");

        // Correlation plotting -- position towards the top, horizontally next to each other
        g.append("text")
            .attr("class", "correlation-text")
            .attr("x", 150)
            .attr("y", 20)
            .attr("fill", "black")
            .style("font-size", "16px")
            .text("Pearson R: " + correlation.toFixed(2));

        g.append("text")
            .attr("class", "r2-text")
            .attr("x", 280)
            .attr("y", 20)
            .attr("fill", "black")
            .style("font-size", "16px")
            .text("R²: " + rSquared.toFixed(2));

        g.append("text")
            .attr("class", "r2-text")
            .attr("x", 355)
            .attr("y", 20)
            .attr("fill", "black")
            .style("font-size", "16px")
            .text(() => {
                // Format p-value conditionally
                return pValue >= 0.01
                    ? `p-value: ${pValue.toFixed(2)}`  // Show two decimal places
                    : `p-value: ${pValue.toExponential(1).replace(/^(\d)\.?\d*e/, '$1 × 10^')}`; // Exponential format with 1 digit
            });

        // plotting the line
        g.append("line")
            .attr("class", "regression-line")
            .attr("x1", x(xStart))
            .attr("y1", y(yStart))
            .attr("x2", x(xEnd))
            .attr("y2", y(yEnd))
            .attr("stroke-width", 2)
            .attr("stroke", "lightgrey")
            .attr("stroke-dasharray", "4,4")
            .attr("clip-path", "url(#clip)");  // Ensure line is also clipped


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

        // add Brain-Score logo
        g.append("svg:image")
            .attr('x', 5)
            .attr('y', 0)
            .attr('width', 120)
            .attr('height', 28)
            .attr("xlink:href", logo_url);
    }

    $(xlabel_selector + ', ' + ylabel_selector)
        .on("change", updatePlot);

    updatePlot();

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
        const serializer = new XMLSerializer();
        const svgNode = d3.select('svg').node();
        const clonedSvg = svgNode.cloneNode(true);
        inlineStyles(clonedSvg);
        const xmlString = serializer.serializeToString(clonedSvg);
        const imgData = 'data:image/svg+xml;base64,' + btoa(xmlString);

        // Create a temporary anchor element
        const a = document.createElement('a');
        a.href = imgData;
        a.download = getFileName(".svg"); // Set the download attribute with a filename

        document.body.appendChild(a); // Append anchor to body
        a.click(); // Trigger download
        document.body.removeChild(a); // Remove anchor from body
    });

    function makeCSV() {
        const headers = Object.keys(comparison_data[0]);
        const rows = comparison_data.map(row => headers.map(field => JSON.stringify(row[field])).join(','));
        return [headers.join(','), ...rows].join('\n');
    }

    $("#downloadCSVButton").click(function () {
        csvData = makeCSV()
        // Create a Blob from the CSV string
        const blob = new Blob([csvData], {type: 'text/csv;charset=utf-8;'});
        const url = URL.createObjectURL(blob);

        // Create a temporary anchor element
        const a = document.createElement('a');
        a.href = url;
        const file_name = getFileName(".csv")
        a.download = file_name; // Set the download attribute with a filename

        // Append anchor to body
        document.body.appendChild(a);

        // Trigger download
        a.click();

        // Remove anchor from body
        document.body.removeChild(a);
    });

    // example selections for correlations in literature
    $(".comparison_selector").click(function () {
        $(this).children('div').show(); // unhide own contents
        $(".comparison_selector").not(this).children('div').hide(); // hide others
        const x = $(this).attr('data-benchmark-x');
        const y = $(this).attr('data-benchmark-y');
        $("#xlabel").val(x).trigger('change');
        $("#ylabel").val(y).trigger('change');
        updatePlot();
    });
    $(".comparison_selector").children('div').hide(); // hide all initially -- do here so that non-js still works
});
