/**
 * useAutosave — debounced localStorage persistence for editor drafts.
 *
 * Subscribes to generation store changes and saves drafts after a 1.5s debounce.
 * Restores drafts on app load. Never sends anything to the backend.
 */
import { useEffect, useRef } from 'react'
import { useGenerationStore } from '../stores/useGenerationStore'

const STORAGE_KEY = 'testgen_draft'
const DEBOUNCE_MS = 1500

/** Load saved draft from localStorage */
export function loadDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

/** Save draft to localStorage */
function saveDraft(draft) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      ...draft,
      savedAt: new Date().toISOString(),
    }))
  } catch {
    // localStorage full or unavailable — silently fail
  }
}

export function useAutosave() {
  const timerRef = useRef(null)

  useEffect(() => {
    // Subscribe to store changes (Zustand subscribe returns unsubscribe fn)
    const unsubscribe = useGenerationStore.subscribe(
      (state) => ({
        sourceCode: state.sourceCode,
        specification: state.specification,
        language: state.language,
        framework: state.framework,
      }),
      (draft) => {
        // Clear previous debounce timer
        if (timerRef.current) clearTimeout(timerRef.current)

        // Debounce the save
        timerRef.current = setTimeout(() => {
          saveDraft(draft)
        }, DEBOUNCE_MS)
      },
      { equalityFn: (a, b) =>
          a.sourceCode === b.sourceCode &&
          a.specification === b.specification &&
          a.language === b.language &&
          a.framework === b.framework
      }
    )

    return () => {
      unsubscribe()
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])
}
