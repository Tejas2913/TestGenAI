/**
 * HistoryTable — displays generation history as a semantic table (desktop)
 * or responsive cards (mobile).
 *
 * Uses cached parsed JSON for function name extraction (no repeated JSON.parse).
 * Keyboard-accessible rows with visible focus indicators.
 */
import { memo, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import StatusBadge from '../common/StatusBadge'
import { useHistoryStore, extractFunctionName } from '../../stores/useHistoryStore'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { formatDuration, formatTokens, formatTimestamp } from '../../utils/codeActions'
import { toast } from '../../stores/useToastStore'

/** Placeholder for null values */
function Val({ children }) {
  return children != null && children !== ''
    ? <>{children}</>
    : <span className="text-gray-300 dark:text-gray-600">—</span>
}

/** Single table row — memoized to avoid re-renders */
const HistoryRow = memo(function HistoryRow({ item, isRowLoading, onOpen }) {
  const functionName = extractFunctionName(item)

  const handleClick = useCallback(() => onOpen(item.id), [item.id, onOpen])
  const handleKeyDown = useCallback(
    (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(item.id) } },
    [item.id, onOpen]
  )

  return (
    <tr
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="row"
      aria-label={`Generation ${functionName || item.id?.slice(0, 8)}`}
      className={`cursor-pointer border-b border-gray-50 transition-colors
                   hover:bg-blue-50/50 dark:border-gray-800/50 dark:hover:bg-blue-900/10
                   focus:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500
                   dark:focus:bg-blue-900/20
                   ${isRowLoading ? 'opacity-60' : ''}`}
    >
      {/* Function */}
      <td className="py-3 pl-4 pr-2">
        <div className="flex items-center gap-2">
          {isRowLoading && (
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-200 border-t-blue-500 dark:border-gray-700 dark:border-t-blue-400" />
          )}
          <span className="text-sm font-medium text-gray-900 dark:text-white truncate max-w-[160px]" title={functionName}>
            <Val>{functionName}</Val>
          </span>
        </div>
      </td>

      {/* Created */}
      <td className="py-3 px-2 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
        <Val>{formatTimestamp(item.created_at)}</Val>
      </td>

      {/* Status */}
      <td className="py-3 px-2">
        <StatusBadge status={item.status} />
      </td>

      {/* Prompt Version — hidden on tablet */}
      <td className="hidden py-3 px-2 text-xs text-gray-500 dark:text-gray-400 xl:table-cell">
        <Val>{item.prompt_version}</Val>
      </td>

      {/* Input Tokens — hidden on tablet */}
      <td className="hidden py-3 px-2 text-xs text-gray-500 dark:text-gray-400 text-right xl:table-cell">
        <Val>{formatTokens(item.input_tokens)}</Val>
      </td>

      {/* Output Tokens — hidden on tablet */}
      <td className="hidden py-3 px-2 text-xs text-gray-500 dark:text-gray-400 text-right xl:table-cell">
        <Val>{formatTokens(item.output_tokens)}</Val>
      </td>

      {/* Total Tokens */}
      <td className="hidden py-3 px-2 text-xs text-gray-500 dark:text-gray-400 text-right lg:table-cell">
        <Val>{formatTokens(item.total_tokens)}</Val>
      </td>

      {/* Duration */}
      <td className="py-3 px-2 text-xs text-gray-500 dark:text-gray-400 text-right">
        <Val>{formatDuration(item.duration_ms)}</Val>
      </td>

      {/* Language — hidden on tablet */}
      <td className="hidden py-3 px-2 text-xs text-gray-500 dark:text-gray-400 xl:table-cell">
        <Val>{item.language}</Val>
      </td>

      {/* Framework — hidden on tablet */}
      <td className="hidden py-3 px-2 pr-4 text-xs text-gray-500 dark:text-gray-400 xl:table-cell">
        <Val>{item.framework}</Val>
      </td>
    </tr>
  )
})

