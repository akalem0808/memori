// Centralized HTTP client for API calls
export async function apiFetch(url, options = {}) {
  try {
    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
    return await response.json();
  } catch (error) {
    // Error handling
    throw error;
  }
}
