$(document).ready(function () {
    const collapsible_controls = document.getElementsByClassName("bibtex_collapsible_control");
    Array.from(collapsible_controls).forEach((control) => {
        control.onclick = function () {
            const target_identifier = control.getAttribute('data-target');
            const target = document.getElementById(target_identifier);
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
        };

        // hide by default -- do this here so that non-javascript users still see content
        control.click();
    });
});
