(function () {
    'use strict';

    var SVG_NS = 'http://www.w3.org/2000/svg';

    function svgElement(name, attributes) {
        var element = document.createElementNS(SVG_NS, name);
        Object.keys(attributes || {}).forEach(function (key) {
            element.setAttribute(key, attributes[key]);
        });
        return element;
    }

    function extent(values) {
        return [Math.min.apply(null, values), Math.max.apply(null, values)];
    }

    function paddedExtent(values) {
        var sorted = values.slice().sort(function (left, right) { return left - right; });
        var trim = sorted.length >= 20 ? Math.floor(sorted.length * 0.025) : 0;
        var bounds = [sorted[trim], sorted[sorted.length - trim - 1]];
        var range = bounds[1] - bounds[0];
        var padding = range > 0 ? range * 0.12 : 1;
        return [bounds[0] - padding, bounds[1] + padding];
    }

    function scale(value, domain, output) {
        if (domain[0] === domain[1]) return (output[0] + output[1]) / 2;
        var ratio = (value - domain[0]) / (domain[1] - domain[0]);
        ratio = Math.max(0, Math.min(1, ratio));
        return output[0] + ratio * (output[1] - output[0]);
    }

    function pointColor(score, scoreExtent) {
        if (!Number.isFinite(score)) return '#7eb7a0';
        var ratio = scoreExtent[0] === scoreExtent[1]
            ? 0.5
            : (score - scoreExtent[0]) / (scoreExtent[1] - scoreExtent[0]);
        ratio = Math.max(0, Math.min(1, ratio));
        var start = [71, 183, 222];
        var end = [22, 139, 75];
        var channels = start.map(function (value, index) {
            return Math.round(value + (end[index] - value) * ratio);
        });
        return 'rgb(' + channels.join(',') + ')';
    }

    function addAxisLabel(svg, text, x, y, transform) {
        var label = svgElement('text', {
            x: x,
            y: y,
            class: 'landing-space__axis-label',
            'text-anchor': 'middle'
        });
        if (transform) label.setAttribute('transform', transform);
        label.textContent = text;
        svg.appendChild(label);
    }

    function renderBenchmarkSpace() {
        var container = document.getElementById('landing-benchmark-space');
        var dataElement = document.getElementById('landing-benchmark-space-data');
        if (!container || !dataElement) return;

        var data;
        try {
            data = JSON.parse(dataElement.textContent);
        } catch (error) {
            data = null;
        }
        var points = data && Array.isArray(data.points) ? data.points : [];
        if (points.length < 3) {
            container.innerHTML = '<div class="landing-space__empty">Benchmark-space data is temporarily unavailable.</div>';
            return;
        }

        container.innerHTML = '';
        var width = 760;
        var height = 390;
        var margin = {top: 24, right: 26, bottom: 49, left: 54};
        var svg = svgElement('svg', {
            viewBox: '0 0 ' + width + ' ' + height,
            preserveAspectRatio: 'xMidYMid meet',
            role: 'group',
            'aria-label': 'Interactive principal component map. Select a point to open its model page.'
        });
        var xDomain = paddedExtent(points.map(function (point) { return point.x; }));
        var yDomain = paddedExtent(points.map(function (point) { return point.y; }));
        var finiteScores = points
            .map(function (point) { return Number(point.score); })
            .filter(Number.isFinite);
        var scoreExtent = finiteScores.length ? extent(finiteScores) : [0, 1];

        var xAxisY = height - margin.bottom;
        svg.appendChild(svgElement('line', {
            x1: margin.left,
            y1: xAxisY,
            x2: width - margin.right,
            y2: xAxisY,
            class: 'landing-space__axis'
        }));
        svg.appendChild(svgElement('line', {
            x1: margin.left,
            y1: margin.top,
            x2: margin.left,
            y2: xAxisY,
            class: 'landing-space__axis'
        }));

        var variance = data.variance || [0, 0];
        addAxisLabel(svg, 'PC1 (' + variance[0] + '% variance)', width / 2, height - 12);
        addAxisLabel(
            svg,
            'PC2 (' + variance[1] + '% variance)',
            15,
            height / 2,
            'rotate(-90 15 ' + (height / 2) + ')'
        );

        var tooltip = document.createElement('div');
        tooltip.className = 'landing-space__tooltip';
        tooltip.hidden = true;
        container.appendChild(svg);
        container.appendChild(tooltip);

        function showTooltip(point, clientX, clientY) {
            var score = Number(point.score);
            tooltip.innerHTML = '<strong></strong><span></span>';
            tooltip.querySelector('strong').textContent = point.name;
            tooltip.querySelector('span').textContent =
                'Rank ' + point.rank + (Number.isFinite(score) ? ' · Brain-Score ' + score.toFixed(3) : '');
            tooltip.hidden = false;
            var bounds = container.getBoundingClientRect();
            var left = clientX - bounds.left + 12;
            var top = clientY - bounds.top + 12;
            if (left > bounds.width - 250) left = Math.max(8, left - 250);
            if (top > bounds.height - 75) top = Math.max(8, top - 75);
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        }

        points.slice().sort(function (left, right) {
            return right.rank - left.rank;
        }).forEach(function (point, index) {
            var cx = scale(point.x, xDomain, [margin.left, width - margin.right]);
            var cy = scale(point.y, yDomain, [xAxisY, margin.top]);
            var topModel = point.rank <= 5;
            var circle = svgElement('circle', {
                cx: cx,
                cy: cy,
                r: topModel ? 6 : 4.5,
                fill: pointColor(Number(point.score), scoreExtent),
                stroke: topModel ? '#ffffff' : 'rgba(255,255,255,0.75)',
                'stroke-width': topModel ? 2 : 1,
                class: 'landing-space__point',
                tabindex: '0',
                'aria-label': point.name + ', rank ' + point.rank,
                style: 'animation-delay:' + Math.min(index * 12, 450) + 'ms'
            });
            var title = svgElement('title');
            title.textContent = point.name + ', rank ' + point.rank;
            circle.appendChild(title);
            circle.addEventListener('mousemove', function (event) {
                showTooltip(point, event.clientX, event.clientY);
            });
            circle.addEventListener('mouseenter', function (event) {
                showTooltip(point, event.clientX, event.clientY);
            });
            circle.addEventListener('mouseleave', function () {
                tooltip.hidden = true;
            });
            circle.addEventListener('focus', function () {
                var bounds = container.getBoundingClientRect();
                showTooltip(
                    point,
                    bounds.left + (cx / width) * bounds.width,
                    bounds.top + (cy / height) * bounds.height
                );
            });
            circle.addEventListener('blur', function () {
                tooltip.hidden = true;
            });
            circle.addEventListener('click', function () {
                window.location.assign('/model/vision/' + point.id);
            });
            circle.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    window.location.assign('/model/vision/' + point.id);
                }
            });
            svg.appendChild(circle);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', renderBenchmarkSpace);
    } else {
        renderBenchmarkSpace();
    }
})();
