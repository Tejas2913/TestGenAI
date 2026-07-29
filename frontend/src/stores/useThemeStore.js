import { create } from 'zustand'

/**
 * Theme store — manages light/dark mode.
 * Persists to localStorage. Reads prefers-color-scheme on first load.
 */

const getInitialMode = () => {
  const stored = localStorage.getItem('testgen_theme')
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const applyTheme = (mode) => {
  const root = document.documentElement
  if (mode === 'dark') {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
  localStorage.setItem('testgen_theme', mode)
}

export const useThemeStore = create((set) => {
  const initialMode = getInitialMode()
  applyTheme(initialMode)

  return {
    mode: initialMode,

    toggle: () =>
      set((state) => {
        const next = state.mode === 'light' ? 'dark' : 'light'
        applyTheme(next)
        return { mode: next }
      }),
  }
})
