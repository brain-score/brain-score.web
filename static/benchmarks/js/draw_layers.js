let currentlyHighlightedRect = null;
const svg = d3.select("svg");
console.log("draw_layers.js loaded");

let selectedLayers = [];
let currentlyShownLayer = null;

const raw = document.getElementById("layers-json");
if (!raw) {
    console.error("layers-json not found!");
}

const allData = JSON.parse(document.getElementById('layers-json').textContent);
console.log("Full parsed JSON:", allData);

const regionData = allData["Region"] || {};
const descriptionData = allData["Visualization-Description"] || {};

function regionHasLayer(layerName) {
    return Object.values(regionData).includes(layerName);
}

function showLayerMetadata(layerName, event, groupElement) {
    const box = document.getElementById("layer-info-box");
    if (!box) return;

    if (currentlyHighlightedRect) {
        currentlyHighlightedRect.select(".front-face")
            .attr("stroke", "black")
            .style("filter", "drop-shadow(2px 2px 2px rgba(0, 0, 0, 0.4))");
        currentlyHighlightedRect.select(".side-face")
            .attr("stroke", "black");
    }
    groupElement.select(".front-face")
        .attr("stroke", "blue")
        .style("filter", "drop-shadow(2px 2px 2px rgba(66, 135, 245, 0.8))");

    groupElement.select(".side-face")
        .attr("stroke", "blue")
        .style("filter", "drop-shadow(2px 2px 2px rgba(66, 135, 245, 0.8))");

    currentlyHighlightedRect = groupElement;

    const metadata = descriptionData[layerName]?.metadata;

    if (metadata) {
        let html = `<strong>Layer: ${layerName}</strong><br>`;
        for (const [key, value] of Object.entries(metadata)) {
            html += `<strong>${key}:</strong> ${value}<br>`;
        }
        box.innerHTML = html;
    } else {
        box.innerHTML = `<strong>${layerName}</strong><br>No metadata available.`;
    }

    // Position the tooltip
    const svgRect = svg.node().getBoundingClientRect();

    box.style.left = `${event.clientX + 10}px`;
    box.style.top = `${svgRect.top + 320}px`;
    box.style.display = 'block';

    currentlyShownLayer = layerName;
}

function renderSelectedMetadataBox() {
    const container = document.getElementById("selected-metadata-content");
    const title = document.getElementById("selected-metadata-title");

    if (!container || !title) return;

    if (selectedLayers.length === 0) {
        container.innerHTML = "<span class='has-text-grey'>Shift-click layers to view metadata.</span>";
        title.style.display = "none";
        return;
    }

    title.style.display = "block";

    let html = "<ul>";
    selectedLayers.forEach(layerName => {
        const metadata =descriptionData[layerName]?.metadata || {};
        html+=`<li><strong>${layerName}</strong><ul>`;
        for (const [key, value] of Object.entries(metadata)) {
            html += `<li>${key}: ${value}</li>`;
        }
        html += "</ul></li>";
    });
    html += "</ul>";
    container.innerHTML = html;
}


const layersData = allData["Visualization-Layer-Parameters"] || {};
const connectionData = allData["Visualization-Connections"] || [];

const xStart = 50;
const yMid = 300;
const spacing = 30;

console.log("scale");

const widthScale = 5;
const heightScale = 3;

console.log("xstart");
let x = xStart;

console.log("layer index");
let layerIndex = 0;

console.log("before layer position");
const layerPositions = {};
const layerOrder = {};

