/**
 * presigned_post.js
 *
 * Handles:
 * - Presigned POST request to Django
 * - Upload to S3 with progress
 * - Finalization call to backend
 */



export function uploadFileWithPresignedPost(file, fileName, fileType, domain, pluginType) {
    const formData = new URLSearchParams();
    formData.append('file_name', fileName);
    formData.append('file_type', fileType);
    formData.append('bucket_choice', pluginType);
    formData.append('domain', domain);
    formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
    formData.append('file_size_bytes', file.size);

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

        const s3Url = data.url;
        const fields = data.fields;
        const objectKey = data.key;

        const s3FormData = new FormData();
        for (const key in fields) s3FormData.append(key, fields[key]);
        s3FormData.append("file", file);

        document.getElementById('upload-progress').style.display = 'block';

        const xhr = new XMLHttpRequest();
        xhr.open('POST', s3Url);

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

        xhr.onreadystatechange = () => {
            if (xhr.readyState !== XMLHttpRequest.DONE) return;

            if (xhr.status === 204 || xhr.status === 200) {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
                fetch('/profile/large_file_upload/finalize/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({
                        object_key: objectKey,
                        plugin_type: pluginType,
                        file_size_bytes: file.size,
                        domain: domain,
                        csrfmiddlewaretoken: csrfToken
                    }).toString()
                })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('message').innerText = data.error;
                    } else {
                        document.getElementById('message').innerHTML =
                            `Upload complete! <a href="${data.public_url}" target="_blank">Download</a>`;
                        document.getElementById('upload-form').reset();
                        document.getElementById('upload-progress').style.display = 'none';
                    }
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
}