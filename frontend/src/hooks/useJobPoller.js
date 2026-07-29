/**
 * useJobPoller — lightweight hook that bridges useJobStore to component cleanup.
 *
 * Responsibilities:
 *   1. Expose job state to components in a single hook call.
 *   2. Cancel the in-flight poll when the component unmounts (memory-safe).
 *   3. Fire toast notifications on terminal state transitions.
 *
 * This hook contains NO business logic — all state lives in useJobStore.
 */
import { useEffect, useRef } from 'react'
import { useJobStore, selectJobStatusStr, selectIsActive } from '../stores/useJobStore'
import { toast } from '../stores/useToastStore'

export function useJobPoller() {
  const jobId          = useJobStore((s) => s.jobId)
  const jobStatus      = useJobStore((s) => s.jobStatus)
  const result         = useJobStore((s) => s.result)
  const error          = useJobStore((s) => s.error)
  const isSubmitting   = useJobStore((s) => s.isSubmitting)
  const isPolling      = useJobStore((s) => s.isPolling)
  const isLoadingResult= useJobStore((s) => s.isLoadingResult)
  const _cancelPoll    = useJobStore((s) => s._cancelPoll)
  const clearError     = useJobStore((s) => s.clearError)
  const reset          = useJobStore((s) => s.reset)
  const retrySubmit    = useJobStore((s) => s.retrySubmit)

  const statusStr = useJobStore(selectJobStatusStr)
  const isActive  = useJobStore(selectIsActive)

  // Track previous status to detect transitions
  const prevStatusRef = useRef(statusStr)

  // Toast on terminal transitions
  useEffect(() => {
    const prev = prevStatusRef.current
    prevStatusRef.current = statusStr

    if (prev !== 'completed' && statusStr === 'completed') {
      toast.success('Tests generated successfully!')
    }
    if (prev !== 'failed' && statusStr === 'failed') {
      toast.error(error?.message || 'Generation failed.')
    }
    if (prev !== 'cancelled' && statusStr === 'cancelled') {
      toast.warning('Generation was cancelled.')
    }
  }, [statusStr, error])

  // Cancel poll on unmount (memory-safe)
  useEffect(() => {
    return () => {
      if (_cancelPoll) _cancelPoll()
    }
  }, [_cancelPoll])

  return {
    jobId,
    jobStatus,
    statusStr,
    result,
    error,
    isSubmitting,
    isPolling,
    isLoadingResult,
    isActive,
    clearError,
    reset,
    retrySubmit,
  }
}
