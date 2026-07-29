/**
 * useGenerate — UI orchestration hook for triggering test generation.
 *
 * Phase 5: routes submissions through the async V2 job engine
 * (useJobStore.submitJob → POST /api/v2/jobs/generate → polling).
 *
 * Responsibilities:
 *   • Snapshot current editor state (so editor remains editable)
 *   • Prevent duplicate submissions
 *   • Delegate to useJobStore.submitJob()
 *   • Expose generate(), isActive, error, canGenerate
 *
 * Business state (result, status, jobStatus) lives in useJobStore.
 * This hook is pure UI orchestration.
 */
import { useCallback } from 'react'
import { useGenerationStore } from '../stores/useGenerationStore'
import { useJobStore, selectIsActive } from '../stores/useJobStore'

export function useGenerate() {
  const sourceCode    = useGenerationStore((s) => s.sourceCode)
  const specification = useGenerationStore((s) => s.specification)
  const language      = useGenerationStore((s) => s.language)
  const framework     = useGenerationStore((s) => s.framework)

  const submitJob  = useJobStore((s) => s.submitJob)
  const error      = useJobStore((s) => s.error)
  const clearError = useJobStore((s) => s.clearError)
  const isActive   = useJobStore(selectIsActive)

  /**
   * Trigger async test generation.
   *
   * 1. Guard: skip if already active or editor is empty.
   * 2. Snapshot: freeze current editor state.
   * 3. Delegate: call jobStore.submitJob(snapshot) which handles
   *    API call, job_id tracking, polling loop, and result loading.
   */
  const handleGenerate = useCallback(() => {
    const trimmed = sourceCode.trim()
    if (!trimmed || isActive) return

    const snapshot = {
      source_code: sourceCode,
      specification: specification || null,
      language,
      framework,
    }

    submitJob(snapshot)
  }, [sourceCode, specification, language, framework, isActive, submitJob])

  /** Whether the generate button should be enabled */
  const canGenerate = !!sourceCode.trim() && !isActive

  return {
    generate: handleGenerate,
    isGenerating: isActive,
    error,
    clearError,
    canGenerate,
  }
}
