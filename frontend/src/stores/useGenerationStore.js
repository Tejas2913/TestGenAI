import { create } from 'zustand'
import { generationService } from '../api/generationService'

/**
 * Generation store — manages the current generation workspace state.
 *
 * Owns: input state, result state, loading/error, and API actions.
 * AbortController ensures only ONE active request at a time.
 */

export const useGenerationStore = create((set, get) => ({
  // Input state
  sourceCode: '',
  specification: '',
  language: 'python',
  framework: 'pytest',

  // Result state
  result: null,
  generationId: null,
  status: null,        // 'pending' | 'processing' | 'completed' | 'failed' | null
  isGenerating: false,
  error: null,

  // UI state
  activeTab: 0,

  // Internal — not exposed to components
  _abortController: null,

  // --- Setters ---

  setSourceCode: (code) => set({ sourceCode: code }),
  setSpecification: (spec) => set({ specification: spec }),
  setLanguage: (lang) => set({ language: lang }),
  setFramework: (fw) => set({ framework: fw }),
  setActiveTab: (index) => set({ activeTab: index }),

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      result: null,
      generationId: null,
      status: null,
      error: null,
      isGenerating: false,
    }),

  // --- API Actions ---

  /**
   * generate(snapshot) — send a generation request to the backend.
   *
   * Lifecycle:
   *   1. Validate snapshot
   *   2. Cancel previous request if still running
   *   3. Set loading state
   *   4. POST /generate
   *   5. Store response
   *   6. Clear loading state
   *
   * @param {Object} snapshot  Frozen editor state at time of click
   * @param {string} snapshot.source_code
   * @param {string} [snapshot.specification]
   * @param {string} snapshot.language
   * @param {string} snapshot.framework
   */
  generate: async (snapshot) => {
    // 1. Validate
    if (!snapshot.source_code?.trim()) {
      set({ error: { message: 'Source code is required.', code: 'VALIDATION_ERROR' } })
      return
    }

    // 2. Cancel any in-flight request
    const prev = get()._abortController
    if (prev) prev.abort()

    // 3. Create new AbortController
    const abortController = new AbortController()

    set({
      isGenerating: true,
      error: null,
      status: 'processing',
      _abortController: abortController,
    })

    try {
      // 4. POST /generate
      const response = await generationService.createGeneration(
        {
          source_code: snapshot.source_code,
          specification: snapshot.specification || null,
          language: snapshot.language,
          framework: snapshot.framework,
        },
        { signal: abortController.signal }
      )

      // 5. Store result
      set({
        result: response,
        generationId: response.id,
        status: response.status,
        isGenerating: false,
        error: null,
        _abortController: null,
      })
    } catch (err) {
      // 6. Handle errors
      if (err.cancelled) {
        // Request was cancelled by a newer request — don't update state
        return
      }

      set({
        isGenerating: false,
        error: {
          message: err.message || 'Generation failed.',
          code: err.code || 'UNKNOWN_ERROR',
        },
        status: 'failed',
        _abortController: null,
      })
    }
  },

  /**
   * loadGeneration(id) — fetch a generation by ID.
   *
   * Used for loading from history (Phase F5) or deep links.
   */
  loadGeneration: async (id) => {
    set({ isGenerating: true, error: null })

    try {
      const response = await generationService.getGeneration(id)

      set({
        result: response,
        generationId: response.id,
        status: response.status,
        sourceCode: response.source_code,
        specification: response.specification || '',
        language: response.language,
        framework: response.framework,
        isGenerating: false,
        error: null,
      })
    } catch (err) {
      set({
        isGenerating: false,
        error: {
          message: err.message || 'Failed to load generation.',
          code: err.code || 'UNKNOWN_ERROR',
        },
      })
    }
  },

  // --- Selectors (computed from result) ---

  get hasResult() {
    return get().result !== null
  },
}))

// Standalone selectors for use with useGenerationStore(selector)
export const selectParsedJson = (state) => {
  if (!state.result?.generated_tests_json) return null
  try {
    return JSON.parse(state.result.generated_tests_json)
  } catch {
    return null
  }
}

export const selectTestCases = (state) => {
  const parsed = selectParsedJson(state)
  return parsed?.test_cases ?? []
}

export const selectGeneratedCode = (state) =>
  state.result?.generated_tests_code ?? null

export const selectTokenUsage = (state) => ({
  input: state.result?.input_tokens ?? null,
  output: state.result?.output_tokens ?? null,
  total: state.result?.total_tokens ?? null,
})

export const selectDurationMs = (state) =>
  state.result?.duration_ms ?? null
