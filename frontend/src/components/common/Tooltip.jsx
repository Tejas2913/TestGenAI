import { useState } from 'react'

/**
 * Tooltip — hover tooltip positioned above the trigger element.
 */
export default function Tooltip({ children, text, className = '' }) {
  const [visible, setVisible] = useState(false)

  return (
    <div
      className={`relative inline-flex ${className}`}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2
                     whitespace-nowrap rounded-md bg-gray-900 px-2.5 py-1
                     text-xs font-medium text-white shadow-lg
                     dark:bg-gray-100 dark:text-gray-900
                     animate-fade-in"
        >
          {text}
          <div
            className="absolute top-full left-1/2 -translate-x-1/2
                       border-4 border-transparent border-t-gray-900
                       dark:border-t-gray-100"
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  )
}
