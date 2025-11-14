/**
 * validate_lfu.js
 *
 * This module handles client-side validation for large file uploads.
 * It includes:
 *  - Allowed file extensions and MIME types
 *  - Magic number (file signature) definitions
 *  - Utility functions for validating extensions, MIME types, and file content
 *
 * Used by: large_file_upload.js
 */


export const allowedExtensions = [
    '.pt', '.pth', '.ckpt', '.bin', '.onnx', '.h5', '.hdf5', '.pb', '.tflite',
    '.pkl', '.weights', '.npy', '.npz', '.safetensors', '.zip', '.csv', '.nc',
    '.jpg', '.jpeg', '.png'
];

export const allowedMimeTypes = [
    'application/octet-stream', 'application/zip', 'application/x-hdf5',
    'application/x-tar', 'application/x-pickle', 'application/x-npy',
    'text/csv', 'application/json', 'application/x-netcdf', 'application/x-zip-compressed',
    'image/jpeg', 'image/png'
];

export const magicNumbers = {
    '.zip':        '504b0304',
    '.npz':        '504b0304',
    '.npy':        '934e554e01',
    '.h5':         '894844460d0a1a0a',
    '.hdf5':       '894844460d0a1a0a',
    '.onnx':       '080310',
    '.pb':         '080212',
    '.pkl':        '80',
    '.tflite':     '544d4642',
    '.safetensors':'7b22686561646572223a',
    '.nc':         '',
    '.jpg':        'ffd8ff',
    '.jpeg':       'ffd8ff',
    '.png':        '89504e47',
    '.csv':        '',
    '.pt':         '',
    '.pth':        '',
    '.ckpt':       '',
    '.bin':        '',
    '.weights':    '',
};

export function hasAllowedExtension(fileName) {
    return allowedExtensions.some(ext => fileName.toLowerCase().endsWith(ext));
}

export function hasAllowedMimeType(fileType) {
    return allowedMimeTypes.includes(fileType);
}

export function getMagicHex(byteArray) {
    return Array.from(byteArray).map(b => b.toString(16).padStart(2, '0')).join('');
}

export function checkMagicNumber(file, expectedHex, callback) {
    if (!expectedHex) {
        callback(true);
        return;
    }
    const reader = new FileReader();
    reader.onload = function (e) {
        const bytes = new Uint8Array(e.target.result);
        const fileHex = getMagicHex(bytes);
        callback(fileHex.startsWith(expectedHex));
    };
    const length = Math.ceil(expectedHex.length / 2);
    const blob = file.slice(0, length);
    reader.readAsArrayBuffer(blob);
}

// ZIP file parsing for adherence:
export async function validateZipContents(file) {
    if (!file.name.toLowerCase().endsWith('.zip')) return true; // skip if not zip

    const zip = await JSZip.loadAsync(file);
    const entries = Object.values(zip.files);

    for (const entry of entries) {
        if (entry.dir) continue; // skip folders

        const name = entry.name;
        const ext = Object.keys(magicNumbers).find(e => name.toLowerCase().endsWith(e));
        const expectedHex = ext ? magicNumbers[ext] : '';
        const mimeGuess = mimeFromExtension(ext); // helper we’ll define next

        // Check extension
        if (!hasAllowedExtension(name)) {
            throw new Error(`File "${name}" in ZIP has disallowed extension.\n\n Allowed: ${allowedExtensions.join(', ')}`);
        }

        // Check guessed MIME
        if (!hasAllowedMimeType(mimeGuess)) {
            throw new Error(`File "${name}" in ZIP has disallowed MIME type "${mimeGuess}".`);
        }

        // Check magic number (only if expectedHex is defined)
        if (expectedHex) {
            const content = await entry.async('uint8array');
            const actualHex = getMagicHex(content.slice(0, Math.ceil(expectedHex.length / 2)));
            if (!actualHex.startsWith(expectedHex)) {
                throw new Error(`File "${name}" in ZIP has invalid magic number.`);
            }
        }
    }

    return true;
}

// Simple helper based on extension
function mimeFromExtension(ext) {
    const mapping = {
        '.csv': 'text/csv',
        '.zip': 'application/zip',
        '.npy': 'application/x-npy',
        '.npz': 'application/zip',
        '.pkl': 'application/x-pickle',
        '.h5': 'application/x-hdf5',
        '.hdf5': 'application/x-hdf5',
        '.json': 'application/json',
        '.nc': 'application/x-netcdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.onnx': 'application/octet-stream',
        '.pt': 'application/octet-stream',
        '.pth': 'application/octet-stream',
        '.pb': 'application/octet-stream',
        '.weights': 'application/octet-stream',
        '.tflite': 'application/octet-stream',
        '.bin': 'application/octet-stream',
        '.safetensors': 'application/octet-stream',
    };
    return mapping[ext] || 'application/octet-stream';
}