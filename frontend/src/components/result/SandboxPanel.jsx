import { useJobStore } from '../../stores/useJobStore'

const EXIT_CODE_CONFIG = {
  0:  { label: 'All Tests Passed', icon: '✓', color: 'text-emerald-700 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/20', border: 'border-emerald-200 dark:border-emerald-800/50' },
  1:  { label: 'Test Failures Detected', icon: '✗', color: 'text-red-700 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-900/20', border: 'border-red-200 dark:border-red-800/50' },
  '-1': { label: 'Sandbox Unavailable', icon: '–', color: 'text-gray-600 dark:text-gray-400', bg: 'bg-gray-50 dark:bg-gray-900', border: 'border-gray-200 dark:border-gray-800' },
}

const getRatingBadge = (pct) => {
  if (pct >= 90) return { label: 'Excellent', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/50' }
  if (pct >= 80) return { label: 'Good', cls: 'bg-emerald-50/70 text-emerald-600 border-emerald-200/60 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-800/40' }
  if (pct >= 60) return { label: 'Fair', cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-800/40' }
  return { label: 'Needs Improvement', cls: 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/30 dark:text-red-400 dark:border-red-800/40' }
}

const getCovColorClass = (pct) => {
  if (pct === null) return 'text-gray-500'
  if (pct >= 80) return 'text-emerald-600 dark:text-emerald-400'
  if (pct >= 50) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

const getMissingColorClass = (count) => {
  if (count === null) return 'text-gray-500'
  if (count === 0) return 'text-emerald-600 dark:text-emerald-400'
  if (count <= 5) return 'text-amber-600 dark:text-amber-400'
  return 'text-red-600 dark:text-red-400'
}

export default function SandboxPanel() {
  const jobStatus = useJobStore((s) => s.jobStatus)
  const result    = useJobStore((s) => s.result)

  const exitCode = jobStatus?.confidence?.metadata?.sandbox_exit_code ?? null
  const sandboxDuration = result?.sandbox_duration_ms ?? jobStatus?.confidence?.metadata?.sandbox_duration_ms ?? null
  const hasResult = jobStatus?.status === 'completed'

  if (!hasResult) return null

  const codeStr = exitCode !== null ? String(exitCode) : null
  const cfg = codeStr !== null ? (EXIT_CODE_CONFIG[codeStr] || EXIT_CODE_CONFIG[1]) : null

  // Sandbox stdout/stderr from generation result
  const sandboxOutput = result?.sandbox_stdout ?? null
  const sandboxStderr = result?.sandbox_stderr ?? null

  // Code coverage metrics from GenerationResponse
  const lineCov = result?.coverage_line_pct ?? null
  const branchCov = result?.coverage_branch_pct ?? null
  const totalStatements = result?.coverage_total_statements ?? null
  const coveredStatements = result?.coverage_covered_statements ?? null
  const missingStatements = result?.coverage_missing_statements ?? null

  const hasCoverage = lineCov !== null
  const badge = hasCoverage ? getRatingBadge(lineCov) : null

  // Feature #2: Self-Healing Test Generation metadata
  const repairAttempted = result?.repair_attempted ?? jobStatus?.confidence?.metadata?.repair_attempted ?? null
  const repairSuccess = result?.repair_success ?? jobStatus?.confidence?.metadata?.repair_success ?? false
  const repairCount = result?.repair_count ?? jobStatus?.confidence?.metadata?.repair_count ?? 0
  const repairDurationMs = result?.repair_duration_ms ?? jobStatus?.confidence?.metadata?.repair_duration_ms ?? 0.0
  const repairFailureType = result?.repair_failure_type ?? jobStatus?.confidence?.metadata?.repair_failure_type ?? null
  const repairReason = result?.repair_reason ?? jobStatus?.confidence?.metadata?.repair_reason ?? null

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <h4 className="mb-4 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        Sandbox Execution
      </h4>

      {exitCode === null ? (
        <div className="flex items-center gap-2 text-sm text-gray-400 dark:text-gray-500">
          <span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600" />
          Sandbox results not available
        </div>
      ) : (
        <>
          {/* Status row */}
          <div className={`flex items-center gap-3 rounded-lg border px-3 py-2.5 ${cfg.bg} ${cfg.border}`}>
            <span className={`text-lg font-bold ${cfg.color}`}>{cfg.icon}</span>
            <div>
              <p className={`text-sm font-semibold ${cfg.color}`}>{cfg.label}</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Exit code: <code className="font-mono">{exitCode}</code>
                {sandboxDuration !== null && (
                  <span className="ml-2 pl-2 border-l border-gray-200 dark:border-gray-700">
                    Execution time: <code className="font-mono">{Math.round(sandboxDuration)} ms</code>
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Sandbox stdout */}
          {sandboxOutput && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                Output
              </p>
              <pre className="overflow-auto rounded-lg bg-gray-950 p-3 text-xs text-green-400 dark:bg-gray-950 max-h-48">
                {sandboxOutput}
              </pre>
            </div>
          )}

          {/* Sandbox stderr */}
          {sandboxStderr && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs font-medium text-red-500 dark:text-red-400">
                Errors / Warnings
              </p>
              <pre className="overflow-auto rounded-lg bg-gray-950 p-3 text-xs text-red-400 dark:bg-gray-950 max-h-32">
                {sandboxStderr}
              </pre>
            </div>
          )}
        </>
      )}

      {/* Code Coverage Section */}
      <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Code Coverage
          </h4>
          {hasCoverage && badge && (
            <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${badge.cls}`}>
              {badge.label}
            </span>
          )}
        </div>

        {!hasCoverage ? (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic">
            Coverage not available
          </p>
        ) : (
          <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3 dark:border-gray-800 dark:bg-gray-950/50">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Line Coverage</p>
                <p className={`text-base font-bold font-mono ${getCovColorClass(lineCov)}`}>
                  {lineCov.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Branch Coverage</p>
                <p className={`text-base font-bold font-mono ${getCovColorClass(branchCov)}`}>
                  {branchCov !== null ? `${branchCov.toFixed(1)}%` : '–'}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Statements Covered</p>
                <p className="text-base font-bold font-mono text-gray-900 dark:text-gray-100">
                  {coveredStatements !== null && totalStatements !== null
                    ? `${coveredStatements} / ${totalStatements}`
                    : '–'}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Missing Statements</p>
                <p className={`text-base font-bold font-mono ${getMissingColorClass(missingStatements)}`}>
                  {missingStatements !== null ? missingStatements : '–'}
                </p>
              </div>
            </div>
            <p className="mt-2.5 text-[11px] text-gray-400 dark:text-gray-500 border-t border-gray-200/50 pt-2 dark:border-gray-800/60">
              Coverage indicates how much of the submitted source code is exercised by the generated tests.
            </p>
          </div>
        )}
      </div>

      {/* Feature #2: Self-Healing Section */}
      <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            Self-Healing
          </h4>
          {repairAttempted !== undefined && repairAttempted !== null && (
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                !repairAttempted
                  ? 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-900/60 dark:text-gray-300 dark:border-gray-800'
                  : repairSuccess
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800/50'
                  : 'bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-400 dark:border-red-800/50'
              }`}
            >
              {!repairAttempted
                ? 'Not Required'
                : repairSuccess
                ? '✓ Self-Healed'
                : '✗ Repair Failed'}
            </span>
          )}
        </div>

        {repairAttempted === undefined || repairAttempted === null ? (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic">
            Self-Healing information unavailable
          </p>
        ) : (
          <div className="rounded-lg border border-gray-100 bg-gray-50/50 p-3 dark:border-gray-800 dark:bg-gray-950/50">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Repair Status</p>
                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100 mt-0.5">
                  {!repairAttempted
                    ? 'Not Required'
                    : repairSuccess
                    ? 'Self-Healed'
                    : 'Repair Failed'}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Repair Attempts</p>
                <p className="text-base font-bold font-mono text-gray-900 dark:text-gray-100">
                  {repairCount ?? 0}
                </p>
              </div>
              <div>
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Repair Duration</p>
                <p className="text-base font-bold font-mono text-gray-900 dark:text-gray-100">
                  {repairDurationMs !== null && repairDurationMs !== undefined
                    ? `${Number(repairDurationMs).toFixed(1)} ms`
                    : '0.0 ms'}
                </p>
              </div>
              {repairFailureType && (
                <div>
                  <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Failure Type</p>
                  <p className="text-xs font-semibold font-mono text-amber-600 dark:text-amber-400 mt-1">
                    {repairFailureType}
                  </p>
                </div>
              )}
            </div>

            {repairReason && (
              <div className="mt-2.5 pt-2 border-t border-gray-200/50 dark:border-gray-800/60">
                <p className="text-[11px] font-medium text-gray-500 dark:text-gray-400">Failure Reason</p>
                <p className="text-xs text-gray-700 dark:text-gray-300 font-mono mt-0.5">
                  {repairReason}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
