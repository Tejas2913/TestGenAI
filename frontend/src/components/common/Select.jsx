/**
 * Select — styled dropdown with label.
 */
export default function Select({
  label,
  value,
  onChange,
  options = [],
  disabled = false,
  id,
  className = '',
}) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      {label && (
        <label
          htmlFor={id}
          className="text-xs font-medium text-gray-500 dark:text-gray-400"
        >
          {label}
        </label>
      )}
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-900
                   transition-colors
                   hover:border-gray-300
                   focus:border-blue-500 focus:ring-1 focus:ring-blue-500
                   disabled:opacity-50 disabled:cursor-not-allowed
                   dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100
                   dark:hover:border-gray-600 dark:focus:border-blue-400 dark:focus:ring-blue-400"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
