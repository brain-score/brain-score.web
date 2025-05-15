// Handle the presigned POST workflow with progress updates
document.getElementById('upload-form').addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent standard form submission

    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) {
        alert("Please select a file to upload.");
        return;
    }

    const file = fileInput.files[0];
    const fileName = file.name;
    const fileType = file.type || "application/octet-stream";

    // Build form data to request a presigned POST from Django.
    const formData = new URLSearchParams();
    formData.append('file_name', fileName);
    formData.append('file_type', fileType);
    formData.append('bucket_choice', document.getElementById('bucketChoice').value);
    formData.append('domain', document.getElementById('bucketChoiceDomain').value);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    formData.append('file_size_bytes', file.size);

    // Step 1: Request a presigned POST from the Django backend
    fetch(window.location.href, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString()
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            document.getElementById('message').innerText = "Error: " + data.error;
            return;
        }
        const s3Url    = data.url;
        const fields   = data.fields;
        const objectKey = data.key;

        // Step 2: Construct S3 FormData
        const s3FormData = new FormData();
        for (const key in fields) s3FormData.append(key, fields[key]);
        s3FormData.append("file", file);

        // Show progress UI
        document.getElementById('upload-progress').style.display = 'block';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', s3Url);

        // Progress bar
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable) {
                const percent = (event.loaded / event.total) * 100;
                document.getElementById('progress').style.width = percent + '%';

                const loadedMB = (event.loaded / 1048576).toFixed(2);
                const totalMB  = (event.total / 1048576).toFixed(2);
                document.getElementById('progress-text').innerText =
                    `${loadedMB} MB / ${totalMB} MB (${percent.toFixed(1)}%)`;
            }
        });

        // Completion
        xhr.onreadystatechange = () => {
            if (xhr.readyState !== XMLHttpRequest.DONE) return;

            if (xhr.status === 204 || xhr.status === 200) {
                // Finalize to get versionId
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                fetch('/profile/large_file_upload/finalize/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({
                        object_key:        objectKey,
                        plugin_type:       document.getElementById('bucketChoice').value,
                        file_size_bytes:   file.size,
                        domain:            document.getElementById('bucketChoiceDomain').value,
                        csrfmiddlewaretoken: csrfToken
                    }).toString()
                })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('message').innerText = data.error;
                    } else {
                        // Success message + reset form
                        document.getElementById('message').innerHTML =
                            `Upload complete! <a href="${data.public_url}" target="_blank">Download</a>`;
                        // reset the file input and selects
                        document.getElementById('upload-form').reset();
                        // hide progress bar
                        document.getElementById('upload-progress').style.display = 'none';
                    }
                })
                .catch(err => {
                    document.getElementById('message').innerText = "Error finalizing upload: " + err;
                });
            } else {
                document.getElementById('message').innerText =
                    "Upload failed. S3 responded with status: " + xhr.status;
            }
        };

        xhr.send(s3FormData);
    })
    .catch(err => {
        document.getElementById('message').innerText = "Error requesting presigned POST: " + err;
    });
});