Object.entries(layersData).forEach(([layerName, values]) => {
    if (!Array.isArray(values)) return;

    const [w, h] = values;
    const rectWidth = Math.max(20, w * widthScale);
    const rectHeight = Math.max(20, h * heightScale);
    const y = yMid - rectHeight / 2;

    layerPositions[layerName] = {
        centerX: x + rectWidth / 2,
        centerY: y + rectHeight / 2,
        leftX: x,
        rightX: x + rectWidth,
        topY: y,
        bottomY: y + rectHeight,
        width: rectWidth,
        height: rectHeight
    };

    layerOrder[layerName] = layerIndex;
    layerIndex++;

    const group = svg.append("g").attr("class", "layer-group");

    const fillColor = regionHasLayer(layerName) ? "#F5FD66" : "rgb(7, 137, 48)";
    const depth = 12;

    // Front face
    const front = group.append("rect")
        .attr("x", x)
        .attr("y", y)
        .attr("width", rectWidth)
        .attr("height", rectHeight)
        .attr("fill", fillColor)
        .attr("stroke", "black")
        .attr("class", "front-face")
        .style("cursor", "pointer")
        .style("filter", "drop-shadow(2px 2px 2px rgba(0, 0, 0, 0.4))")
        .on("click", function (event) {
            if (event.shiftKey) {
                if (!selectedLayers.includes(layerName)) {
                    selectedLayers.push(layerName);
                } else {
                    selectedLayers = selectedLayers.filter(name => name !== layerName);
                }
                renderSelectedMetadataBox();
            } else {
                selectedLayers = [];
                renderSelectedMetadataBox();

                // Reset all groups
                svg.selectAll(".front-face")
                    .attr("stroke", "black")
                    .style("filter", "drop-shadow(2px 2px 2px rgba(0, 0, 0, 0.4))");

                showLayerMetadata(layerName, event, group);
            }

            event.stopPropagation();
        });

    // Top face
    group.append("polygon")
        .attr("points", `
            ${x},${y}
            ${x + depth},${y - depth}
            ${x + rectWidth + depth},${y - depth}
            ${x + rectWidth},${y}
        `)
        .attr("fill", d3.color(fillColor).darker(0.5))
        .attr("stroke", "black");

    // Side face
    group.append("polygon")
        .attr("class", "side-face")
        .attr("points", `
            ${x + rectWidth},${y}
            ${x + rectWidth + depth},${y - depth}
            ${x + rectWidth + depth},${y + rectHeight - depth}
            ${x + rectWidth},${y + rectHeight}
        `)
        .attr("fill", d3.color(fillColor).darker(1))
        .attr("stroke", "black");




    svg.append("text")
        .attr("x", x + rectWidth / 2)
        .attr("y", y + rectHeight + 15)
        .attr("text-anchor", "middle")
        .attr("font-size", "12px")
        .text(layerName);

    x += rectWidth + spacing;
});

// Add a marker for arrowheads
const defs = svg.append("defs");

defs.append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 0 10 10")
    .attr("refX", 10)
    .attr("refY", 5)
    .attr("markerWidth", 4)
    .attr("markerHeight", 4)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M 0 0 L 10 5 L 0 10 z")
    .attr("fill", "black");

// Draw connections
connectionData.forEach(([source, target]) => {
    const sourcePos = layerPositions[source];
    const targetPos = layerPositions[target];
    console.log(`Trying to draw connection: ${source} -> ${target}`);

    if (!sourcePos || !targetPos) {
        console.warn(`Skipping connection from ${source} to ${target} — missing position`);
        return;
    }

    const isRecurrent = source === target;

    if (isRecurrent) {
        console.log("recurrent")
        const box = sourcePos;
        const loopWidth = box.width * 0.5;
        const loopHeight = box.height * 1.5;

        const startX = box.rightX;
        const startY = box.centerY;
        const endX = box.leftX;
        const endY = box.centerY;

        const pathData = `
        M ${startX} ${startY}
        C ${startX + loopWidth} ${startY - loopHeight},
          ${endX - loopWidth} ${endY - loopHeight},
          ${endX} ${endY}
    `;

        svg.append("path")
            .attr("d", pathData)
            .attr("fill", "none")
            .attr("stroke", "black")
            .attr("stroke-width", 2)
            .attr("marker-end", "url(#arrow)");
    } else {
        const dx = targetPos.leftX - sourcePos.rightX;
        const dy = targetPos.centerY - sourcePos.centerY;

        const startX = sourcePos.rightX;
        const startY = sourcePos.centerY;
        const endX = targetPos.leftX;
        const endY = targetPos.centerY;

        const gap = targetPos.leftX - sourcePos.rightX;
        const tolerance = 5;
        const isAdjacent = Math.abs(gap - spacing) <= tolerance;

        let pathData;
        if (isAdjacent) {
            // Draw a straight line
            pathData = `
                M ${startX} ${startY}
                L ${endX} ${endY}
            `;
        } else {
            // Draw a curved line
            const curveHeight = Math.min(Math.abs(dx) * 0.2, 150);

            pathData = `
                M ${startX} ${startY}
                C ${startX + dx / 3} ${startY - curveHeight},
                  ${startX + 2 * dx / 3} ${endY - curveHeight},
                  ${endX} ${endY}
            `;
        }

        svg.append("path")
            .attr("d", pathData)
            .attr("fill", "none")
            .attr("stroke", "black")
            .attr("stroke-width", 2)
            .attr("marker-end", "url(#arrow)");
    }
});

window.addEventListener("click", function () {
    const box = document.getElementById("layer-info-box");
    if (box) box.style.display = "none";
    currentlyShownLayer = null;

    if (currentlyHighlightedRect) {
        currentlyHighlightedRect.select(".front-face")
            .attr("stroke", "black")
            .style("filter", "drop-shadow(2px 2px 2px rgba(0, 0, 0, 0.4))");

        currentlyHighlightedRect.select(".side-face")
            .attr("stroke", "black")
            .style("filter", null);

        currentlyHighlightedRect = null;
    }
});







