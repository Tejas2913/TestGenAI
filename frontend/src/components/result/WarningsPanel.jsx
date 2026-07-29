/**
 * WarningsPanel — displays validation warnings, errors, or success state.
 *
 * Since validation_warnings are not persisted in the DB, this panel:
 * 1. Shows error_message for failed generations
 * 2. Shows success state when generation completed without issues
 */
import { useGenerationStore } from '../../stores/useGenerationStore'
import { useJobStore } from '../../stores/useJobStore'

export default function WarningsPanel() {
  const jobResult = useJobStore((s) => s.result)
  const v1Result  = useGenerationStore((s) => s.result)
  const result    = jobResult ?? v1Result

  if (!result) return null

  const isFailed = result.status === 'failed'
  const errorMessage = result.error_message

  // Failed generation with error message
  if (isFailed && errorMessage) {
    return (
      <div className="flex flex-col gap-4 overflow-y-auto p-4">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800/50 dark:bg-red-900/20">
          <div className="flex items-start gap-3">
            <svg
              className="mt-0.5 h-5 w-5 shrink-0 text-red-500"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <h4 className="text-sm font-semibold text-red-800 dark:text-red-200">
                Generation Failed
              </h4>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                {errorMessage}
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Failed without specific error
  if (isFailed) {
    return (
      <div className="flex flex-col gap-4 overflow-y-auto p-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800/50 dark:bg-amber-900/20">
          <div className="flex items-start gap-3">
            <svg
              className="mt-0.5 h-5 w-5 shrink-0 text-amber-500"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
                clipRule="evenodd"
              />
            </svg>
            <div>
              <h4 className="text-sm font-semibold text-amber-800 dark:text-amber-200">
                Generation Incomplete
              </h4>
              <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                The generation did not complete successfully. Please try again.
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Success state — no warnings
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 inline-flex rounded-2xl bg-green-50 p-4 dark:bg-green-900/20">
        <svg
          className="h-10 w-10 text-green-500 dark:text-green-400"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z"
            clipRule="evenodd"
          />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-gray-900 dark:text-white">
        All checks passed
      </h3>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        No validation warnings or errors detected.
      </p>
    </div>
  )
}
