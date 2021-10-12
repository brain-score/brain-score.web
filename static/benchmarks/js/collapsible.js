$(document).ready(function () {
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
                Array.from(targets).forEach((target) => {
                    switch_state(target, control);
                })
            }
        };

        if (control.getAttribute("data-initial") === "hidden") {
            // hide by default -- do this here so that non-javascript users still see content
            control.click();
        }
    });
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
