/**
 * ResultPanel — main result workspace container.
 *
 * Phase 5: reads from useJobStore for async job state.
 * Result data (result object) is also in useJobStore after the V1
 * generation is fetched on completion.
 *
 * States:
 *   1. Empty (no job) → ResultEmptyState
 *   2. Loading (submitting | polling | loading result) → LoadingState
 *   3. Job failed → FailureState
 *   4. Result ready → Tabbed interface (Summary / Tests / Code / Warnings / Sandbox)
 *
 * Tab selection persists across generations — only data refreshes.
 */
import { useState } from 'react'
import { useJobStore, selectIsActive } from '../../stores/useJobStore'
import { useGenerationStore } from '../../stores/useGenerationStore'
import LoadingState from './LoadingState'
import SummaryPanel from './SummaryPanel'
import TestSuitePanel from './TestSuitePanel'
import CodePanel from './CodePanel'
import WarningsPanel from './WarningsPanel'
import SandboxPanel from './SandboxPanel'
import QualityDashboard from '../Quality/QualityDashboard'
import ConfidencePanel from './ConfidencePanel'

const TABS = [
  { id: 'summary',   label: 'Summary' },
  { id: 'quality',   label: 'Quality & Mutation' },
  { id: 'tests',     label: 'Generated Tests' },
  { id: 'code',      label: 'Generated Code' },
  { id: 'warnings',  label: 'Warnings' },
  { id: 'sandbox',   label: 'Sandbox' },
]

function ResultEmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-5 inline-flex rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 p-5 dark:from-blue-900/20 dark:to-indigo-900/20">
        <svg
          className="h-12 w-12 text-blue-400 dark:text-blue-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
        Results will appear here
      </h3>
      <p className="mt-2 max-w-xs text-sm text-gray-500 dark:text-gray-400">
        Write or paste your Python function, then click <strong>Generate Tests</strong> to see
        AI-generated test cases, code, and validation results.
      </p>
      <div className="mt-5 flex items-center gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 dark:border-gray-800 dark:bg-gray-900">
        <kbd className="rounded border border-gray-200 bg-white px-1.5 py-0.5 text-[10px] font-mono font-medium text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
          Ctrl+Enter
        </kbd>
        <span className="text-xs text-gray-400 dark:text-gray-500">to generate tests</span>
      </div>
    </div>
  )
}

function FailureState({ error, jobStatus, onRetry }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-5 inline-flex rounded-2xl bg-red-50 p-5 dark:bg-red-900/20">
        <svg
          className="h-12 w-12 text-red-400 dark:text-red-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      </div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
        Generation Failed
      </h3>
      <p className="mt-2 max-w-sm text-sm text-gray-500 dark:text-gray-400">
        {error?.message || jobStatus?.error_detail || 'An error occurred during test generation.'}
      </p>
      {(error?.code || jobStatus?.error_code) && (
        <p className="mt-1 text-xs font-mono text-gray-400 dark:text-gray-500">
          Error code: {error?.code || jobStatus?.error_code}
        </p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="
            mt-5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white
            transition-all hover:bg-blue-500 active:scale-[0.98] cursor-pointer
          "
        >
          Try Again
        </button>
      )}
    </div>
  )
}

function TabButton({ tab, isActive, onClick }) {
  return (
    <button
      role="tab"
      aria-selected={isActive}
      onClick={onClick}
      className={`
        relative whitespace-nowrap px-3 py-2.5 text-xs font-medium transition-colors cursor-pointer
        ${isActive
          ? 'text-blue-600 dark:text-blue-400'
          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
        }
      `}
    >
      {tab.label}
      {isActive && (
        <span className="absolute inset-x-0 bottom-0 h-0.5 rounded-full bg-blue-500 dark:bg-blue-400" />
      )}
    </button>
  )
}

export default function ResultPanel() {
  const [activeTab, setActiveTab] = useState(0)

  // Phase 5: primary state from job store
  const jobResult  = useJobStore((s) => s.result)
  const jobStatus  = useJobStore((s) => s.jobStatus)
  const jobError   = useJobStore((s) => s.error)
  const isActive   = useJobStore(selectIsActive)
  const reset      = useJobStore((s) => s.reset)

  // Legacy V1 result (from history / deep link)
  const v1Result = useGenerationStore((s) => s.result)

  // Use job store result (async path) or fall back to V1 result
  const result = jobResult ?? v1Result

  const sourceCode = useGenerationStore((s) => s.sourceCode)

  const jobFailed = jobStatus?.status === 'failed' || jobStatus?.status === 'cancelled'

  // State 1: Loading (any async operation in-flight)
  if (isActive) {
    return (
      <div className="flex h-full flex-col">
        <LoadingState />
      </div>
    )
  }

  // State 2: Job failed
  if (jobFailed && !result) {
    return (
      <FailureState
        error={jobError}
        jobStatus={jobStatus}
        onRetry={reset}
      />
    )
  }

  // State 3: No result yet
  if (!result) {
    return <ResultEmptyState />
  }

  // State 4: Result ready — tabbed interface
  const panels = [
    <SummaryPanel key="summary" />,
    <div key="quality" className="p-4">
      <QualityDashboard jobId={jobStatus?.job_id} />
    </div>,
    <TestSuitePanel key="tests" />,
    <CodePanel key="code" />,
    <WarningsPanel key="warnings" />,
    <div key="sandbox" className="flex flex-col gap-4 p-4">
      <SandboxPanel />
      <ConfidencePanel />
    </div>,
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Tab bar */}
      <div
        role="tablist"
        className="flex border-b border-gray-100 px-2 dark:border-gray-800"
      >
        {TABS.map((tab, i) => (
          <TabButton
            key={tab.id}
            tab={tab}
            isActive={activeTab === i}
            onClick={() => setActiveTab(i)}
          />
        ))}
      </div>

      {/* Active panel */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {panels[activeTab]}
      </div>
    </div>
  )
}
