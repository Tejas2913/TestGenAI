/**
 * ToastContainer — renders queued toasts in the bottom-right corner.
 *
 * Accessible: role="status", aria-live="polite"
 * Respects prefers-reduced-motion for animations.
 */
import { useToastStore } from '../../stores/useToastStore'

const ICONS = {
  success: (
    <svg className="h-4 w-4 shrink-0 text-emerald-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
    </svg>
  ),
  error: (
    <svg className="h-4 w-4 shrink-0 text-red-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
    </svg>
  ),
  warning: (
    <svg className="h-4 w-4 shrink-0 text-amber-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
    </svg>
  ),
  info: (
    <svg className="h-4 w-4 shrink-0 text-blue-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a.75.75 0 000 1.5h.253a.25.25 0 01.244.304l-.459 2.066A1.75 1.75 0 0010.747 15H11a.75.75 0 000-1.5h-.253a.25.25 0 01-.244-.304l.459-2.066A1.75 1.75 0 009.253 9H9z" clipRule="evenodd" />
    </svg>
  ),
}

const BG = {
  success: 'border-emerald-100 dark:border-emerald-900/40',
  error:   'border-red-100 dark:border-red-900/40',
  warning: 'border-amber-100 dark:border-amber-900/40',
  info:    'border-blue-100 dark:border-blue-900/40',
}

function Toast({ id, message, type }) {
  const remove = useToastStore((s) => s.removeToast)

  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex w-80 max-w-[calc(100vw-2rem)] items-start gap-3 rounded-xl border bg-white px-4 py-3 shadow-lg
                  dark:bg-gray-900 motion-safe:animate-slide-up ${BG[type] || BG.info}`}
    >
      {ICONS[type]}
      <p className="flex-1 text-sm text-gray-700 dark:text-gray-200 leading-snug">{message}</p>
      <button
        onClick={() => remove(id)}
        className="shrink-0 rounded p-0.5 text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 cursor-pointer"
        aria-label="Dismiss notification"
      >
        <svg className="h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
        </svg>
      </button>
    </div>
  )
}

export default function ToastContainer() {
  const toasts = useToastStore((s) => s.toasts)
  if (!toasts.length) return null

  return (
    <div
      aria-label="Notifications"
      className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 items-end"
    >
      {toasts.map((t) => (
        <Toast key={t.id} {...t} />
      ))}
    </div>
  )
}
