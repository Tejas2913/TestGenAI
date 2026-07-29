import { clientV2 } from './client'

/**
 * Auth API service — wraps V2 authentication endpoints.
 *
 * Endpoints used:
 *   POST /api/v2/auth/register  → create user
 *   POST /api/v2/auth/login     → obtain JWT
 *   POST /api/v2/auth/keys      → create API key (field: label)
 *   GET  /api/v2/auth/keys      → list API keys
 *   DELETE /api/v2/auth/keys/{id} → revoke API key
 *
 * All methods return normalized data via the clientV2 response interceptor.
 */
export const authService = {
  /**
   * Register a new user account.
   *
   * @param {Object} data
   * @param {string} data.email
   * @param {string} data.password
   * @returns {Promise<Object>} UserResponse
   */
  register: (data) => clientV2.post('/auth/register', data),

  /**
   * Log in and obtain a JWT access token.
   *
   * @param {Object} data
   * @param {string} data.email
   * @param {string} data.password
   * @returns {Promise<Object>} { access_token, token_type, expires_in_seconds }
   */
  login: (data) => clientV2.post('/auth/login', data),

  /**
   * Create a new personal API key.
   *
   * @param {Object} data
   * @param {string} [data.label]  Optional human-readable label for the key
   * @returns {Promise<Object>} { id, label, raw_key, created_at }
   */
  createApiKey: (data) => clientV2.post('/auth/keys', data),

  /**
   * List all active API keys for the current user.
   *
   * @returns {Promise<Object>} { keys: [...] }
   */
  listApiKeys: () => clientV2.get('/auth/keys'),

  /**
   * Revoke an API key by ID.
   *
   * @param {string} keyId
   * @returns {Promise<Object>} { id, revoked }
   */
  revokeApiKey: (keyId) => clientV2.delete(`/auth/keys/${keyId}`),
}
