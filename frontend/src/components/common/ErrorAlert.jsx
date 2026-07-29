/**
 * ErrorAlert — dismissible error banner.
 */
import { useState } from 'react'

export default function ErrorAlert({ message, onRetry, onDismiss, className = '' }) {
  const [dismissed, setDismissed] = useState(false)

  if (dismissed) return null

  const handleDismiss = () => {
    setDismissed(true)
    onDismiss?.()
  }

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4
                  dark:border-red-800/50 dark:bg-red-900/20 ${className}`}
    >
      {/* Icon */}
      <svg
        className="mt-0.5 h-5 w-5 shrink-0 text-red-500"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
          clipRule="evenodd"
        />
      </svg>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm text-red-800 dark:text-red-200">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 text-sm font-medium text-red-700 underline hover:text-red-800
                       dark:text-red-300 dark:hover:text-red-200 cursor-pointer"
          >
            Try again
          </button>
        )}
      </div>

      {/* Dismiss */}
      <button
        onClick={handleDismiss}
        className="shrink-0 rounded p-0.5 text-red-400 hover:text-red-600
                   dark:text-red-500 dark:hover:text-red-300 cursor-pointer"
        aria-label="Dismiss error"
      >
        <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
        </svg>
      </button>
    </div>
  )
}
