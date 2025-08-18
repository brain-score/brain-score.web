$(document).ready(function () {
    let isInitialSetup = true;
    
    const collapsible_controls = document.getElementsByClassName("collapsible_control");
    Array.from(collapsible_controls).forEach((control) => {
        control.onclick = function () {
            // either the control directly specifies a target (e.g. for benchmark bibtex)
            const target_identifier = control.getAttribute('data-target');
            if (target_identifier != null) {
                const target = document.getElementById(target_identifier);
                switch_state(target, control);
            }
            // or the control has an identifier that children point to with data-parent (e.g. child benchmark scores)
            else {
                const identifier = control.getAttribute('data-identifier');
                const targets = document.querySelectorAll(`[data-parent=${CSS.escape(identifier)}]`);
                
                // Check if we're about to hide children (for recursive collapsing)
                let isCollapsing = false;
                if (targets.length > 0) {
                    isCollapsing = targets[0].style.display !== "none";
                }
                
                Array.from(targets).forEach((target) => {
                    switch_state(target, control);
                });
                
                // Only apply recursive hiding after initial setup and for user interactions
                if (isCollapsing && !isInitialSetup) {
                    recursivelyHideDescendants(identifier);
                }
            }
        };

        if (control.getAttribute("data-initial") === "hidden") {
            // hide by default -- do this here so that non-javascript users still see content
            control.click();
        }
    });
    
    // After initial setup is complete, enable recursive behavior for user interactions
    setTimeout(() => {
        isInitialSetup = false;
    }, 100);
});

function switch_state(target, control) {
    const is_hidden = target.style.display === "none";
    if (is_hidden) {
        target.style.display = ""; // unhide
        control.className = control.className.replace(
            "is_expandable", "is_collapsible"); // switch symbol
    } else {
        target.style.display = "none"; // hide
        control.className = control.className.replace(
            "is_collapsible", "is_expandable"); // switch symbol
    }
}

function recursivelyHideDescendants(parentId) {
    // Find all divs that are children of this parent
    const childDivs = document.querySelectorAll(`div[data-parent="${CSS.escape(parentId)}"]`);
    
    childDivs.forEach((childDiv) => {
        // Look for collapsible controls within this child
        const childControl = childDiv.querySelector('.collapsible_control[data-identifier]');
        
        if (childControl) {
            const childId = childControl.getAttribute('data-identifier');
            
            // Force hide all grandchildren
            const grandChildren = document.querySelectorAll(`[data-parent="${CSS.escape(childId)}"]`);
            grandChildren.forEach((grandChild) => {
                grandChild.style.display = "none";
            });
            
            // Set the child control to collapsed state
            if (childControl.className.includes("is_collapsible")) {
                childControl.className = childControl.className.replace("is_collapsible", "is_expandable");
            }
            
            // Recursively handle this child's descendants
            recursivelyHideDescendants(childId);
        }
    });
}
