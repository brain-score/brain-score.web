$(document).ready(() => {
  const leaderboardTableComponent = document.querySelector('.leaderboard-table-component');
  const leaderboardTotals = document.querySelector('.leaderboard-totals');
  const graphContainer = document.querySelector('.leaderboard-graph-container');

  // https://www.chartjs.org/docs/latest/
  new Chart(
    document.getElementById('scores_time_graph'),
    {
      type: 'line',
      data: {
        datasets: [{
          label: 'Top Score',
          data: score_accuracy_chart.map(row => ({
            x: row.day,
            y: row.score,
            label: [row.model.name, row.score]
          }))
        }]
      },
      options: {
        normalized: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              label: (context) => context.raw.label
            }
          }
        }
      }
    }
  );

  // let the page render before setting the dimensions
  setTimeout(setGraphContainerDimensions, 1);

  window.addEventListener("resize", setGraphWidth);

  function setGraphContainerDimensions() {
    setGraphWidth();
    setGraphHeight();
  };

  function setGraphWidth() {
    graphContainer.style.width = (leaderboardTableComponent.offsetWidth - leaderboardTotals.offsetWidth) + 'px';      
  };

  function setGraphHeight() {
    // the height of both totals cards plus 24px padding;
    const rowHeight = (document.querySelector('.leaderboard-totals-card').offsetHeight * 2) + 24;
    graphContainer.style.height = rowHeight + 'px';
  }
});
