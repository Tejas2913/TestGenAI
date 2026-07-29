/**
 * EmptyState — placeholder for empty panels/pages.
 */
export default function EmptyState({ icon, title, description, action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
      {icon && <div className="mb-4 text-gray-300 dark:text-gray-600">{icon}</div>}
      {title && (
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">{title}</h3>
      )}
      {description && (
        <p className="mt-1 max-w-sm text-sm text-gray-500 dark:text-gray-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
