/**
 * Badge — colored label for categories, statuses, and metadata.
 */
export default function Badge({ children, color = 'gray', className = '' }) {
  const colors = {
    gray: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    blue: 'bg-blue-50 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    green: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    red: 'bg-red-50 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    amber: 'bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    purple: 'bg-purple-50 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${colors[color] || colors.gray} ${className}`}
    >
      {children}
    </span>
  )
}
