$(document).ready(function () {
    const tabs = document.getElementsByClassName("tab leaderboard-track");
    Array.from(tabs).forEach((tab) => {
        tab.addEventListener('click', function () {
            const target_identifier = tab.getAttribute('data-target');
            const depth_0_cells = document.getElementsByClassName("depth_0");
            Array.from(depth_0_cells).forEach((cell) => {
                if (target_identifier.endsWith("average")) {
                    // when we select the average track, show depth_0 (i.e. average) th and td cells
                    cell.style.display = "";
                } else {
                    // when we select other tracks (V1/behavior), hide the depth_0 cells
                    cell.style.display = "none";
                }
            })
        });
    });
});
