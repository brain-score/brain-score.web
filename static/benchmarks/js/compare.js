$(document).ready(function () {
    // adapted from http://bl.ocks.org/peterssonjonas/4a0e7cb8d23231243e0e

    var container_selector = "div#comparison-scatter",
        xlabel_selector = '#xlabel',
        ylabel_selector = '#ylabel',
        label_description_selector = "#label-description";

    // make sure we have a container to work with, otherwise abort
    if ($(container_selector).length < 1) {
        return;
    }

    var margin = {top: 0, right: 0, bottom: 40, left: 60},
        outerWidth = 600,
        outerHeight = 400,
        width = outerWidth - margin.left - margin.right,
        height = outerHeight - margin.top - margin.bottom;

    var dot_size = 8,
        color = '#078930';

    var idKey = "model",
        xKey = null,
        yKey = null;

    var g = null,
        xAxis = null,
        yAxis = null;

    var x = null,
        y = null;

    var svg = d3.select(container_selector)
        .append("svg")
        .attr("width", outerWidth)
        .attr("height", outerHeight)
        .attr("fill", "white");

    function zoom() {
        svg.select(".x.axis").call(xAxis);
        svg.select(".y.axis").call(yAxis);

        svg.selectAll(".dot")
            .attr("transform", transform);

    }

    function transform(d) {
        return "translate(" + x(d[xKey]) + "," + y(d[yKey]) + ")";
    }

    // Function to make a string human-readable
    function humanReadable(text) {
        return text
            .replace(/([a-z])([A-Z])/g, '$1 $2')  // Adds space before capital letters in camel case
            .replace(/(\b[a-zA-Z]+)(\d+)(?!V1\b)/g, '$1 $2')  // Adds space between letters and digits, ignoring "V1"
            .replace(/(\d+)([a-zA-Z])(?!V1\b)/g, '$1 $2')  // Adds space between digits and letters, ignoring "V1"
            .replace(/[_]/g, ' ')  // Replace all '_' with spaces
            .replace(/[-]/g, ' - ');  // Replace all '-' with ' - '
    }

// from http://bl.ocks.org/williaster/10ef968ccfdc71c30ef8
// Handler for dropdown value change
    var updatePlot = function () {
        xKey = $(xlabel_selector).prop('value') + "-score";
        yKey = $(ylabel_selector).prop('value') + "-score";
        var xName = humanReadable($(xlabel_selector).find('option:selected').text()),
            yName = humanReadable($(ylabel_selector).find('option:selected').text());
        $(label_description_selector).html(xName + ' <span>vs</span> ' + yName);


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

        // filter data to guard against empty "" or "X" scores turning into NaNs that mess up d3
        var filtered_data = comparison_data.filter(row =>
            row[xKey].length > 0 && !isNaN(row[xKey]) &&
            row[yKey].length > 0 && !isNaN(row[yKey]));

        // axes range
        var xMax = d3.max(filtered_data, function (d) {
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

        // zoom
        var zoomBeh = d3.behavior.zoom()
            .x(x)
            .y(y)
            .scaleExtent([0, 500])
            .on("zoom", zoom);

        g = svg
            .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
            .call(zoomBeh);

        // axes
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
            .attr("x", width / 2)
            .attr("y",  margin.bottom - 6)
            .attr("text-anchor", "middle")
            .attr("fill", "currentColor")
            .text(xName);

        g.append("g")
            .classed("y axis", true)
            .call(yAxis)
            .append("text")
            .attr("text-anchor", "middle")
            .attr("x", -height / 2)
            .attr("y", -36)
            .attr("fill", "currentColor")
            .attr("transform", "rotate(-90)")
            .text(yName);

        // create svg objects
        var objects = g.append("svg")
            .classed("objects", true)
            .attr("width", width)
            .attr("height", height);

        // fill svg with data and position
        objects.selectAll(".dot")
            .data(filtered_data)
            .enter().append("circle")
            .classed("dot", true)
            .attr("r", dot_size)
            .attr("transform", transform)
            .style("fill", color)
            .on("mouseover", tip.show)
            .on("mouseout", tip.hide);
    };

    $(xlabel_selector + ', ' + ylabel_selector)
        .on("change", updatePlot);

    updatePlot();

    $('#xlabel').select2({
        placeholder: "Select or type",
    });

    $('#ylabel').select2({
        placeholder: "Select or type",
    });

    function setDropdownValue(xName, yName) {
        const select_xlabel = document.getElementById('xlabel');
        select_xlabel.value = xName;
        const select_ylabel = document.getElementById('ylabel');
        select_ylabel.value = yName;
        updatePlot();
        const element = document.getElementById("controls-container");
        element.scrollIntoView({ behavior: "smooth" });
    };

    function getFileName(extension) {
        var file_name = $(xlabel_selector).find('option:selected').text() + "_VS_" + $(ylabel_selector).find('option:selected').text() + extension;
        return file_name
    };

    function inlineStyles(element) {
        console.log(element);
        const cssStyles = window.getComputedStyle(element);
        console.log(cssStyles);
        for (let i = 0; i < cssStyles.length; i++) {
            const styleName = cssStyles[i];
            console.log(styleName);
            console.log(element);
            element.style[styleName] = cssStyles.getPropertyValue(styleName);
    }

    Array.from(element.children).forEach(child => inlineStyles(child));
   }
 

    $("#downloadSVGButton").click(function() {
        var serializer = new XMLSerializer();
        const svgNode = d3.select('svg').node();
        const clonedSvg = svgNode.cloneNode(true);
        inlineStyles(clonedSvg);
        var xmlString = serializer.serializeToString(clonedSvg);
        var imgData = 'data:image/svg+xml;base64,' + btoa(xmlString);
        
        // Create a temporary anchor element
        const a = document.createElement('a');
        a.href = imgData;
        a.download = getFileName(".svg"); // Set the download attribute with a filename

        // Append anchor to body
        document.body.appendChild(a);

        // Trigger download
        a.click();

        // Remove anchor from body
        document.body.removeChild(a);
    });

    function makeCSV() {
        const headers = Object.keys(data[0]);
        const rows = data.map(row => headers.map(field => JSON.stringify(row[field])).join(','));
        return [headers.join(','), ...rows].join('\n');
    };

    $("#downloadCSVButton").click(function() {
        csvData = makeCSV() 
        // Create a Blob from the CSV string
        const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);

        // Create a temporary anchor element
        const a = document.createElement('a');
        a.href = url;
        var file_name = getFileName(".csv")
        a.download = file_name; // Set the download attribute with a filename

        // Append anchor to body
        document.body.appendChild(a);

        // Trigger download
        a.click();

        // Remove anchor from body
        document.body.removeChild(a);
    });

    $("#objectClassificationButton").click(function() {
        setDropdownValue("ImageNet-top1_v1", "average_vision_v0")
    });
    $("#objectClassificationButton2").click(function() {
        setDropdownValue("average_vision_v0", "neural_vision_v0")
    });
    $("#objectClassificationButton3").click(function() {
        setDropdownValue("neural_vision_v0", "average_vision_v0")
    });
});
