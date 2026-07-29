import client from './client'

/**
 * Health API service — wraps the backend health endpoint.
 */

export const healthService = {
  /** GET /health */
  getHealth: () => client.get('/health'),
}
