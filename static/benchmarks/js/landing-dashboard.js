(function () {
    'use strict';

    var SVG_NS = 'http://www.w3.org/2000/svg';
    var DEFAULT_CAMERA = {yaw: -0.68, pitch: -0.34};

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

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value));
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
        var ratio = clamp((value - domain[0]) / (domain[1] - domain[0]), 0, 1);
        return output[0] + ratio * (output[1] - output[0]);
    }

    function pointColor(score, scoreExtent) {
        if (!Number.isFinite(score)) return '#7eb7a0';
        var ratio = scoreExtent[0] === scoreExtent[1]
            ? 0.5
            : (score - scoreExtent[0]) / (scoreExtent[1] - scoreExtent[0]);
        ratio = clamp(ratio, 0, 1);
        var start = [71, 183, 222];
        var end = [22, 139, 75];
        var channels = start.map(function (value, index) {
            return Math.round(value + (end[index] - value) * ratio);
        });
        return 'rgb(' + channels.join(',') + ')';
    }

    function robustCoordinateLimit(points, mode) {
        var coordinates = [];
        points.forEach(function (point) {
            coordinates.push(Math.abs(point.x), Math.abs(point.y));
            if (mode === '3d') coordinates.push(Math.abs(point.z));
        });
        coordinates.sort(function (left, right) { return left - right; });
        var index = Math.min(coordinates.length - 1, Math.floor(coordinates.length * 0.975));
        return Math.max(0.1, coordinates[index]);
    }

    function rotatePoint(point, camera) {
        var cosYaw = Math.cos(camera.yaw);
        var sinYaw = Math.sin(camera.yaw);
        var cosPitch = Math.cos(camera.pitch);
        var sinPitch = Math.sin(camera.pitch);
        var yawX = point.x * cosYaw + point.z * sinYaw;
        var yawZ = -point.x * sinYaw + point.z * cosYaw;
        return {
            x: yawX,
            y: point.y * cosPitch - yawZ * sinPitch,
            z: point.y * sinPitch + yawZ * cosPitch
        };
    }

    function projectPoint(point, camera, dimensions) {
        var rotated = rotatePoint(point, camera);
        var perspective = 4.8 / (4.8 - rotated.z * 0.55);
        return {
            x: dimensions.centerX + rotated.x * dimensions.scale * perspective,
            y: dimensions.centerY - rotated.y * dimensions.scale * perspective,
            z: rotated.z,
            perspective: perspective
        };
    }

    function setLine(line, start, end) {
        line.setAttribute('x1', start.x);
        line.setAttribute('y1', start.y);
        line.setAttribute('x2', end.x);
        line.setAttribute('y2', end.y);
    }

    function setSvgElementVisible(element, visible) {
        element.style.display = visible ? '' : 'none';
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
        var points = data && Array.isArray(data.points)
            ? data.points.filter(function (point) {
                return Number.isFinite(point.x) && Number.isFinite(point.y) && Number.isFinite(point.z);
            })
            : [];
        if (points.length < 3) {
            container.innerHTML = '<div class="landing-space__empty">Benchmark-space data is temporarily unavailable.</div>';
            return;
        }

        container.innerHTML = '';
        var width = 760;
        var height = 390;
        var dimensions = {centerX: 377, centerY: 194, scale: 120};
        var camera = {yaw: DEFAULT_CAMERA.yaw, pitch: DEFAULT_CAMERA.pitch};
        var mode = container.dataset.spaceMode === '3d' ? '3d' : '2d';
        var coordinateLimit3d = robustCoordinateLimit(points, '3d');
        var twoDimensionalMargin = {top: 24, right: 26, bottom: 49, left: 54};
        var xDomain = paddedExtent(points.map(function (point) { return point.x; }));
        var yDomain = paddedExtent(points.map(function (point) { return point.y; }));
        var finiteScores = points
            .map(function (point) { return Number(point.score); })
            .filter(Number.isFinite);
        var scoreExtent = finiteScores.length ? extent(finiteScores) : [0, 1];
        var variance = data.variance || [0, 0, 0];
        var dragging = false;
        var dragMoved = false;
        var suppressClick = false;
        var lastPointer = {x: 0, y: 0};

        var svg = svgElement('svg', {
            viewBox: '0 0 ' + width + ' ' + height,
            preserveAspectRatio: 'xMidYMid meet',
            role: 'group',
            tabindex: '0',
            'aria-label': 'Two-dimensional principal component map. Select a point to open its model page.'
        });
        var gridGroup = svgElement('g', {class: 'landing-space__grid'});
        var axesGroup = svgElement('g', {class: 'landing-space__axes'});
        var pointsGroup = svgElement('g', {class: 'landing-space__points'});
        var labelsGroup = svgElement('g', {class: 'landing-space__labels'});
        svg.appendChild(gridGroup);
        svg.appendChild(axesGroup);
        svg.appendChild(pointsGroup);
        svg.appendChild(labelsGroup);

        var gridLines3d = [];
        [-1, -0.5, 0, 0.5, 1].forEach(function (position) {
            [
                [{x: -1, y: -1, z: position}, {x: 1, y: -1, z: position}],
                [{x: position, y: -1, z: -1}, {x: position, y: -1, z: 1}]
            ].forEach(function (endpoints) {
                var line = svgElement('line', {class: 'landing-space__grid-line'});
                gridGroup.appendChild(line);
                gridLines3d.push({line: line, start: endpoints[0], end: endpoints[1]});
            });
        });

        var axisOrigin = {x: -1, y: -1, z: -1};
        var axisDefinitions = [
            {end: {x: 1.08, y: -1, z: -1}, label: 'PC1 · ' + variance[0] + '%'},
            {end: {x: -1, y: 1.08, z: -1}, label: 'PC2 · ' + variance[1] + '%'},
            {end: {x: -1, y: -1, z: 1.08}, label: 'PC3 · ' + variance[2] + '%'}
        ];
        var axes = axisDefinitions.map(function (definition, index) {
            var line = svgElement('line', {
                class: 'landing-space__axis landing-space__axis--' + (index + 1)
            });
            var label = svgElement('text', {
                class: 'landing-space__axis-label',
                'text-anchor': 'middle'
            });
            label.textContent = definition.label;
            axesGroup.appendChild(line);
            labelsGroup.appendChild(label);
            return {line: line, label: label, end: definition.end, index: index};
        });

        var tooltip = document.createElement('div');
        tooltip.className = 'landing-space__tooltip';
        tooltip.hidden = true;
        var legend = document.createElement('div');
        legend.className = 'landing-space__legend';
        legend.innerHTML = '<span>Brain-Score</span><i aria-hidden="true"></i><small>Lower</small><small>Higher</small>';
        container.appendChild(svg);
        container.appendChild(tooltip);
        container.appendChild(legend);

        function normalizedCoordinate(value, coordinateLimit) {
            return clamp(value / coordinateLimit, -1.18, 1.18);
        }

        var scenePoints = points.map(function (point) {
            var circle = svgElement('circle', {
                fill: pointColor(Number(point.score), scoreExtent),
                stroke: point.rank <= 5 ? '#ffffff' : 'rgba(255,255,255,0.82)',
                'stroke-width': point.rank <= 5 ? 2.2 : 1,
                class: 'landing-space__point',
                tabindex: '0',
                'aria-label': point.name + ', rank ' + point.rank
            });
            var title = svgElement('title');
            title.textContent = point.name + ', rank ' + point.rank;
            circle.appendChild(title);
            pointsGroup.appendChild(circle);
            return {
                point: point,
                circle: circle,
                coordinates3d: {
                    x: normalizedCoordinate(point.x, coordinateLimit3d),
                    y: normalizedCoordinate(point.y, coordinateLimit3d),
                    z: normalizedCoordinate(point.z, coordinateLimit3d)
                }
            };
        });

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

        function renderTwoDimensionalScene() {
            gridLines3d.forEach(function (gridLine) {
                setSvgElementVisible(gridLine.line, false);
            });
            var xAxisY = height - twoDimensionalMargin.bottom;
            axes.forEach(function (axis) {
                var isVisible = axis.index < 2;
                setSvgElementVisible(axis.line, isVisible);
                setSvgElementVisible(axis.label, isVisible);
                if (!isVisible) return;
                axis.label.removeAttribute('transform');
                if (axis.index === 0) {
                    setLine(
                        axis.line,
                        {x: twoDimensionalMargin.left, y: xAxisY},
                        {x: width - twoDimensionalMargin.right, y: xAxisY}
                    );
                    axis.label.textContent = 'PC1 (' + variance[0] + '% variance)';
                    axis.label.setAttribute('x', width / 2);
                    axis.label.setAttribute('y', height - 12);
                } else {
                    setLine(
                        axis.line,
                        {x: twoDimensionalMargin.left, y: twoDimensionalMargin.top},
                        {x: twoDimensionalMargin.left, y: xAxisY}
                    );
                    axis.label.textContent = 'PC2 (' + variance[1] + '% variance)';
                    axis.label.setAttribute('x', 15);
                    axis.label.setAttribute('y', height / 2);
                    axis.label.setAttribute('transform', 'rotate(-90 15 ' + (height / 2) + ')');
                }
            });

            scenePoints.slice().sort(function (left, right) {
                return right.point.rank - left.point.rank;
            }).forEach(function (scenePoint) {
                var point = scenePoint.point;
                scenePoint.circle.setAttribute('cx', scale(
                    point.x,
                    xDomain,
                    [twoDimensionalMargin.left, width - twoDimensionalMargin.right]
                ));
                scenePoint.circle.setAttribute('cy', scale(
                    point.y,
                    yDomain,
                    [xAxisY, twoDimensionalMargin.top]
                ));
                scenePoint.circle.setAttribute('r', point.rank <= 5 ? 6 : 4.5);
                scenePoint.circle.setAttribute('opacity', 0.78);
                pointsGroup.appendChild(scenePoint.circle);
            });
        }

        function renderThreeDimensionalScene() {
            gridLines3d.forEach(function (gridLine) {
                setSvgElementVisible(gridLine.line, true);
                setLine(
                    gridLine.line,
                    projectPoint(gridLine.start, camera, dimensions),
                    projectPoint(gridLine.end, camera, dimensions)
                );
            });
            var origin = projectPoint(axisOrigin, camera, dimensions);
            axes.forEach(function (axis) {
                setSvgElementVisible(axis.line, true);
                setSvgElementVisible(axis.label, true);
                axis.label.removeAttribute('transform');
                axis.label.textContent = axisDefinitions[axis.index].label;
                var endpoint = projectPoint(axis.end, camera, dimensions);
                setLine(axis.line, origin, endpoint);
                var xOffset = axis.index === 0 ? 7 : axis.index === 2 ? -5 : 0;
                var yOffset = axis.index === 1 ? -8 : 15;
                axis.label.setAttribute('x', clamp(endpoint.x + xOffset, 44, width - 44));
                axis.label.setAttribute('y', clamp(endpoint.y + yOffset, 18, height - 12));
            });

            var projectedPoints = scenePoints.map(function (scenePoint) {
                return {
                    scenePoint: scenePoint,
                    projected: projectPoint(scenePoint.coordinates3d, camera, dimensions)
                };
            }).sort(function (left, right) {
                return left.projected.z - right.projected.z;
            });

            projectedPoints.forEach(function (item) {
                var point = item.scenePoint.point;
                var projected = item.projected;
                var depthRatio = clamp((projected.z + 1.4) / 2.8, 0, 1);
                var baseRadius = point.rank <= 5 ? 5.8 : 4.2;
                item.scenePoint.circle.setAttribute('cx', projected.x);
                item.scenePoint.circle.setAttribute('cy', projected.y);
                item.scenePoint.circle.setAttribute('r', baseRadius * projected.perspective * (0.82 + depthRatio * 0.32));
                item.scenePoint.circle.setAttribute('opacity', 0.48 + depthRatio * 0.43);
                pointsGroup.appendChild(item.scenePoint.circle);
            });
        }

        function renderScene() {
            if (mode === '2d') renderTwoDimensionalScene();
            else renderThreeDimensionalScene();
        }

        scenePoints.forEach(function (scenePoint) {
            var circle = scenePoint.circle;
            var point = scenePoint.point;
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
                var bounds = circle.getBoundingClientRect();
                showTooltip(point, bounds.left + bounds.width / 2, bounds.top + bounds.height / 2);
            });
            circle.addEventListener('blur', function () {
                tooltip.hidden = true;
            });
            circle.addEventListener('click', function () {
                if (!suppressClick) window.location.assign('/model/vision/' + point.id);
            });
            circle.addEventListener('keydown', function (event) {
                if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    window.location.assign('/model/vision/' + point.id);
                }
            });
        });

        svg.addEventListener('pointerdown', function (event) {
            if (mode !== '3d' || event.button !== 0) return;
            dragging = true;
            dragMoved = false;
            lastPointer = {x: event.clientX, y: event.clientY};
            svg.setPointerCapture(event.pointerId);
            svg.classList.add('is-dragging');
        });
        svg.addEventListener('pointermove', function (event) {
            if (!dragging) return;
            var deltaX = event.clientX - lastPointer.x;
            var deltaY = event.clientY - lastPointer.y;
            if (Math.abs(deltaX) + Math.abs(deltaY) > 1) dragMoved = true;
            camera.yaw += deltaX * 0.008;
            camera.pitch = clamp(camera.pitch - deltaY * 0.008, -1.12, 1.12);
            lastPointer = {x: event.clientX, y: event.clientY};
            renderScene();
        });
        function finishDrag(event) {
            if (!dragging) return;
            dragging = false;
            suppressClick = dragMoved;
            svg.classList.remove('is-dragging');
            if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
            window.setTimeout(function () { suppressClick = false; }, 0);
        }
        svg.addEventListener('pointerup', finishDrag);
        svg.addEventListener('pointercancel', finishDrag);
        svg.addEventListener('keydown', function (event) {
            if (mode !== '3d') return;
            var handled = true;
            if (event.key === 'ArrowLeft') camera.yaw -= 0.12;
            else if (event.key === 'ArrowRight') camera.yaw += 0.12;
            else if (event.key === 'ArrowUp') camera.pitch = clamp(camera.pitch + 0.12, -1.12, 1.12);
            else if (event.key === 'ArrowDown') camera.pitch = clamp(camera.pitch - 0.12, -1.12, 1.12);
            else if (event.key === 'Home') {
                camera.yaw = DEFAULT_CAMERA.yaw;
                camera.pitch = DEFAULT_CAMERA.pitch;
            } else handled = false;
            if (handled) {
                event.preventDefault();
                renderScene();
            }
        });

        var resetButton = document.getElementById('landing-space-reset');
        if (resetButton) {
            resetButton.addEventListener('click', function () {
                camera.yaw = DEFAULT_CAMERA.yaw;
                camera.pitch = DEFAULT_CAMERA.pitch;
                renderScene();
                svg.focus();
            });
        }

        var title = document.getElementById('landing-space-title');
        var hint = document.getElementById('landing-space-hint');
        var method = document.getElementById('landing-space-method');
        var modeButtons = document.querySelectorAll('.landing-space-toggle button[data-space-mode]');

        function setMode(nextMode) {
            mode = nextMode === '3d' ? '3d' : '2d';
            container.dataset.spaceMode = mode;
            modeButtons.forEach(function (button) {
                button.setAttribute('aria-pressed', button.dataset.spaceMode === mode ? 'true' : 'false');
            });
            if (title) title.textContent = 'The ' + mode.toUpperCase() + ' benchmark space';
            if (hint) {
                hint.innerHTML = mode === '3d'
                    ? '<i class="fa-regular fa-hand-pointer" aria-hidden="true"></i> Drag to rotate'
                    : 'PC1 &times; PC2';
            }
            if (resetButton) resetButton.hidden = mode !== '3d';
            if (method) {
                method.textContent = mode === '3d'
                    ? 'A three-component preview of the highest-ranked public models with complete scores across the five displayed branches. Drag to rotate; hover or focus a point for model details.'
                    : 'A two-component preview of the highest-ranked public models with complete scores across the five displayed branches. Hover or focus a point for model details.';
            }
            svg.setAttribute('aria-label', mode === '3d'
                ? 'Interactive three-dimensional principal component map. Drag or use the arrow keys to rotate. Select a point to open its model page.'
                : 'Two-dimensional principal component map. Select a point to open its model page.');
            svg.classList.toggle('is-3d', mode === '3d');
            container.classList.toggle('is-2d', mode === '2d');
            legend.hidden = mode === '2d';
            renderScene();
        }

        modeButtons.forEach(function (button) {
            button.addEventListener('click', function () {
                setMode(button.dataset.spaceMode);
            });
        });

        setMode(mode);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', renderBenchmarkSpace);
    } else {
        renderBenchmarkSpace();
    }
})();
