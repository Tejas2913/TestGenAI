/**
 * Pagination — Previous / Next controls with "Page X of Y" display.
 *
 * Disables buttons at boundaries. Preserves search query when changing pages.
 */

export default function Pagination({ page, totalPages, onPageChange, disabled = false }) {
  if (totalPages <= 1) return null

  const canPrev = page > 1 && !disabled
  const canNext = page < totalPages && !disabled

  return (
    <div className="flex items-center justify-between border-t border-gray-100 px-1 pt-4 dark:border-gray-800">
      <button
        onClick={() => canPrev && onPageChange(page - 1)}
        disabled={!canPrev}
        className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors
                   text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800
                   disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent
                   dark:disabled:hover:bg-transparent cursor-pointer"
        aria-label="Previous page"
      >
        <svg className="h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M12.79 5.23a.75.75 0 01-.02 1.06L8.832 10l3.938 3.71a.75.75 0 11-1.04 1.08l-4.5-4.25a.75.75 0 010-1.08l4.5-4.25a.75.75 0 011.06.02z" clipRule="evenodd" />
        </svg>
        Previous
      </button>

      <span className="text-xs text-gray-500 dark:text-gray-400">
        Page {page} of {totalPages}
      </span>

      <button
        onClick={() => canNext && onPageChange(page + 1)}
        disabled={!canNext}
        className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors
                   text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800
                   disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent
                   dark:disabled:hover:bg-transparent cursor-pointer"
        aria-label="Next page"
      >
        Next
        <svg className="h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clipRule="evenodd" />
        </svg>
      </button>
    </div>
  )
}
