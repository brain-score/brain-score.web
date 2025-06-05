Large File Upload System
========================

Overview
--------
This JavaScript-based system enables secure and validated large file uploads to AWS S3 via Django-backed presigned POST requests. It includes robust client-side validation of file types, MIME types, and file signatures, with support for ZIP file inspection.

Modules
-------

presigned_post.js
^^^^^^^^^^^^^^^^^
Handles the upload logic including:

- Requesting a presigned POST URL from the backend
- Uploading the file to AWS S3 with progress feedback
- Notifying the backend to finalize and store metadata

**Function**

``uploadFileWithPresignedPost(file, fileName, fileType, domain, pluginType)``

**Parameters:**

- ``file``: File object selected by the user
- ``fileName``: Name of the file
- ``fileType``: MIME type of the file
- ``domain``: Business logic parameter to route the request
- ``pluginType``: S3 bucket selector

**Features:**

- Displays a real-time progress bar during upload
- Makes a finalization call to the backend upon success
- Gracefully handles S3 and server-side errors


validate_lfu.js
^^^^^^^^^^^^^^^
Performs client-side file validation before uploading.

**Validations:**

- Allowed file extensions
- Allowed MIME types
- File signature (magic number) validation
- ZIP content inspection (internal file extension, MIME, and signature checks)

**Constants:**

- ``allowedExtensions`` – Whitelisted file extensions
- ``allowedMimeTypes`` – Supported MIME types
- ``magicNumbers`` – Dictionary mapping file extensions to expected hex signatures

**Utility Functions:**

- ``hasAllowedExtension(fileName)``
- ``hasAllowedMimeType(fileType)``
- ``checkMagicNumber(file, expectedHex, callback)``
- ``validateZipContents(file)``
- ``getMagicHex(byteArray)``
- ``mimeFromExtension(ext)`` – Maps extensions to MIME types


large_file_upload.js
^^^^^^^^^^^^^^^^^^^^
Orchestrates form submission and end-to-end upload.

**Responsibilities:**

- Attaches a submit event listener to the file upload form
- Performs layered validation (extension, MIME type, signature, ZIP contents)
- Invokes ``uploadFileWithPresignedPost`` after successful validation

**Workflow:**

1. User submits form
2. File validated for:
   - Extension
   - MIME type
   - Magic number
   - ZIP file contents (if applicable)
3. Presigned POST URL is requested
4. File is uploaded to S3
5. Finalization call is made to backend

Usage
-----
1. User selects a file and submits the form.
2. Client script:
   - Validates extension, MIME, and signature
   - Optionally checks ZIP file contents
   - Requests a presigned POST from Django backend
   - Uploads to AWS S3
   - Sends finalization request with metadata

3. Backend completes the transaction and returns a public URL.

Dependencies
------------
- `JSZip`: Required for ZIP file validation
- Django CSRF middleware (`csrfmiddlewaretoken`)
- AWS S3 Presigned POST URLs

Security Notes
--------------
- Magic number validation helps protect against spoofed file types.
- Only whitelisted file types and signatures are allowed.
- Finalization ensures only successfully uploaded files are processed.