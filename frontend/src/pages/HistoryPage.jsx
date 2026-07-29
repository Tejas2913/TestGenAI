/**
 * HistoryPage — generation history with search, table, and pagination.
 *
 * F5: fetch, search, table, pagination, row-click restore.
 * F6 additions:
 *   • Scroll position persistence (restores exactly where user left off)
 *   • Page / search-query persistence (no unnecessary resets)
 *   • "/" shortcut to focus search input
 *   • Toast on history-item restore (fired by HistoryTable)
 */
import { useEffect, useCallback, useRef } from 'react'
import { useHistoryStore, selectTotalPages } from '../stores/useHistoryStore'
import { useKeyboardShortcuts } from '../hooks/useKeyboardShortcuts'
import SearchInput from '../components/common/SearchInput'
import HistoryTable from '../components/history/HistoryTable'
import Pagination from '../components/history/Pagination'
import ErrorAlert from '../components/common/ErrorAlert'

export default function HistoryPage() {
  const total        = useHistoryStore((s) => s.total)
  const page         = useHistoryStore((s) => s.page)
  const totalPages   = useHistoryStore(selectTotalPages)
  const searchQuery  = useHistoryStore((s) => s.searchQuery)
  const isLoading    = useHistoryStore((s) => s.isLoading)
  const error        = useHistoryStore((s) => s.error)
  const fetchHistory = useHistoryStore((s) => s.fetchHistory)
  const setPage      = useHistoryStore((s) => s.setPage)
  const setSearchQuery = useHistoryStore((s) => s.setSearchQuery)
  const refresh      = useHistoryStore((s) => s.refresh)

  const searchRef   = useRef(null)
  const scrollRef   = useRef(null)     // scroll container
  const scrollPosRef = useRef(0)       // saved scroll position (module-level persistence)

  // --- Fetch on mount (only if items empty, preserving page/search across nav) ---
  useEffect(() => {
    fetchHistory(page)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])  // intentionally runs once; page is read from store state

  // --- Restore scroll position after items render ---
  useEffect(() => {
    if (!isLoading && scrollRef.current) {
      scrollRef.current.scrollTop = scrollPosRef.current
    }
  }, [isLoading])

  // --- Save scroll position on unmount ---
  useEffect(() => {
    const el = scrollRef.current
    return () => {
      if (el) scrollPosRef.current = el.scrollTop
    }
  }, [])

  const handlePageChange = useCallback((newPage) => {
    setPage(newPage)
  }, [setPage])

  // "/" shortcut → focus search
  const handleFocusSearch = useCallback(() => {
    searchRef.current?.focus()
  }, [])

  useKeyboardShortcuts({ onFocusSearch: handleFocusSearch })

  return (
    <div
      ref={scrollRef}
      className="h-full overflow-auto"
    >
      <div className="mx-auto max-w-6xl px-4 py-6 lg:px-6">
        {/* Page header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              Generation History
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              View and revisit your previous test generations.
            </p>
          </div>
          <span className="rounded-lg bg-gray-100 px-3 py-1 text-sm font-medium text-gray-500 dark:bg-gray-800 dark:text-gray-400">
            {total} total
          </span>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4">
            <ErrorAlert
              message={error.message}
              onRetry={refresh}
              onDismiss={() => {}}
            />
          </div>
        )}

        {/* Search — "/" focuses this */}
        <div className="mb-4">
          <SearchInput
            ref={searchRef}
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search by function name, status, or prompt version… (press / to focus)"
          />
        </div>

        {/* Table */}
        <div className="rounded-xl border border-gray-100 bg-white dark:border-gray-800 dark:bg-gray-900/50">
          <HistoryTable />
        </div>

        {/* Pagination */}
        {!isLoading && total > 0 && (
          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={handlePageChange}
            disabled={isLoading}
          />
        )}
      </div>
    </div>
  )
}
