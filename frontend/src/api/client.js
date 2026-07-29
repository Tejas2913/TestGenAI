import axios from 'axios'

/**
 * Axios client — shared instance for all API calls.
 * Configures base URL, content type, and error normalization.
 *
 * Phase 5: adds request interceptor that injects the JWT Bearer token
 * from localStorage when present. The V2 client (clientV2) is
 * constructed from the same interceptor chain with a separate baseURL.
 */

/** Normalize an Axios error into a plain object with stable shape. */
function normalizeError(error) {
  if (axios.isCancel(error)) {
    return {
      message: 'Request was cancelled',
      code: 'REQUEST_CANCELLED',
      status: 0,
      cancelled: true,
    }
  }

  const normalized = {
    message: 'An unexpected error occurred',
    code: 'UNKNOWN_ERROR',
    status: 0,
    cancelled: false,
  }

  if (error.code === 'ECONNABORTED') {
    normalized.message = 'Request timed out. The server may be processing a large request.'
    normalized.code = 'TIMEOUT'
  } else if (error.response) {
    const data = error.response.data
    normalized.status = error.response.status
    normalized.message = data?.detail || data?.message || error.message
    normalized.code = data?.error_code || `HTTP_${error.response.status}`

    // Friendlier messages for known HTTP codes
    if (error.response.status === 401) {
      normalized.message = 'Authentication required. Please log in.'
      normalized.code = 'UNAUTHORIZED'
    } else if (error.response.status === 403) {
      normalized.message = 'Access denied.'
      normalized.code = 'FORBIDDEN'
    } else if (error.response.status === 422) {
      normalized.message = data?.detail?.[0]?.msg
        || data?.detail
        || 'Invalid input. Please check your code and try again.'
      normalized.code = 'VALIDATION_ERROR'
    } else if (error.response.status === 502) {
      normalized.message = 'The AI model is temporarily unavailable. Please try again.'
      normalized.code = 'LLM_UNAVAILABLE'
    } else if (error.response.status === 503) {
      normalized.message = 'Service is temporarily unavailable. Please try again later.'
      normalized.code = 'SERVICE_UNAVAILABLE'
    }
  } else if (error.request) {
    normalized.message = 'Cannot reach server. Check your connection.'
    normalized.code = 'NETWORK_ERROR'
  } else {
    normalized.message = error.message
  }

  return normalized
}

/** Attach JWT Bearer token to every outgoing request if available. */
function attachAuthInterceptor(instance) {
  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem('testgen_jwt')
    if (token) {
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  })
}

/** Attach response normalizer (unwrap data, normalize errors). */
function attachResponseInterceptor(instance) {
  instance.interceptors.response.use(
    (response) => response.data,
    (error) => Promise.reject(normalizeError(error))
  )
}

// ─── V1 client (existing V1 endpoints) ───────────────────────────────────────
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 90_000, // 90s — accounts for LLM generation time
})

attachAuthInterceptor(client)
attachResponseInterceptor(client)

// ─── V2 client (async jobs, auth) ─────────────────────────────────────────────
export const clientV2 = axios.create({
  baseURL: import.meta.env.VITE_API_V2_BASE_URL || 'http://localhost:8000/api/v2',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000, // 30s — job submit + status polling; not waiting for LLM
})

attachAuthInterceptor(clientV2)
attachResponseInterceptor(clientV2)

export default client
