/**
 * useKeyboardShortcuts — global keyboard shortcut bindings.
 *
 * Ctrl+Enter     → generate
 * Ctrl+K         → focus source editor
 * Ctrl+Shift+E   → load example
 * Ctrl+Shift+C   → copy generated code
 * Esc            → close dialogs (handled by individual dialogs)
 * /              → focus history search
 * ?              → open shortcut help
 */
import { useEffect, useCallback } from 'react'

export function useKeyboardShortcuts({
  onGenerate,
  onFocusEditor,
  onLoadExample,
  onCopyCode,
  onFocusSearch,
  onOpenHelp,
}) {
  const handleKeyDown = useCallback(
    (e) => {
      const ctrl = e.ctrlKey || e.metaKey
      const tag = e.target?.tagName

      // Don't intercept when user is typing in an input/textarea (except ctrl combos)
      const inInput = tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable

      // Ctrl+Enter → Generate
      if (ctrl && e.key === 'Enter') {
        e.preventDefault()
        onGenerate?.()
        return
      }

      // Ctrl+K → Focus editor
      if (ctrl && e.key === 'k') {
        e.preventDefault()
        onFocusEditor?.()
        return
      }

      // Ctrl+Shift+E → Load example
      if (ctrl && e.shiftKey && (e.key === 'E' || e.key === 'e')) {
        e.preventDefault()
        onLoadExample?.()
        return
      }

      // Ctrl+Shift+C → Copy generated code
      if (ctrl && e.shiftKey && (e.key === 'C' || e.key === 'c')) {
        e.preventDefault()
        onCopyCode?.()
        return
      }

      // Skip bare key shortcuts when typing in inputs
      if (inInput) return

      // / → focus search
      if (e.key === '/') {
        e.preventDefault()
        onFocusSearch?.()
        return
      }

      // ? → open shortcut help
      if (e.key === '?') {
        e.preventDefault()
        onOpenHelp?.()
        return
      }
    },
    [onGenerate, onFocusEditor, onLoadExample, onCopyCode, onFocusSearch, onOpenHelp]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}
