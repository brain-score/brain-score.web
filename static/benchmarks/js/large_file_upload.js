/**
 * large_file_upload.js
 *
 * Handles form submission:
 *  - Validates file extension, MIME type, and magic number
 *  - Calls presigned_post.js to upload if validation passes
 */

import {
    hasAllowedExtension,
    hasAllowedMimeType,
    checkMagicNumber,
    magicNumbers,
    allowedExtensions,
    allowedMimeTypes
} from './validate_lfu.js';

import { uploadFileWithPresignedPost } from './presigned_post.js';

document.getElementById('upload-form').addEventListener('submit', function(event) {
    event.preventDefault();

    const fileInput = document.getElementById('fileInput');
    if (!fileInput.files.length) {
        alert("Please select a file to upload.");
        return;
    }

    const file = fileInput.files[0];
    const fileName = file.name;
    const fileType = file.type || "application/octet-stream";
    const pluginType = document.getElementById('bucketChoice').value;
    const domain = document.getElementById('bucketChoiceDomain').value;

    console.log("File selected:", fileName, "| Type:", fileType);

    // Extension check
    const extFromName = fileName.slice(fileName.lastIndexOf('.')).toLowerCase();
    if (!hasAllowedExtension(fileName)) {
        alert(`File extension "${extFromName}" is not allowed.\nAllowed: ${allowedExtensions.join(', ')}`);
        return;
    }

    // MIME type check
    if (!hasAllowedMimeType(fileType)) {
        alert(`MIME type "${fileType}" is not allowed.\nAllowed: ${allowedMimeTypes.join(', ')}`);
        return;
    }

    // Magic number check
    const ext = Object.keys(magicNumbers).find(e => fileName.toLowerCase().endsWith(e));
    const expectedHex = ext ? magicNumbers[ext] : '';

    checkMagicNumber(file, expectedHex, (isValid) => {
        if (!isValid) {
            alert(`Invalid file signature for ${ext}.`);
            return;
        }

        // Passed all checks, proceed to upload
        uploadFileWithPresignedPost(file, fileName, fileType, domain, pluginType);
    });
});