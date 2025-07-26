import React, { useState, useRef } from 'react';
import { uploadAudioMemory } from '../services/api';

function UploadPanel({ onUploadComplete }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setError(null);
    setSuccess(false);
    
    if (!file) {
      setSelectedFile(null);
      return;
    }
    
    // Validate file type
    if (!file.type.startsWith('audio/')) {
      setError('Please select an audio file');
      setSelectedFile(null);
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }
    
    // Validate file size (limit to 50MB)
    if (file.size > 50 * 1024 * 1024) {
      setError('File size must be less than 50MB');
      setSelectedFile(null);
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }
    
    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file first');
      return;
    }
    
    try {
      setUploading(true);
      setError(null);
      setProgress(0);
      
      // Add optional metadata (can be expanded)
      const metadata = {
        uploadedAt: new Date().toISOString(),
        source: 'web-upload'
      };
      
      // Upload with progress tracking
      const result = await uploadAudioMemory(
        selectedFile, 
        metadata,
        (progressPercent) => setProgress(progressPercent)
      );
      
      setSuccess(true);
      setSelectedFile(null);
      
      // Reset the file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
      // Notify parent component
      if (onUploadComplete && typeof onUploadComplete === 'function') {
        onUploadComplete(result);
      }
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err.message || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const cancelUpload = () => {
    setSelectedFile(null);
    setError(null);
    setSuccess(false);
    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-panel p-4 bg-white rounded-lg shadow-sm mb-6">
      <h3 className="text-lg font-medium mb-4">Upload Memory</h3>
      
      <div className="flex flex-col space-y-4">
        {/* File Input */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Audio File
          </label>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            disabled={uploading}
            className="block w-full text-sm text-gray-500
                      file:mr-4 file:py-2 file:px-4
                      file:rounded-md file:border-0
                      file:text-sm file:font-semibold
                      file:bg-blue-50 file:text-blue-700
                      hover:file:bg-blue-100"
          />
          {selectedFile && (
            <p className="mt-1 text-sm text-gray-500">
              {selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(2)} MB)
            </p>
          )}
        </div>
        
        {/* Error Message */}
        {error && (
          <div className="text-red-500 text-sm bg-red-50 p-2 rounded">
            {error}
          </div>
        )}
        
        {/* Success Message */}
        {success && (
          <div className="text-green-500 text-sm bg-green-50 p-2 rounded">
            Memory uploaded successfully!
          </div>
        )}
        
        {/* Progress Bar (shown when uploading) */}
        {uploading && (
          <div className="w-full bg-gray-200 rounded-full h-2.5">
            <div 
              className="bg-blue-600 h-2.5 rounded-full" 
              style={{ width: `${progress}%` }}
            ></div>
            <p className="text-xs text-gray-500 mt-1">Uploading: {progress}%</p>
          </div>
        )}
        
        {/* Action Buttons */}
        <div className="flex space-x-3">
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className={`px-4 py-2 rounded-md text-white font-medium ${
              !selectedFile || uploading
                ? 'bg-gray-300 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {uploading ? 'Uploading...' : 'Upload Memory'}
          </button>
          
          {selectedFile && !uploading && (
            <button
              onClick={cancelUpload}
              className="px-4 py-2 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default UploadPanel;
