// adapted from http://bl.ocks.org/peterssonjonas/4a0e7cb8d23231243e0e

var margin = { top: 0, right: 0, bottom: 20, left: 60 },
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

var container_selector = "#analysis div#brain-score",
    figure_selector = "#analysis #brain-score-fig",
    xlabel_selector = figure_selector + ' #xlabel',
    ylabel_selector = figure_selector + ' #ylabel',
    label_description_selector = figure_selector + " figcaption #label-description";

d3.json("/static/benchmarks/fixture-scores-javascript.json", function(error, data) {
    var svg = d3.select(container_selector)
        .append("svg")
        .attr("width", outerWidth)
        .attr("height", outerHeight);

    function zoom() {
        svg.select(".x.axis").call(xAxis);
        svg.select(".y.axis").call(yAxis);

        svg.selectAll(".dot")
            .attr("transform", transform)
            .attr("r", dot_size * d3.event.scale);
    }

    function transform(d) {
        return "translate(" + x(d[xKey]) + "," + y(d[yKey]) + ")";
    }

    // from http://bl.ocks.org/williaster/10ef968ccfdc71c30ef8
    // Handler for dropdown value change
    var updatePlot = function() {
        xKey = $(xlabel_selector).prop('value') + "-score";
        yKey = $(ylabel_selector).prop('value') + "-score";
        var xName = $(xlabel_selector).find('option:selected').text(),
            yName = $(ylabel_selector).find('option:selected').text();
        $(label_description_selector).text(xName + ' vs ' + yName);


        d3.selectAll("svg > *").remove();

        // tip
        var tip = d3.tip()
            .attr("class", "d3-tip")
            .offset([-10, 0])
            .html(function(d) {
                return "<strong>" + d[idKey] + "</strong><br>" +
                    xKey + ": " + d[xKey].toFixed(3) + "<br>" +
                    yKey + ": " + d[yKey].toFixed(3);
            });

        svg.call(tip);

        // axes range
        var xMax = d3.max(data, function(d) { return d[xKey]; }) * 1.05,
            xMin = d3.min(data, function(d) { return d[xKey]; }) * .95,
            yMax = d3.max(data, function(d) { return d[yKey]; }) * 1.05,
            yMin = d3.min(data, function(d) { return d[yKey]; }) * .95;

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
            .call(xAxis);

        g.append("g")
            .classed("y axis", true)
            .call(yAxis);

        // g.append("g")
        //     .append("text")
        //     .attr("x", 375)
        //     .attr("y", 350)
        //     .text("r=" + 3 + " (p=" + 0.05 + ")")
        //     .attr("font-size", "18px");

        // data
        var objects = g.append("svg")
            .classed("objects", true)
            .attr("width", width)
            .attr("height", height);

        objects.selectAll(".dot")
            .data(data)
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
});