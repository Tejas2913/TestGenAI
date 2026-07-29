/**
 * SearchInput — text input with search icon and clear button.
 * Forwards ref to the internal <input> for programmatic focus (e.g. "/" shortcut).
 */
import { forwardRef } from 'react'

const SearchInput = forwardRef(function SearchInput(
  { value, onChange, placeholder = 'Search...', className = '' },
  ref
) {
  return (
    <div className={`relative ${className}`}>
      {/* Search icon */}
      <svg
        className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
          clipRule="evenodd"
        />
      </svg>

      <input
        ref={ref}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-gray-200 bg-white py-2 pl-9 pr-9 text-sm
                   text-gray-900 placeholder:text-gray-400
                   transition-colors
                   hover:border-gray-300
                   focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                   dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100
                   dark:placeholder:text-gray-500
                   dark:hover:border-gray-600 dark:focus:border-blue-400 dark:focus:ring-blue-400"
        aria-label={placeholder}
      />

      {/* Clear button */}
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5
                     text-gray-400 hover:text-gray-600
                     dark:text-gray-500 dark:hover:text-gray-300 cursor-pointer"
          aria-label="Clear search"
        >
          <svg className="h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      )}
    </div>
  )
})

export default SearchInput
