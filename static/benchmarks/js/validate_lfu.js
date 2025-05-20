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
    '.pkl', '.weights', '.npy', '.npz', '.safetensors', '.zip', '.csv'
];

export const allowedMimeTypes = [
    'application/octet-stream', 'application/zip', 'application/x-hdf5',
    'application/x-tar', 'application/x-pickle', 'application/x-npy',
    'text/csv', 'application/json'
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

