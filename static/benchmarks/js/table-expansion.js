$(document).ready(function () {
    // This script functions by finding all the elements whose parents the benchmark that is clicked and setting them to
    // visible or invisible. (And doing it recursively for all of its children)
    var coll = document.getElementsByClassName("clicker");
    var i;

    for (i = 0; i < coll.length; i++) {
        // This allows the current value of i to be saved to the assigned function.
        assignFunction(coll, i)
    }

    function recursiveChildren(all_coll) {
        // Performs recursiveChildren on the current benchmark and checking for all of its children and
        // then setting each child's benchmark to be the current benchmark. (Making them invisible in the meantime).
        var used_set = new Set();
        for (var i = 0; i < all_coll.length; i++) {
            const benchmark = all_coll[i].dataset.benchmark;
            if (!used_set.has(benchmark)) {
                used_set.add(all_coll[i].dataset.benchmark)
                changeChildSymbol(benchmark)
                child_coll = document.querySelectorAll(`[data-parent=${CSS.escape(benchmark)}]`);
                for (j = 0; j < child_coll.length; j++) {
                    if (child_coll[j].style.display === "") {
                        child_coll[j].style.display = "none";
                    }
                }
                recursiveChildren(child_coll)
            }
        }
    }

    function assignFunction(coll, i) {
        // Simple hide/show function onClick(). Determines what to show by finding all elements with their
        // data-parent value == the current benchmark.

        coll[i].onclick = function () {
            var j;
            let benchmark = coll[i].dataset.benchmark;
            var all_coll = document.querySelectorAll(`[data-parent=${CSS.escape(benchmark + '_v0')}]`);
            changeParentSymbol(benchmark)
            recursiveChildren(all_coll);
            for (j = 0; j < all_coll.length; j++) {
                if (all_coll[j].style.display === "none") {
                    all_coll[j].style.display = "";
                } else {
                    all_coll[j].style.display = "none";
                }
            }
            var table = document.getElementById("leaderboard");
            table.style.margin = "auto";
        };
    }

    function changeParentSymbol(parentName) {
        // Changes the plus to a minus and a minus to a plus upon clicking the column
        var allParentsExpand = document.getElementsByClassName("headerExpand");
        var allParentContract = document.getElementsByClassName("headerContract");

        for (var i = 0; i < allParentsExpand.length; i++) {
            if (allParentsExpand[i].dataset.benchmark == parentName) {
                allParentsExpand[i].className = "headerContract clicker";
                return null
            }
        }
        for (var i = 0; i < allParentContract.length; i++) {
            if (allParentContract[i].dataset.benchmark == parentName) {
                allParentContract[i].className = "headerExpand clicker";
                return null
            }
        }
    }

    function changeChildSymbol(childName) {
        // Only changes the minus to a plus for the children (since the children shouldn't automatically expand.)
        var allParentContract = document.getElementsByClassName("headerContract");
        for (var i = 0; i < allParentContract.length; i++) {
            if (allParentContract[i].dataset.benchmark == childName) {
                allParentContract[i].className = "headerExpand clicker";
                return null
            }
        }
    }
});
