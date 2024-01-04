$(document).ready(() => {
  // set a max-width on the table to allow the 'overflow-x: scroll' styling to work correctly
  setTableWidth();

  window.addEventListener("resize", setTableWidth);

  const select = $('.benchmark-sort');
  // https://select2.org/
  select.select2();
  // https://select2.org/programmatic-control/events
  select.on('select2:select', sortTable);

  function setTableWidth() {
    const padding = 15;
    const newTableContainerWidth = $('.leaderboard-table-component').width() - padding + 'px';
    $('.leaderboard-table-container').css({ maxWidth: newTableContainerWidth });
  }

  // sort rows based on the selected benchmark then re-render
  function sortTable(e) {
    if (!e.params) return;

    const selectedBenchmark = e.params.data.id;

    const sortByColumnIndex = getColumnIndex(selectedBenchmark);
    const sortedTableRows = $('tbody tr').sort((a, b) => {
      sortByA = parseFloat(a.children[sortByColumnIndex].innerText)
      sortByB = parseFloat(b.children[sortByColumnIndex].innerText)

      return sortByB - sortByA;
    });

    return $('table tbody').html(sortedTableRows);

    function getColumnIndex(selectedBenchmark) {
      const rankColumnIndex = 2;
      if (selectedBenchmark === 'average') { return rankColumnIndex; }

      // for some reason I couldn't get this to work with jQuery so vanilla js it is
      const columnHeaders = document.querySelectorAll('thead th');
      const benchmarkColumn = document.querySelector(`th[data-benchmark='${selectedBenchmark}']`);
      const columnIndex = Array.prototype.slice.call(columnHeaders).indexOf(benchmarkColumn);

      return columnIndex;
    }
  }
});
