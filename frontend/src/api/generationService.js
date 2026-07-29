import client from './client'

/**
 * Generation API service — wraps all generation endpoints.
 *
 * All methods return normalized data (via Axios response interceptor)
 * and throw normalized errors.
 */

export const generationService = {
  /**
   * POST /generate
   *
   * @param {Object}  data              Request payload
   * @param {string}  data.source_code  Python source code
   * @param {string}  [data.specification]  Natural language specification
   * @param {string}  [data.language]   Source language (default: python)
   * @param {string}  [data.framework]  Test framework (default: pytest)
   * @param {Object}  [options]         Axios request config overrides
   * @param {AbortSignal} [options.signal]  AbortController signal for cancellation
   * @returns {Promise<Object>} GenerationResponse from backend
   */
  createGeneration: (data, options = {}) =>
    client.post('/generate', data, options),

  /**
   * GET /generations/:id
   *
   * @param {string} id   Generation UUID
   * @returns {Promise<Object>} GenerationResponse
   */
  getGeneration: (id) =>
    client.get(`/generations/${id}`),

  /**
   * GET /generations?page=N&size=N
   *
   * @param {Object}  params
   * @param {number}  [params.page=1]
   * @param {number}  [params.size=20]
   * @returns {Promise<Object>} Paginated list of GenerationResponse
   */
  getGenerations: ({ page = 1, size = 20 } = {}) =>
    client.get('/generations', { params: { page, size } }),
}
