/**
 * ConfidencePanel — displays quality confidence score for completed jobs.
 *
 * Reads from useJobStore.jobStatus.confidence (populated by Phase 4 backend
 * when ENABLE_CONFIDENCE=True and job status='completed').
 *
 * Shows:
 *   • Overall score (0.0–1.0) as a circular progress indicator
 *   • Grade badge (HIGH / MEDIUM / LOW)
 *   • Three signal bars (sandbox, validation, test_count)
 *   • Raw metadata (test count, warning count, sandbox exit code)
 *
 * Returns null when confidence data is not available (e.g. ENABLE_CONFIDENCE=False).
 */
import { useJobStore, selectConfidence } from '../../stores/useJobStore'

const GRADE_CONFIG = {
  HIGH:   { label: 'HIGH',   color: 'text-emerald-700 dark:text-emerald-400', bg: 'bg-emerald-100 dark:bg-emerald-900/30', ring: 'stroke-emerald-500 dark:stroke-emerald-400' },
  MEDIUM: { label: 'MEDIUM', color: 'text-amber-700 dark:text-amber-400',     bg: 'bg-amber-100 dark:bg-amber-900/30',     ring: 'stroke-amber-500 dark:stroke-amber-400' },
  LOW:    { label: 'LOW',    color: 'text-red-700 dark:text-red-400',          bg: 'bg-red-100 dark:bg-red-900/30',          ring: 'stroke-red-500 dark:stroke-red-400' },
}

function CircularScore({ score, grade }) {
  const cfg = GRADE_CONFIG[grade] || GRADE_CONFIG.MEDIUM
  const radius = 36
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - score)

  return (
    <div className="relative flex h-24 w-24 items-center justify-center">
      <svg className="absolute inset-0 -rotate-90" viewBox="0 0 80 80" fill="none">
        {/* Track */}
        <circle cx="40" cy="40" r={radius} strokeWidth="6" className="stroke-gray-200 dark:stroke-gray-700" />
        {/* Progress */}
        <circle
          cx="40" cy="40" r={radius}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className={`transition-all duration-700 ${cfg.ring}`}
        />
      </svg>
      <div className="text-center">
        <span className={`text-lg font-bold ${cfg.color}`}>
          {Math.round(score * 100)}%
        </span>
      </div>
    </div>
  )
}

function SignalBar({ label, value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 55 ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium capitalize text-gray-600 dark:text-gray-400">
          {label}
        </span>
        <span className="text-xs font-semibold text-gray-800 dark:text-gray-200">
          {pct}%
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100 dark:bg-gray-800">
        <div
          className={`h-1.5 rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function ConfidencePanel() {
  const confidence = useJobStore(selectConfidence)

  if (!confidence) return null

  const { overall, grade, signals, metadata } = confidence
  const cfg = GRADE_CONFIG[grade] || GRADE_CONFIG.MEDIUM

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
      <h4 className="mb-4 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
        Quality Confidence
      </h4>

      <div className="flex items-start gap-5">
        {/* Circular score */}
        <CircularScore score={overall} grade={grade} />

        {/* Grade + metadata */}
        <div className="flex flex-1 flex-col gap-2">
          <span className={`inline-flex w-fit rounded-full px-2.5 py-0.5 text-xs font-semibold ${cfg.bg} ${cfg.color}`}>
            {cfg.label}
          </span>

          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="flex flex-col">
              <span className="text-gray-400 dark:text-gray-500">Tests</span>
              <span className="font-semibold text-gray-800 dark:text-gray-200">{metadata.test_count}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-gray-400 dark:text-gray-500">Warnings</span>
              <span className="font-semibold text-gray-800 dark:text-gray-200">{metadata.warning_count}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-gray-400 dark:text-gray-500">Exit Code</span>
              <span className="font-semibold text-gray-800 dark:text-gray-200">
                {metadata.sandbox_exit_code ?? '—'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Signal bars */}
      <div className="mt-4 flex flex-col gap-2.5">
        <SignalBar label="Sandbox Execution" value={signals.sandbox} />
        <SignalBar label="Validation Quality" value={signals.validation} />
        <SignalBar label="Test Coverage" value={signals.test_count} />
      </div>
    </div>
  )
}
