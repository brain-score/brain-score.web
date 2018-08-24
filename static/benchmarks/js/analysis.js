// adapted from http://bl.ocks.org/peterssonjonas/4a0e7cb8d23231243e0e

var margin = { top: 0, right: 0, bottom: 40, left: 50 },
    outerWidth = 600,
    outerHeight = 400,
    width = outerWidth - margin.left - margin.right,
    height = outerHeight - margin.top - margin.bottom;

var x = d3.scale.linear()
    .range([0, width]).nice();

var y = d3.scale.linear()
    .range([height, 0]).nice();

var idKey = "name",
    xKey = "imagenet_top1",
    yKey = "brain_score";

d3.json("/static/benchmarks/fixture.json", function(data) {
    data = data.map(function(row) {return row.fields});

    var xMax = d3.max(data, function(d) { return d[xKey]; }) * 1.05,
        xMin = d3.min(data, function(d) { return d[xKey]; }) * .95,
        yMax = d3.max(data, function(d) { return d[yKey]; }) * 1.05,
        yMin = d3.min(data, function(d) { return d[yKey]; }) * .95;

    x.domain([xMin, xMax]);
    y.domain([yMin, yMax]);

    var xAxis = d3.svg.axis()
        .scale(x)
        .orient("bottom")
        .tickSize(-height);

    var yAxis = d3.svg.axis()
        .scale(y)
        .orient("left")
        .tickSize(-width);

    var tip = d3.tip()
        .attr("class", "d3-tip")
        .offset([-10, 0])
        .html(function(d) {
            return "<strong>" + d[idKey] + "</strong><br>" +
                xKey + ": " + d[xKey].toFixed(2) + "<br>" +
                yKey + ": " + d[yKey].toFixed(2);
        });

    var zoomBeh = d3.behavior.zoom()
        .x(x)
        .y(y)
        .scaleExtent([0, 500])
        .on("zoom", zoom);

    var svg = d3.select("#analysis #brain-score")
        .append("svg")
        .attr("width", outerWidth)
        .attr("height", outerHeight)
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")")
        .call(zoomBeh);

    svg.call(tip);

    // axes
    svg.append("rect")
        .attr("width", width)
        .attr("height", height);

    svg.append("g")
        .classed("x axis", true)
        .attr("transform", "translate(0," + height + ")")
        .call(xAxis)
        .append("text")
        .classed("label", true)
        .attr("x", margin.left + width / 2)
        .attr("y", margin.bottom - 10)
        .style("text-anchor", "end")
        .text(xKey);

    svg.append("g")
        .classed("y axis", true)
        .call(yAxis)
        .append("text")
        .classed("label", true)
        .attr("transform", "rotate(-90)")
        .attr("x", margin.bottom - height / 2)
        .attr("y", -margin.left)
        .attr("dy", ".71em")
        .style("text-anchor", "end")
        .text(yKey);

    var objects = svg.append("svg")
        .classed("objects", true)
        .attr("width", width)
        .attr("height", height);

    objects.append("svg:line")
        .classed("axisLine hAxisLine", true)
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", width)
        .attr("y2", 0)
        .attr("transform", "translate(0," + height + ")");

    objects.append("svg:line")
        .classed("axisLine vAxisLine", true)
        .attr("x1", 0)
        .attr("y1", 0)
        .attr("x2", 0)
        .attr("y2", height);

    // data
    objects.selectAll(".dot")
        .data(data)
        .enter().append("circle")
        .classed("dot", true)
        .attr("r", 5)
        .attr("transform", transform)
        .style("fill", 'purple')
        .on("mouseover", tip.show)
        .on("mouseout", tip.hide);

    d3.select("input").on("click", change);

    function change() {
        xMax = d3.max(data, function(d) { return d[xKey]; });
        xMin = d3.min(data, function(d) { return d[xKey]; });

        zoomBeh.x(x.domain([xMin, xMax])).y(y.domain([yMin, yMax]));

        var svg = d3.select("#scatter").transition();

        svg.select(".x.axis").duration(750).call(xAxis).select(".label").text(xKey);

        objects.selectAll(".dot")
            .transition().duration(1000)
            .attr("transform", transform);
    }

    function zoom() {
        svg.select(".x.axis").call(xAxis);
        svg.select(".y.axis").call(yAxis);

        svg.selectAll(".dot")
            .attr("transform", transform)
            .attr("r", 5 * d3.event.scale);
    }

    function transform(d) {
        return "translate(" + x(d[xKey]) + "," + y(d[yKey]) + ")";
    }
});