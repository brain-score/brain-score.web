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
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    console.log("Request body string:", formData.toString());

    // Step 1: Request a presigned POST from the Django backend
    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: formData.toString()
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            document.getElementById('message').innerText = "Error: " + data.error;
            return;
        }
        const s3Url = data.url;     // S3 endpoint URL for presigned POST
        const fields = data.fields; // Form fields required by S3
        const objectKey = data.key;

        // Step 2: Construct a new FormData for the S3 POST upload.
        const s3FormData = new FormData();
        for (const key in fields) {
            s3FormData.append(key, fields[key]);
        }
        s3FormData.append("file", file);

        // Unhide the progress container now that upload is starting.
        document.getElementById('upload-progress').style.display = 'block';

        // Create a new XMLHttpRequest to handle the S3 upload.
        const xhr = new XMLHttpRequest();
        xhr.open('POST', s3Url);

        // Update the progress bar and progress text.
        xhr.upload.addEventListener('progress', function(event) {
            if (event.lengthComputable) {
                // Calculate percentage complete.
                const percentComplete = (event.loaded / event.total) * 100;
                document.getElementById('progress').style.width = percentComplete + '%';

                // Convert bytes to MB (1 MB = 1048576 bytes) and format the values.
                const loadedMB = (event.loaded / 1048576).toFixed(2);
                const totalMB = (event.total / 1048576).toFixed(2);

                // Update the progress text (e.g., "1.23 MB / 10.00 MB (12.3%)").
                document.getElementById('progress-text').innerText = `${loadedMB} MB / ${totalMB} MB (${percentComplete.toFixed(1)}%)`;
            }
        });

        // Monitor state changes for success or failure.
        bucket = "test-large-file-uploads-quest"
        const bucketUrl = "https://" + bucket + ".s3.us-east-2.amazonaws.com/" + objectKey;
        xhr.onreadystatechange = function() {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                if (xhr.status === 204 || xhr.status === 200) {
                    document.getElementById('message').innerHTML =
                        "Upload successful! You can access your object <a href='" + bucketUrl +
                        "' target='_blank'>here</a>.";
                } else {
                    document.getElementById('message').innerText = "Upload failed. S3 responded with status: " + xhr.status;
                }
            }
        };

        // Send the form data to S3.
        xhr.send(s3FormData);
    })
    .catch(err => {
        document.getElementById('message').innerText = "Error requesting presigned POST: " + err;
    });
});