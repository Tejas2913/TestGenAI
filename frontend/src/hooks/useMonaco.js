/**
 * useMonaco — manages Monaco Editor theme sync, preference sync, and ref access.
 *
 * Returns configuration object and editorRef for external focus control.
 */
import { useRef, useMemo } from 'react'
import { useThemeStore } from '../stores/useThemeStore'
import { usePreferencesStore } from '../stores/usePreferencesStore'

export function useMonaco() {
  const editorRef = useRef(null)
  const theme = useThemeStore((s) => s.mode)
  const fontSize = usePreferencesStore((s) => s.editorFontSize)
  const wordWrap = usePreferencesStore((s) => s.wordWrap)

  const monacoTheme = theme === 'dark' ? 'vs-dark' : 'vs'

  const editorOptions = useMemo(
    () => ({
      fontSize,
      wordWrap,
      lineNumbers: 'on',
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      automaticLayout: true,
      tabSize: 4,
      renderLineHighlight: 'line',
      smoothScrolling: true,
      cursorSmoothCaretAnimation: 'on',
      padding: { top: 12, bottom: 12 },
      folding: true,
      bracketPairColorization: { enabled: true },
      guides: { indentation: true },
    }),
    [fontSize, wordWrap]
  )

  /** Store editor instance on mount for programmatic access (e.g. focus) */
  const handleEditorDidMount = (editor) => {
    editorRef.current = editor
  }

  /** Focus the editor programmatically */
  const focusEditor = () => {
    editorRef.current?.focus()
  }

  return {
    editorRef,
    monacoTheme,
    editorOptions,
    handleEditorDidMount,
    focusEditor,
  }
}
