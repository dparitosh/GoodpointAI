const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * Fetches a resource with a retry mechanism using exponential backoff.
 * This is useful for handling transient network errors or temporary server issues.
 * @param {string} url The URL to fetch for E2ETrace.
 * @param {object} options Fetch options.
 * @param {number} retries Number of retries.
 * @returns {Promise<Response>} A promise that resolves with the fetch Response.
 */
export async function e2etraceFetchWithRetry(url, options, retries = 3) {
    const fullUrl = `${API_BASE_URL}${url}`;

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch(fullUrl, options);
            if (response.ok) {
                return response;
            }

            // Don't retry on 4xx client errors, as they are likely not transient.
            if (response.status >= 400 && response.status < 500) {
                const errorData = await response.json().catch(() => ({ message: `HTTP error! status: ${response.status}` }));
                throw new Error(errorData.message || `Client Error: ${response.status}`);
            }

            // For 5xx server errors, we'll throw, which triggers a retry.
            throw new Error(`Server Error: ${response.status}`);
        } catch (error) {
            if (attempt >= retries) {
                console.error(`All ${retries} fetch attempts failed for ${fullUrl}.`);
                throw error; // Re-throw the last error after all retries fail.
            }
            // Exponential backoff: 1s, 2s, 4s...
            const delay = Math.pow(2, attempt - 1) * 1000;
            console.warn(`Attempt ${attempt} failed for ${fullUrl}. Retrying in ${delay}ms...`);
            await new Promise(res => setTimeout(res, delay));
        }
    }
}