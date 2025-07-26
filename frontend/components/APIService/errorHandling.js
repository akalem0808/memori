// Error handling utilities for API requests
export function handleApiError(error) {
  // Log and format error
  console.error('API Error:', error);
  return { message: error.message || 'Unknown error', error };
}
