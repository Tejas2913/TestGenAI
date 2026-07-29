/**
 * SummaryPanel — displays generation metadata and job info.
 *
 * Phase 5: augmented to show async job details (job_id, retry_count,
 * checkpoint) alongside the existing generation metadata. Reads from
 * both useJobStore (job lifecycle) and the generation result object.
 * Falls back gracefully when job data is not present (V1 history path).
 *
 * Renders: function name, status, prompt version, timestamp,
 * duration, token usage, job metadata, error section for failures.
 */
import { useMemo } from 'react'
import { useJobStore } from '../../stores/useJobStore'
import { useGenerationStore } from '../../stores/useGenerationStore'
import Badge from '../common/Badge'
import StatusBadge from '../common/StatusBadge'
import { formatDuration, formatTokens, formatTimestamp } from '../../utils/codeActions'

function MetaItem({ label, children }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {label}
      </span>
      <span className="text-sm text-gray-800 dark:text-gray-200">
        {children ?? <span className="text-gray-300 dark:text-gray-600">—</span>}
      </span>
    </div>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-gray-100 bg-gray-50 px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
      <span className="text-xl font-bold text-gray-900 dark:text-white">
        {value ?? <span className="text-gray-300 dark:text-gray-600">—</span>}
      </span>
      <span className="mt-0.5 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
        {label}
      </span>
    </div>
  )
}

export default function SummaryPanel() {
  // Phase 5: job store is primary for async path
  const jobResult  = useJobStore((s) => s.result)
  const jobStatus  = useJobStore((s) => s.jobStatus)
  const jobError   = useJobStore((s) => s.error)

  // V1 history fallback
  const v1Result = useGenerationStore((s) => s.result)

  const result = jobResult ?? v1Result

  // Parse JSON once — memoized to avoid new object on every render
  const parsed = useMemo(() => {
    if (!result?.generated_tests_json) return null
    try {
      return JSON.parse(result.generated_tests_json)
    } catch {
      return null
    }
  }, [result?.generated_tests_json])

  if (!result) return null

  const functionName = parsed?.function_name || null
  const testCount    = parsed?.test_cases?.length ?? null
  const duration     = formatDuration(result.duration_ms)
  const timestamp    = formatTimestamp(result.created_at)

  // Combine status: job status takes priority over generation status
  const displayStatus = jobStatus?.status ?? result.status

  // Job metadata (async path)
  const jobId        = jobStatus?.job_id ?? null
  const retryCount   = jobStatus?.retry_count ?? 0
  const checkpoint   = jobStatus?.last_checkpoint ?? null

  // Error information
  const hasError = displayStatus === 'failed' || displayStatus === 'cancelled'
  const errorMessage = jobStatus?.error_detail || result.error_message || jobError?.message

  return (
    <div className="flex flex-col gap-5 p-4 overflow-y-auto">
      {/* Function & Status */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {functionName || <span className="text-gray-400 italic">Function name not available</span>}
          </h3>
          {timestamp && (
            <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{timestamp}</p>
          )}
        </div>
        <StatusBadge status={displayStatus} />
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Tests" value={testCount} />
        <StatCard label="Duration" value={duration} />
        <StatCard label="Tokens" value={formatTokens(result.total_tokens)} />
        <StatCard label="Status" value={displayStatus === 'completed' ? '✓ Done' : displayStatus} />
      </div>

      {/* Generation details */}
      <div className="rounded-lg border border-gray-100 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Generation Details
        </h4>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          <MetaItem label="Language">
            <Badge color="blue">{result.language}</Badge>
          </MetaItem>
          <MetaItem label="Framework">
            <Badge color="purple">{result.framework}</Badge>
          </MetaItem>
          <MetaItem label="Prompt Version">
            {result.prompt_version && <Badge color="gray">{result.prompt_version}</Badge>}
          </MetaItem>
          <MetaItem label="Input Tokens">{formatTokens(result.input_tokens)}</MetaItem>
          <MetaItem label="Output Tokens">{formatTokens(result.output_tokens)}</MetaItem>
          <MetaItem label="Generation ID">
            <span className="font-mono text-xs break-all">{result.id?.slice(0, 8)}</span>
          </MetaItem>
        </div>
      </div>

      {/* Job details (async path only) */}
      {jobId && (
        <div className="rounded-lg border border-gray-100 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
          <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Async Job Details
          </h4>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
            <MetaItem label="Job ID">
              <span className="font-mono text-xs break-all">{jobId?.slice(0, 8)}</span>
            </MetaItem>
            <MetaItem label="Retry Count">
              {retryCount > 0 ? (
                <Badge color="amber">{retryCount} retries</Badge>
              ) : (
                <Badge color="green">No retries</Badge>
              )}
            </MetaItem>
            <MetaItem label="Last Checkpoint">
              {checkpoint ? (
                <span className="font-mono text-xs">{checkpoint}</span>
              ) : null}
            </MetaItem>
          </div>
        </div>
      )}

      {/* Error message for failed generations */}
      {hasError && errorMessage && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800/50 dark:bg-red-900/20">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-red-600 dark:text-red-400">
            Error
          </h4>
          <p className="mt-1 text-sm text-red-700 dark:text-red-300">{errorMessage}</p>
          {(jobStatus?.error_code || jobError?.code) && (
            <p className="mt-1 text-xs font-mono text-red-500/70 dark:text-red-400/70">
              {jobStatus?.error_code || jobError?.code}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
