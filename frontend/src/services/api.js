/**
 * API Service for Memori
 * Handles all communications with the backend API
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Fetch memories with optional filters
 * @param {Object} filters - Filter parameters
 * @returns {Promise<Array>} - List of memories
 */
export async function fetchMemories(filters = {}) {
  try {
    // Convert filters to query string
    const queryParams = new URLSearchParams();
    
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, value);
      }
    }
    
    const url = `${API_BASE_URL}/memories${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching memories:', error);
    throw error;
  }
}

/**
 * Upload an audio file to create a new memory
 * @param {File} file - The audio file to upload
 * @param {Object} metadata - Additional metadata
 * @param {Function} onProgress - Progress callback
 * @returns {Promise<Object>} - The created memory
 */
export async function uploadAudioMemory(file, metadata = {}, onProgress = null) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    if (metadata) {
      formData.append('metadata', JSON.stringify(metadata));
    }
    
    const xhr = new XMLHttpRequest();
    
    // Set up progress monitoring if callback provided
    if (onProgress && typeof onProgress === 'function') {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const percentComplete = Math.round((event.loaded / event.total) * 100);
          onProgress(percentComplete);
        }
      });
    }
    
    return new Promise((resolve, reject) => {
      xhr.open('POST', `${API_BASE_URL}/memories/upload`);
      
      xhr.onload = function() {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
        }
      };
      
      xhr.onerror = function() {
        reject(new Error('Network error during upload'));
      };
      
      xhr.send(formData);
    });
  } catch (error) {
    console.error('Error uploading memory:', error);
    throw error;
  }
}

/**
 * Get a single memory by ID
 * @param {string} id - Memory ID
 * @returns {Promise<Object>} - Memory details
 */
export async function getMemory(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/memories/${id}`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Error fetching memory ${id}:`, error);
    throw error;
  }
}

/**
 * Get memory statistics
 * @returns {Promise<Object>} - Statistics object
 */
export async function getMemoryStats() {
  try {
    const response = await fetch(`${API_BASE_URL}/memories/stats`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching memory stats:', error);
    throw error;
  }
}

/**
 * Search memories by query
 * @param {string} query - Search query
 * @returns {Promise<Array>} - Search results
 */
export async function searchMemories(query) {
  try {
    const response = await fetch(`${API_BASE_URL}/memories/search?q=${encodeURIComponent(query)}`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error searching memories:', error);
    throw error;
  }
}

/**
 * Get available memory filters
 * @returns {Promise<Object>} - Available filters
 */
export async function getAvailableFilters() {
  try {
    const response = await fetch(`${API_BASE_URL}/memories/filters`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching available filters:', error);
    throw error;
  }
}
