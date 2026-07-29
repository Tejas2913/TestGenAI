import { create } from 'zustand'
import { generationService } from '../api/generationService'

/**
 * History store — manages generation history list, pagination, and search.
 *
 * items        — raw items from the backend (current page)
 * parsedCache  — WeakMap caching JSON.parse results per item reference
 * searchQuery  — client-side filter string
 * loadingId    — generation ID currently being opened (row-level loading)
 */

// Module-level cache: parse generated_tests_json only once per item object
const parsedCache = new WeakMap()

/**
 * Parse and cache generated_tests_json for a history item.
 * Returns cached result if already parsed for this exact object reference.
 */
export function getParsedJson(item) {
  if (!item) return null
  if (parsedCache.has(item)) return parsedCache.get(item)

  let parsed = null
  if (item.generated_tests_json) {
    try {
      parsed = JSON.parse(item.generated_tests_json)
    } catch { /* ignore */ }
  }
  parsedCache.set(item, parsed)
  return parsed
}

/**
 * Extract function name from a generation record (uses cache).
 */
export function extractFunctionName(item) {
  const parsed = getParsedJson(item)
  if (parsed?.function_name) return parsed.function_name

  // Fallback: parse first def from source_code
  const match = item.source_code?.match(/def\s+(\w+)/)
  return match ? match[1] : null
}

export const useHistoryStore = create((set, get) => ({
  items: [],
  total: 0,
  page: 1,
  size: 20,
  searchQuery: '',
  isLoading: false,
  error: null,
  loadingId: null,  // Row-level loading indicator

  // --- Actions ---

  /**
   * fetchHistory(page) — fetch a page of generations from the backend.
   */
  fetchHistory: async (page) => {
    const { size } = get()
    const targetPage = page ?? get().page
    set({ isLoading: true, error: null, page: targetPage })

    try {
      const response = await generationService.getGenerations({
        page: targetPage,
        size,
      })

      set({
        items: response.items ?? [],
        total: response.total ?? 0,
        page: response.page ?? targetPage,
        isLoading: false,
      })
    } catch (err) {
      set({
        isLoading: false,
        error: {
          message: err.message || 'Failed to load history.',
          code: err.code || 'UNKNOWN_ERROR',
        },
      })
    }
  },

  /**
   * setPage(page) — change page and refetch.
   */
  setPage: async (page) => {
    set({ page })
    await get().fetchHistory(page)
  },

  /**
   * setSearchQuery(query) — update client-side filter.
   */
  setSearchQuery: (query) => set({ searchQuery: query }),

  /**
   * clearSearch() — reset search filter.
   */
  clearSearch: () => set({ searchQuery: '' }),

  /**
   * refresh() — refetch the current page.
   */
  refresh: async () => {
    await get().fetchHistory(get().page)
  },

  /**
   * setLoadingId(id) — mark a row as loading.
   */
  setLoadingId: (id) => set({ loadingId: id }),
}))

// --- Standalone selectors (reactive, avoid getters) ---

/**
 * selectFilteredItems — client-side search filter.
 * Uses cached parsed JSON for function name extraction.
 */
export const selectFilteredItems = (state) => {
  const { items, searchQuery } = state
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
}

/**
 * selectTotalPages — computed from total and size.
 */
export const selectTotalPages = (state) =>
  Math.max(1, Math.ceil(state.total / state.size))