/** Mobile card — shown on small screens */
const HistoryCard = memo(function HistoryCard({ item, isRowLoading, onOpen }) {
  const functionName = extractFunctionName(item)

  return (
    <button
      onClick={() => onOpen(item.id)}
      className={`w-full text-left rounded-lg border border-gray-100 bg-white p-4 transition-colors
                   hover:border-gray-200 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700
                   focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer
                   ${isRowLoading ? 'opacity-60' : ''}`}
      aria-label={`Open generation ${functionName || item.id?.slice(0, 8)}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 dark:text-white truncate">
            {functionName || <span className="text-gray-400 italic">Unnamed</span>}
          </p>
          <p className="mt-0.5 text-xs text-gray-400 dark:text-gray-500">
            <Val>{formatTimestamp(item.created_at)}</Val>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isRowLoading && (
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-gray-200 border-t-blue-500" />
          )}
          <StatusBadge status={item.status} />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-gray-400 dark:text-gray-500">
        <span>Duration: <Val>{formatDuration(item.duration_ms)}</Val></span>
        <span>Tokens: <Val>{formatTokens(item.total_tokens)}</Val></span>
        <span>{item.language} / {item.framework}</span>
      </div>
    </button>
  )
})

/** Skeleton rows for loading state */
function SkeletonRows({ count = 5 }) {
  return Array.from({ length: count }, (_, i) => (
    <tr key={i} className="border-b border-gray-50 dark:border-gray-800/50 animate-pulse">
      {Array.from({ length: 10 }, (_, j) => (
        <td key={j} className={`py-3 px-2 ${j >= 3 && j <= 5 ? 'hidden xl:table-cell' : j === 6 ? 'hidden lg:table-cell' : j >= 8 ? 'hidden xl:table-cell' : ''}`}>
          <div className="h-3 rounded bg-gray-100 dark:bg-gray-800" style={{ width: `${40 + Math.random() * 40}%` }} />
        </td>
      ))}
    </tr>
  ))
}

export default function HistoryTable() {
  const items = useHistoryStore((s) => s.items)
  const isLoading = useHistoryStore((s) => s.isLoading)
  const loadingId = useHistoryStore((s) => s.loadingId)
  const searchQuery = useHistoryStore((s) => s.searchQuery)

  // Compute filtered items with useMemo — avoids infinite re-render from selector
  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items
    const q = searchQuery.toLowerCase()
    return items.filter((item) => {
      const fn = (extractFunctionName(item) || '').toLowerCase()
      return (
        fn.includes(q) ||
        item.status?.toLowerCase().includes(q) ||
        item.prompt_version?.toLowerCase().includes(q) ||
        item.language?.toLowerCase().includes(q) ||
        item.framework?.toLowerCase().includes(q)
      )
    })
  }, [items, searchQuery])
  const setLoadingId = useHistoryStore((s) => s.setLoadingId)
  const loadGeneration = useGenerationStore((s) => s.loadGeneration)
  const navigate = useNavigate()

  const handleOpen = useCallback(async (id) => {
    setLoadingId(id)
    try {
      await loadGeneration(id)
      toast.info('Generation restored.')
      navigate('/')
    } catch {
      toast.error('Failed to restore generation.')
    } finally {
      setLoadingId(null)
    }
  }, [loadGeneration, navigate, setLoadingId])

  // Loading skeleton
  if (isLoading) {
    return (
      <>
        {/* Desktop skeleton */}
        <div className="hidden lg:block">
          <table className="w-full" role="table">
            <thead><tr><th colSpan={10} /></tr></thead>
            <tbody><SkeletonRows count={5} /></tbody>
          </table>
        </div>
        {/* Mobile skeleton */}
        <div className="space-y-3 lg:hidden">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="animate-pulse rounded-lg border border-gray-100 bg-white p-4 dark:border-gray-800 dark:bg-gray-900">
              <div className="h-4 w-32 rounded bg-gray-100 dark:bg-gray-800" />
              <div className="mt-2 h-3 w-48 rounded bg-gray-100 dark:bg-gray-800" />
            </div>
          ))}
        </div>
      </>
    )
  }

  // Empty: no search results
  if (searchQuery && filteredItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-3 rounded-xl bg-gray-100 p-3 dark:bg-gray-800">
          <svg className="h-8 w-8 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No matching generations</p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          Try a different search term or clear the filter.
        </p>
      </div>
    )
  }

  // Empty: no history at all
  if (filteredItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="mb-3 rounded-xl bg-gray-100 p-3 dark:bg-gray-800">
          <svg className="h-8 w-8 text-gray-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No generations yet</p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          Create your first test suite from the Dashboard.
        </p>
      </div>
    )
  }

  return (
    <>
      {/* Desktop: semantic table */}
      <div className="hidden lg:block overflow-x-auto">
        <table className="w-full" role="table" aria-label="Generation history">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              {[
                { label: 'Function', cls: 'pl-4 text-left' },
                { label: 'Created', cls: 'text-left' },
                { label: 'Status', cls: 'text-left' },
                { label: 'Prompt', cls: 'text-left hidden xl:table-cell' },
                { label: 'In Tokens', cls: 'text-right hidden xl:table-cell' },
                { label: 'Out Tokens', cls: 'text-right hidden xl:table-cell' },
                { label: 'Tokens', cls: 'text-right hidden lg:table-cell' },
                { label: 'Duration', cls: 'text-right' },
                { label: 'Language', cls: 'text-left hidden xl:table-cell' },
                { label: 'Framework', cls: 'text-left hidden xl:table-cell pr-4' },
              ].map(({ label, cls }) => (
                <th
                  key={label}
                  className={`py-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 ${cls}`}
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => (
              <HistoryRow
                key={item.id}
                item={item}
                isRowLoading={loadingId === item.id}
                onOpen={handleOpen}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Mobile: cards */}
      <div className="space-y-2 lg:hidden">
        {filteredItems.map((item) => (
          <HistoryCard
            key={item.id}
            item={item}
            isRowLoading={loadingId === item.id}
            onOpen={handleOpen}
          />
        ))}
      </div>
    </>
  )
}
