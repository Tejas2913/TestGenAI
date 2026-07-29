import { create } from 'zustand'

/**
 * Preferences store — persists editor and layout preferences to localStorage.
 */

const STORAGE_KEY = 'testgen_prefs'

const loadPrefs = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const savePrefs = (prefs) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs))
}

const defaults = {
  editorFontSize: 14,
  wordWrap: 'on',
  splitPaneSize: 40,
}

const initial = { ...defaults, ...loadPrefs() }

export const usePreferencesStore = create((set, get) => ({
  editorFontSize: initial.editorFontSize,
  wordWrap: initial.wordWrap,
  splitPaneSize: initial.splitPaneSize,

  setEditorFontSize: (size) => {
    set({ editorFontSize: size })
    savePrefs({ ...get(), editorFontSize: size })
  },

  setWordWrap: (wrap) => {
    set({ wordWrap: wrap })
    savePrefs({ ...get(), wordWrap: wrap })
  },

  setSplitPaneSize: (size) => {
    set({ splitPaneSize: size })
    savePrefs({ ...get(), splitPaneSize: size })
  },
}))
