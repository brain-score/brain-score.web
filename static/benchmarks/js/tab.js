$(document).ready(function () {
    hide_all_tabs(); // initially hide all tabs (active one will be displayed again)

    const tabs = document.getElementsByClassName("tab");
    Array.from(tabs).forEach((tab) => {
        tab.onclick = function () {
            // set other tabs to inactive
            Array.from(tabs).forEach((tab) => {
                tab.className = tab.className.replace("is-active", ""); // set not active
            });
            // set tab to active
            tab.className = tab.className + " is-active";
            // hide other tab contents
            hide_all_tabs();
            // set target visible
            show_tab_content(tab);
        };

        if (tab.className.includes("is-active")) {
            show_tab_content(tab); // show active tab
        }
    });
});

function show_tab_content(tab) {
    const target_identifier = tab.getAttribute('data-target');
    const target = document.getElementById(target_identifier);
    target.style.display = ""; // unhide
}

function hide_all_tabs() {
    const tab_contents = document.getElementsByClassName('tab-content')
    Array.from(tab_contents).forEach((tab_content) => {
        tab_content.style.display = "none"; // hide
    });
}
