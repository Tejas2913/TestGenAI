/**
 * TestSuitePanel — test suite summary + individual test case cards.
 *
 * Statistics computed dynamically from test_cases — no hardcoded categories.
 * Color-coded badges for categories.
 */
import { useMemo } from 'react'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { useJobStore } from '../../stores/useJobStore'
import Badge from '../common/Badge'

/** Category display config — colors and labels */
const CATEGORY_CONFIG = {
  happy_path:     { label: 'Happy Path',     color: 'green',  emoji: '🟢' },
  edge_case:      { label: 'Edge Case',      color: 'amber',  emoji: '🟠' },
  boundary:       { label: 'Boundary',       color: 'amber',  emoji: '🟡' },
  error_handling: { label: 'Error Handling',  color: 'red',    emoji: '🔴' },
  negative:       { label: 'Negative',        color: 'red',    emoji: '🔴' },
  type_check:     { label: 'Type Check',      color: 'purple', emoji: '🟣' },
  performance:    { label: 'Performance',     color: 'blue',   emoji: '🔵' },
  invalid_input:  { label: 'Invalid Input',   color: 'red',    emoji: '🔴' },
}

function getCategoryDisplay(category) {
  return CATEGORY_CONFIG[category] || {
    label: category?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Other',
    color: 'gray',
    emoji: '⚪',
  }
}

/** Stat card for category counts */
function CategoryStat({ category, count }) {
  const display = getCategoryDisplay(category)
  return (
    <div className="flex flex-col items-center rounded-lg border border-gray-100 bg-gray-50 px-3 py-2.5 dark:border-gray-800 dark:bg-gray-900">
      <span className="text-lg font-bold text-gray-900 dark:text-white">{count}</span>
      <span className="mt-0.5 text-[10px] font-medium text-gray-500 dark:text-gray-400">
        {display.emoji} {display.label}
      </span>
    </div>
  )
}

/** Individual test case card */
function TestCaseCard({ testCase }) {
  const display = getCategoryDisplay(testCase.category)

  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 transition-colors hover:border-gray-200 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white truncate" title={testCase.name}>
            {testCase.name}
          </h4>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            {testCase.description}
          </p>
        </div>
        <Badge color={display.color}>{display.label}</Badge>
      </div>

      {/* Inputs */}
      {testCase.inputs && Object.keys(testCase.inputs).length > 0 && (
        <div className="mt-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Inputs
          </span>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {Object.entries(testCase.inputs).map(([key, value]) => (
              <code
                key={key}
                className="rounded bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                {key}={JSON.stringify(value)}
              </code>
            ))}
          </div>
        </div>
      )}

      {/* Expected output */}
      {testCase.expected_output !== undefined && testCase.expected_output !== null && (
        <div className="mt-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Expected Output
          </span>
          <code className="mt-1 block rounded bg-gray-100 px-2 py-1 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-300">
            {JSON.stringify(testCase.expected_output)}
          </code>
        </div>
      )}

      {/* Assertions */}
      {testCase.assertions?.length > 0 && (
        <div className="mt-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Assertions ({testCase.assertions.length})
          </span>
          <div className="mt-1 space-y-1">
            {testCase.assertions.map((assertion, i) => (
              <code
                key={i}
                className="block rounded bg-gray-100 px-2 py-1 text-[11px] text-gray-700 dark:bg-gray-800 dark:text-gray-300"
              >
                {assertion}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function TestSuitePanel() {
  const jobResult = useJobStore((s) => s.result)
  const v1Result  = useGenerationStore((s) => s.result)
  const result    = jobResult ?? v1Result

  // Parse test cases from JSON — memoized to avoid new array on every render
  const testCases = useMemo(() => {
    if (!result?.generated_tests_json) return []
    try {
      const parsed = JSON.parse(result.generated_tests_json)
      return parsed?.test_cases ?? []
    } catch {
      return []
    }
  }, [result?.generated_tests_json])

  // Dynamically compute category statistics
  const categoryStats = useMemo(() => {
    const counts = {}
    testCases.forEach((tc) => {
      const cat = tc.category || 'other'
      counts[cat] = (counts[cat] || 0) + 1
    })
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([category, count]) => ({ category, count }))
  }, [testCases])

  // Empty state
  if (!testCases.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <div className="mb-4 rounded-xl bg-gray-100 p-3 dark:bg-gray-800">
          <svg className="h-8 w-8 text-gray-400 dark:text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No test cases generated</p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          Check the Summary tab for details.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5 overflow-y-auto p-4">
      {/* Test Suite Summary */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Test Suite Summary
          </h3>
          <Badge color="blue">{testCases.length} total</Badge>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {categoryStats.map(({ category, count }) => (
            <CategoryStat key={category} category={category} count={count} />
          ))}
        </div>
      </div>

      {/* Separator */}
      <div className="border-t border-gray-100 dark:border-gray-800" />

      {/* Test Cases */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300">
          Generated Test Cases
        </h3>
        <div className="space-y-3">
          {testCases.map((tc, i) => (
            <TestCaseCard key={tc.name || i} testCase={tc} />
          ))}
        </div>
      </div>
    </div>
  )
}
