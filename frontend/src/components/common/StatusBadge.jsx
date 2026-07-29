/**
 * StatusBadge — visual status indicator for generation lifecycle.
 */

const STATUS_CONFIG = {
  completed: { label: 'Completed', dot: 'bg-emerald-500', text: 'text-emerald-700 dark:text-emerald-400' },
  processing: { label: 'Processing', dot: 'bg-amber-500 animate-pulse', text: 'text-amber-700 dark:text-amber-400' },
  failed: { label: 'Failed', dot: 'bg-red-500', text: 'text-red-700 dark:text-red-400' },
  pending: { label: 'Pending', dot: 'bg-gray-400', text: 'text-gray-600 dark:text-gray-400' },
}

export default function StatusBadge({ status, className = '' }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending

  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${config.text} ${className}`}>
      <span className={`h-2 w-2 rounded-full ${config.dot}`} aria-hidden="true" />
      {config.label}
    </span>
  )
}
