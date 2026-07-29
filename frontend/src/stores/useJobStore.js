import { create } from 'zustand'
import { jobService, TERMINAL_STATES } from '../api/jobService'
import { generationService } from '../api/generationService'

/**
 * useJobStore — async job lifecycle state.
 *
 * Manages the complete V2 async generation flow:
 *   1. submitJob()  — POST /api/v2/jobs/generate → job_id
 *   2. startPolling() — GET /api/v2/jobs/{job_id} until terminal state
 *   3. loadResult() — GET /api/v1/generations/{generation_id}
 *
 * Architecture: polling is interval-based (no WebSockets or SSE).
 * Terminal states: completed | failed | cancelled
 *
 * This store is the Phase 5 replacement for useGenerationStore.generate()
 * for the async V2 path. The existing generation store remains for the
 * V1 history and deep-link loading paths.
 */

export const useJobStore = create((set, get) => ({
  // ── Job lifecycle state ──────────────────────────────────────────────────

  /** UUID of the current job, or null */
  jobId: null,

  /**
   * Current job status object from GET /api/v2/jobs/{job_id}
   * Shape: { job_id, status, retry_count, last_checkpoint,
   *          generation_id, error_code, error_detail,
   *          created_at, updated_at, confidence }
   */
  jobStatus: null,

  /** True while submitting the job (before job_id is received) */
  isSubmitting: false,

  /** True while polling for a non-terminal status */
  isPolling: false,

  /** True while fetching the Generation result from V1 API */
  isLoadingResult: false,

  /**
   * The full Generation result fetched from /api/v1/generations/{id}
   * after the job completes. Shape matches existing GenerationResponse.
   */
  result: null,

  /** Normalized error from any phase of the flow, or null */
  error: null,

  /** Cancel function for the active poll loop (set by startPolling) */
  _cancelPoll: null,

  // ── Derived ──────────────────────────────────────────────────────────────

  /**
   * True if any async operation (submit | poll | load) is in flight.
   * Used by UI components to show a unified loading indicator.
   */
  get isActive() {
    const s = get()
    return s.isSubmitting || s.isPolling || s.isLoadingResult
  },

  // ── Actions ──────────────────────────────────────────────────────────────

  /** Reset all state (new submission resets everything). */
  reset: () => {
    // Cancel any in-flight poll first
    const cancel = get()._cancelPoll
    if (cancel) cancel()

    set({
      jobId: null,
      jobStatus: null,
      isSubmitting: false,
      isPolling: false,
      isLoadingResult: false,
      result: null,
      error: null,
      _cancelPoll: null,
    })
  },

  clearError: () => set({ error: null }),

  /**
   * submitJob(snapshot) — Phase 5 primary action.
   *
   * Lifecycle:
   *   reset → isSubmitting → POST /jobs/generate → startPolling
   *
   * @param {Object} snapshot  Frozen editor state at submit time.
   */
  submitJob: async (snapshot) => {
    if (!snapshot.source_code?.trim()) {
      set({ error: { message: 'Source code is required.', code: 'VALIDATION_ERROR' } })
      return
    }

    get().reset()

    set({ isSubmitting: true, error: null })

    try {
      const response = await jobService.submitJob({
        source_code: snapshot.source_code,
        specification: snapshot.specification || null,
        language: snapshot.language,
        framework: snapshot.framework,
      })

      const jobId = response.job_id
      set({
        jobId,
        jobStatus: { job_id: jobId, status: response.status },
        isSubmitting: false,
        isPolling: true,
      })

      // Start polling immediately
      get().startPolling(jobId)
    } catch (err) {
      set({
        isSubmitting: false,
        error: {
          message: err.message || 'Failed to submit generation job.',
          code: err.code || 'SUBMIT_FAILED',
        },
      })
    }
  },

  /**
   * startPolling(jobId) — begin polling GET /api/v2/jobs/{jobId}.
   *
   * Called automatically by submitJob. Can also be called directly
   * for recovery (e.g. after page reload with a known job_id).
   *
   * Stops automatically when a terminal state is reached or on error.
   */
  startPolling: (jobId) => {
    const INTERVAL_MS = parseInt(import.meta.env.VITE_POLL_INTERVAL_MS || '2000', 10)
    const TIMEOUT_MS  = parseInt(import.meta.env.VITE_POLL_TIMEOUT_MS  || '300000', 10)

    let cancelled = false
    let timer = null
    const startTime = Date.now()

    function cancel() {
      cancelled = true
      if (timer) clearTimeout(timer)
    }

    async function tick() {
      if (cancelled) return

      if (Date.now() - startTime > TIMEOUT_MS) {
        set({
          isPolling: false,
          error: {
            message: `Generation timed out after ${TIMEOUT_MS / 1000}s. The job may still be running.`,
            code: 'POLL_TIMEOUT',
          },
        })
        return
      }

      try {
        const status = await jobService.getJobStatus(jobId)

        if (cancelled) return

        set({ jobStatus: status })

        if (TERMINAL_STATES.has(status.status)) {
          set({ isPolling: false })

          if (status.status === 'completed' && status.generation_id) {
            get().loadResult(status.generation_id)
          } else if (status.status === 'failed') {
            set({
              error: {
                message: status.error_detail || 'Generation failed on the server.',
                code: status.error_code || 'JOB_FAILED',
              },
            })
          } else if (status.status === 'cancelled') {
            set({
              error: {
                message: 'The generation job was cancelled.',
                code: 'JOB_CANCELLED',
              },
            })
          }
        } else {
          timer = setTimeout(tick, INTERVAL_MS)
        }
      } catch (err) {
        if (!cancelled) {
          set({
            isPolling: false,
            error: {
              message: err.message || 'Lost connection while polling job status.',
              code: err.code || 'POLL_ERROR',
            },
          })
        }
      }
    }

    set({ _cancelPoll: cancel })
    tick()
  },

  /**
   * loadResult(generationId) — fetch the full Generation from V1 API.
   *
   * Called automatically after job reaches COMPLETED state.
   * The result is stored in `result` — identical shape to V1 responses,
   * so existing ResultPanel / SummaryPanel / CodePanel components work
   * without modification.
   */
  loadResult: async (generationId) => {
    set({ isLoadingResult: true })

    try {
      const generation = await generationService.getGeneration(generationId)
      set({ result: generation, isLoadingResult: false })
    } catch (err) {
      set({
        isLoadingResult: false,
        error: {
          message: err.message || 'Failed to load generation results.',
          code: err.code || 'LOAD_RESULT_FAILED',
        },
      })
    }
  },

  /**
   * retrySubmit(snapshot) — re-submit as a brand-new job.
   *
   * Does not retry the same job_id — creates a new one.
   */
  retrySubmit: (snapshot) => get().submitJob(snapshot),
}))

// ── Selectors ─────────────────────────────────────────────────────────────────

/** Current job status string ('pending' | 'processing' | 'completed' | 'failed' | null) */
export const selectJobStatusStr = (s) => s.jobStatus?.status ?? null

/** True when the job has reached a terminal state */
export const selectIsTerminal = (s) =>
  s.jobStatus ? TERMINAL_STATES.has(s.jobStatus.status) : false

/** Confidence object from the latest job status response (or null) */
export const selectConfidence = (s) => s.jobStatus?.confidence ?? null

/** Last checkpoint name (for progress display during polling) */
export const selectLastCheckpoint = (s) => s.jobStatus?.last_checkpoint ?? null

/** True when any async operation is in progress */
export const selectIsActive = (s) =>
  s.isSubmitting || s.isPolling || s.isLoadingResult
