/**
 * LoadingState — real-time pipeline progress during async job execution.
 *
 * Phase 5: reads live job status from useJobStore so the displayed
 * stage reflects actual backend checkpoint progress, not a simulated
 * sequence. Falls back to animated stage cycling when no checkpoint
 * is available yet.
 *
 * Displays:
 *   • Animated spinner
 *   • Current stage message (from last_checkpoint or animated fallback)
 *   • Job status badge (pending | processing)
 *   • Retry count (if > 0)
 *   • Progress dots
 */
import { useState, useEffect, useRef } from 'react'
import { useJobStore } from '../../stores/useJobStore'
import StatusBadge from '../common/StatusBadge'

// Fallback animation stages shown while waiting for the first checkpoint
const ANIMATION_STAGES = [
  { message: 'Submitting job to engine...', icon: '🚀', checkpoint: null },
  { message: 'Analysing source code...', icon: '🔍', checkpoint: 'ANALYZED' },
  { message: 'Building prompt...', icon: '📝', checkpoint: 'PROMPTED' },
  { message: 'Contacting AI model...', icon: '🤖', checkpoint: 'LLM_RESPONDED' },
  { message: 'Parsing response...', icon: '🔧', checkpoint: 'PARSED' },
  { message: 'Running sandbox tests...', icon: '⚡', checkpoint: 'SANDBOX_TESTED' },
  { message: 'Rendering results...', icon: '🎨', checkpoint: null },
]

/** Map backend checkpoint name to stage index */
const CHECKPOINT_TO_STAGE = {
  ANALYZED:        1,
  PROMPTED:        2,
  LLM_RESPONDED:   3,
  PARSED:          4,
  SANDBOX_TESTED:  5,
}

export default function LoadingState() {
  const jobStatus = useJobStore((s) => s.jobStatus)
  const isSubmitting = useJobStore((s) => s.isSubmitting)
  const isLoadingResult = useJobStore((s) => s.isLoadingResult)

  const lastCheckpoint = jobStatus?.last_checkpoint ?? null
  const retryCount = jobStatus?.retry_count ?? 0
  const status = jobStatus?.status ?? (isSubmitting ? 'pending' : 'processing')

  // Derive stage index from real checkpoint, or animate forward
  const checkpointStage = lastCheckpoint ? (CHECKPOINT_TO_STAGE[lastCheckpoint] ?? 0) : null
  const [animStage, setAnimStage] = useState(0)
  const timers = useRef([])

  // Animate stage cycling only when there's no real checkpoint data
  useEffect(() => {
    if (checkpointStage !== null) return // Real data available — skip animation

    timers.current.forEach(clearTimeout)
    timers.current = []

    const delays = [0, 2500, 5000, 9000, 13000, 17000, 21000]
    delays.forEach((delay, idx) => {
      if (idx === 0) return
      const t = setTimeout(() => setAnimStage(idx), delay)
      timers.current.push(t)
    })

    return () => timers.current.forEach(clearTimeout)
  }, [checkpointStage])

  const stageIndex = checkpointStage !== null ? checkpointStage : animStage
  const clampedIndex = Math.min(stageIndex, ANIMATION_STAGES.length - 1)
  const stage = ANIMATION_STAGES[clampedIndex]

  // While loading the result (after COMPLETED), show a distinct message
  if (isLoadingResult) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6">
        <div className="relative mb-8">
          <div className="h-16 w-16 rounded-full border-4 border-gray-200 dark:border-gray-700" />
          <div className="absolute inset-0 h-16 w-16 animate-spin rounded-full border-4 border-transparent border-t-emerald-500 dark:border-t-emerald-400" />
          <div className="absolute inset-0 flex items-center justify-center text-2xl">🎨</div>
        </div>
        <p className="text-base font-medium text-gray-700 dark:text-gray-200">
          Loading results…
        </p>
        <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
          Fetching generated tests from the server.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      {/* Animated spinner */}
      <div className="relative mb-8">
        <div className="h-16 w-16 rounded-full border-4 border-gray-200 dark:border-gray-700" />
        <div className="absolute inset-0 h-16 w-16 animate-spin rounded-full border-4 border-transparent border-t-blue-500 dark:border-t-blue-400" />
        <div className="absolute inset-0 flex items-center justify-center text-2xl">
          {stage.icon}
        </div>
      </div>

      {/* Status badge + retry count */}
      <div className="mb-3 flex items-center gap-2">
        <StatusBadge status={status} />
        {retryCount > 0 && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
            Retry #{retryCount}
          </span>
        )}
      </div>

      {/* Current stage message */}
      <p className="text-base font-medium text-gray-700 dark:text-gray-200 transition-all duration-300">
        {stage.message}
      </p>

      {/* Last checkpoint name (real data only) */}
      {lastCheckpoint && (
        <p className="mt-1.5 text-xs font-mono text-gray-400 dark:text-gray-500">
          checkpoint: {lastCheckpoint}
        </p>
      )}

      {/* Progress dots */}
      <div className="mt-6 flex items-center gap-2">
        {ANIMATION_STAGES.map((_, i) => (
          <div
            key={i}
            className={`h-1.5 rounded-full transition-all duration-500 ${
              i <= clampedIndex
                ? 'w-6 bg-blue-500 dark:bg-blue-400'
                : 'w-1.5 bg-gray-200 dark:bg-gray-700'
            }`}
          />
        ))}
      </div>

      {/* Tip */}
      <p className="mt-8 text-xs text-gray-400 dark:text-gray-500">
        The editor remains editable while generating.
      </p>
    </div>
  )
}
