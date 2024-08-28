 document.getElementById('download-csv').addEventListener('click', function () {
            // Get the CSV data from the hidden textarea
            const csvData = document.getElementById('csv-data').value;

            // Create a blob with the CSV data
            const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });

            // Create a link element
            const link = document.createElement('a');

            if (navigator.msSaveBlob) { // For IE 10+
                navigator.msSaveBlob(blob, 'benchmark_scores.csv');
            } else {
                // Create a URL for the blob and set it as the href attribute
                const url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', 'benchmark_scores.csv');
                link.style.visibility = 'hidden';

                // Append the link to the document and trigger the download
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
        });