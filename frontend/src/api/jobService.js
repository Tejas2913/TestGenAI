import { clientV2 } from './client'

/**
 * Job API service — wraps V2 async job endpoints.
 *
 * Architecture:
 *   POST /api/v2/jobs/generate → submit job, get job_id (HTTP 202)
 *   GET  /api/v2/jobs/{job_id} → poll job status
 *
 * Terminal states: completed | failed | cancelled
 * Polling interval: VITE_POLL_INTERVAL_MS (default 2000ms)
 * Polling timeout:  VITE_POLL_TIMEOUT_MS  (default 300000ms = 5min)
 *
 * Do NOT use WebSockets or Server-Sent Events.
 */

/** Terminal states — polling stops when any of these are reached. */
export const TERMINAL_STATES = new Set(['completed', 'failed', 'cancelled'])

/** Default polling interval from env (architecture: 2s). */
const POLL_INTERVAL_MS = parseInt(
  import.meta.env.VITE_POLL_INTERVAL_MS || '2000',
  10
)

/** Maximum polling duration before the UI declares a timeout. */
const POLL_TIMEOUT_MS = parseInt(
  import.meta.env.VITE_POLL_TIMEOUT_MS || '300000',
  10
)

export const jobService = {
  /**
   * Submit a generation request for async processing.
   *
   * @param {Object} data
   * @param {string} data.source_code
   * @param {string|null} [data.specification]
   * @param {string} [data.language='python']
   * @param {string} [data.framework='pytest']
   * @returns {Promise<{job_id: string, status: string, message: string}>}
   */
  submitJob: (data) => clientV2.post('/jobs/generate', data),

  /**
   * Fetch the current status of a job.
   *
   * @param {string} jobId
   * @returns {Promise<JobStatusResponse>}
   *   { job_id, status, retry_count, last_checkpoint, generation_id,
   *     error_code, error_detail, created_at, updated_at, confidence }
   */
  getJobStatus: (jobId) => clientV2.get(`/jobs/${jobId}`),

  /**
   * Poll a job until it reaches a terminal state OR timeout.
   *
   * Returns the final JobStatusResponse. Throws a normalized error on
   * network failure or timeout.
   *
   * @param {string}   jobId
   * @param {Function} onUpdate   Called with JobStatusResponse on every poll.
   * @param {Object}   [options]
   * @param {number}   [options.intervalMs]  Override poll interval.
   * @param {number}   [options.timeoutMs]   Override max wait time.
   * @returns {Promise<JobStatusResponse>}
   */
  pollUntilDone: (jobId, onUpdate, { intervalMs = POLL_INTERVAL_MS, timeoutMs = POLL_TIMEOUT_MS } = {}) => {
    return new Promise((resolve, reject) => {
      const startTime = Date.now()
      let timer = null
      let cancelled = false

      async function tick() {
        if (cancelled) return

        // Timeout guard
        if (Date.now() - startTime > timeoutMs) {
          reject({
            message: `Job polling timed out after ${timeoutMs / 1000}s. The generation may still be running.`,
            code: 'POLL_TIMEOUT',
            status: 0,
            cancelled: false,
          })
          return
        }

        try {
          const status = await jobService.getJobStatus(jobId)
          if (!cancelled) {
            onUpdate(status)
            if (TERMINAL_STATES.has(status.status)) {
              resolve(status)
            } else {
              timer = setTimeout(tick, intervalMs)
            }
          }
        } catch (err) {
          if (!cancelled) {
            reject(err)
          }
        }
      }

      // Return a cancel function attached to the promise object
      // so callers can abort polling (e.g. on component unmount).
      const promise = { cancel: () => { cancelled = true; clearTimeout(timer) } }
      Object.assign(resolve, { _cancel: () => { cancelled = true; clearTimeout(timer) } })

      tick()

      return promise
    })
  },
}
