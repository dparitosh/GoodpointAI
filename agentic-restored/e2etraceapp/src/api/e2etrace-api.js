import { API_CONFIG, getFullUrl } from '../config/api-config.js';

/**
 * Fetches a resource with a retry mechanism using exponential backoff.
 * This is useful for handling transient network errors or temporary server issues.
 * @param {string} url The URL to fetch for E2ETrace.
 * @param {object} options Fetch options.
 * @param {number} retries Number of retries (defaults to config value).
 * @returns {Promise<Response>} A promise that resolves with the fetch Response.
 */
export async function e2etraceFetchWithRetry(url, options, retries = API_CONFIG.API_RETRY_ATTEMPTS) {
    const fullUrl = getFullUrl(url);

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            const response = await fetch(fullUrl, options);
            if (response.ok) {
                return response;
            }

            // Don't retry on 4xx client errors, as they are likely not transient.
            if (response.status >= 400 && response.status < 500) {
                const errorData = await response
                    .json()
                    .catch(() => ({ message: `HTTP error! status: ${response.status}` }));

                // Normalize FastAPI-style {detail: ...} payloads into a readable string.
                let message = `Client Error: ${response.status}`;
                if (errorData && typeof errorData === 'object') {
                    if (typeof errorData.message === 'string' && errorData.message.trim()) {
                        message = errorData.message;
                    } else if (typeof errorData.detail === 'string' && errorData.detail.trim()) {
                        message = errorData.detail;
                    } else if (errorData.detail && typeof errorData.detail === 'object') {
                        if (typeof errorData.detail.message === 'string' && errorData.detail.message.trim()) {
                            message = errorData.detail.message;
                        } else {
                            try {
                                message = JSON.stringify(errorData.detail);
                            } catch {
                                message = String(errorData.detail);
                            }
                        }
                    } else {
                        try {
                            message = JSON.stringify(errorData);
                        } catch {
                            message = String(errorData);
                        }
                    }
                }

                const clientError = new Error(message);
                clientError.isClientError = true; // Mark as non-retryable
                clientError.status = response.status;
                clientError.data = errorData;
                throw clientError;
            }

            // For 5xx server errors, we'll throw, which triggers a retry.
            throw new Error(`Server Error: ${response.status}`);
        } catch (error) {
            // Don't retry client errors (4xx)
            if (error.isClientError) {
                throw error;
            }
            if (attempt >= retries) {
                console.error(`All ${retries} fetch attempts failed for ${fullUrl}.`);
                throw error; // Re-throw the last error after all retries fail.
            }
            // Exponential backoff using config delay: 1s, 2s, 4s...
            const delay = Math.pow(2, attempt - 1) * API_CONFIG.API_RETRY_DELAY;
            console.warn(`Attempt ${attempt} failed for ${fullUrl}. Retrying in ${delay}ms...`);
            await new Promise(res => setTimeout(res, delay));
        }
    }
}