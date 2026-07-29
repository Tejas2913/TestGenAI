/**
 * Card — bordered container with optional header and padding.
 */
export default function Card({ children, header, className = '', noPadding = false }) {
  return (
    <div
      className={`rounded-xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 ${className}`}
    >
      {header && (
        <div className="border-b border-gray-200 px-4 py-3 dark:border-gray-800">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{header}</h3>
        </div>
      )}
      <div className={noPadding ? '' : 'p-4'}>{children}</div>
    </div>
  )
}
