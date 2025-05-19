// draw_layers.js
// Author: Aneesa Beckford
// Description:
// Renders interactive 3D-like dummy layer blocks and connections in an SVG with zoom and pan support.
// Users can click or shift-click on  layers to view metadata and highlight different components

// Keeps track of which rectangle is currently highlighted
let currentlyHighlightedRect = null;

// Create the main SVG container and a zoomable group inside it
const svg = d3.select("svg");
const zoomGroup = svg.append("g").attr("class", "zoom-group")

// Set up zoom & pan behavior
const zoom = d3.zoom()
    .scaleExtent([0.5, 5])
    .on("zoom", (event) => {
        zoomGroup.attr("transform", event.transform)
    });

svg.call(zoom)

let selectedLayers = [];
let currentlyShownLayer = null;

// Load & parse the JSON data injected into the DOM
const raw = document.getElementById("layers-json");
if (!raw) {
    console.error("layers-json not found!");
}

const allData = JSON.parse(document.getElementById('layers-json').textContent);

// Extract different sections from the parsed JSON
const regionData = allData["Region"] || {};
const descriptionData = allData["Visualization-Description"] || {};

// Returns true if the given layer name exists in regionData
function regionHasLayer(layerName) {
    return Object.values(regionData).includes(layerName);
}

/**
 * Displays a floating box with metadata for the clicked layer.
 * Highlights the selected rectangle and positions the tooltip
 * @param layerName
 * @param event
 * @param groupElement
 */
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

/**
 * Renders the list of metadata for all shift-clicked (selected) layers
 * in the side panel under "Selected Layers"
 */
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

// Layout constants
const xStart = 50;
const yMid = 300;
const spacing = 30;

//Scaling factors for converting width/height to screen pixels
const widthScale = 5;
const heightScale = 3;

let x = xStart;

let layerIndex = 0;

const layerPositions = {};
const layerOrder = {};

// Render each layer as a 3D-styled rectangle with depth (front, top, side)
Object.entries(layersData).forEach(([layerName, values]) => {
    if (!Array.isArray(values)) return;

    const [w, h] = values;
    const rectWidth = Math.max(20, w * widthScale);
    const rectHeight = Math.max(20, h * heightScale);
    const y = yMid - rectHeight / 2;

    // Track layer position and dimensions for drawing arrows later
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

    // Create a group to hold all parts of the layer block
    const group = zoomGroup.append("g").attr("class", "layer-group");

    const fillColor = regionHasLayer(layerName) ? "#F5FD66" : "rgb(7, 137, 48)";
    const depth = 12;

    // Add the front face of the rectangle
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
            // Shift-click toggles selection for multi-layer metadata view
            // Regular click selects only this layer and shows tooltip
            if (event.shiftKey) {
                // Prevent zoom behavior when shift-clicking on layer
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
            if (event.shiftKey){
                event.preventDefault();
                event.stopImmediatePropagation();
            } else {
                event.stopPropagation();
            }
        });

    // Add top face of the rectangle
    group.append("polygon")
        .attr("points", `
            ${x},${y}
            ${x + depth},${y - depth}
            ${x + rectWidth + depth},${y - depth}
            ${x + rectWidth},${y}
        `)
        .attr("fill", d3.color(fillColor).darker(0.5))
        .attr("stroke", "black");

    // Add side face of the rectangle
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


    // Add a text label centered below each layer rectangle
    zoomGroup.append("text")
        .attr("x", x + rectWidth / 2)
        .attr("y", y + rectHeight + 15)
        .attr("text-anchor", "middle")
        .attr("font-size", "12px")
        .text(layerName);

    x += rectWidth + spacing;
});

// Add a marker for arrowheads
const defs = zoomGroup.append("defs");

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

// Draw arrows representing connections between layers by iterating through all defined connections
connectionData.forEach(([source, target]) => {
    const sourcePos = layerPositions[source];
    const targetPos = layerPositions[target];

    if (!sourcePos || !targetPos) {
        console.warn(`Skipping connection from ${source} to ${target} — missing position`);
        return;
    }

    // Draw a curved self-loop for recurrent layers
    const isRecurrent = source === target;
    if (isRecurrent) {
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

        zoomGroup.append("path")
            .attr("d", pathData)
            .attr("fill", "none")
            .attr("stroke", "black")
            .attr("stroke-width", 2)
            .attr("marker-end", "url(#arrow)");

    } else {
        // Draw a straight or curved connection between different layers

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

        zoomGroup.append("path")
            .attr("d", pathData)
            .attr("fill", "none")
            .attr("stroke", "black")
            .attr("stroke-width", 2)
            .attr("marker-end", "url(#arrow)");
    }
});

// When clicking anywhere outside a layer, hide a tooltip and reset highlights
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







