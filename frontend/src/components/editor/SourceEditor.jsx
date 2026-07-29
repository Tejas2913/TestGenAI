/**
 * SourceEditor — Monaco-powered Python code editor.
 *
 * Lazy loads Monaco. Falls back to textarea if Monaco fails.
 * Always editable (snapshot model — never read-only during generation).
 * Connected to GenerationStore and synced via useMonaco.
 */
import { lazy, Suspense, useState, useCallback, forwardRef, useImperativeHandle } from 'react'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { useMonaco } from '../../hooks/useMonaco'

const MonacoEditor = lazy(() => import('@monaco-editor/react'))

/** Textarea fallback when Monaco fails or is loading */
function TextareaFallback({ value, onChange, placeholder }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="h-full w-full resize-none rounded-lg border border-gray-200 bg-gray-50 p-3
                 font-mono text-sm text-gray-900 placeholder:text-gray-400
                 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100
                 dark:placeholder:text-gray-500 dark:focus:border-blue-400"
      spellCheck={false}
      aria-label="Python source code editor"
    />
  )
}

/** Loading skeleton while Monaco initializes */
function EditorSkeleton() {
  return (
    <div className="flex h-full items-center justify-center rounded-lg border border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800">
      <div className="flex flex-col items-center gap-2">
        <svg
          className="h-6 w-6 animate-spin text-blue-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        <span className="text-xs text-gray-400 dark:text-gray-500">Loading editor...</span>
      </div>
    </div>
  )
}

const SourceEditor = forwardRef(function SourceEditor({ readOnly = false }, ref) {
  const sourceCode = useGenerationStore((s) => s.sourceCode)
  const language = useGenerationStore((s) => s.language)
  const setSourceCode = useGenerationStore((s) => s.setSourceCode)
  const [monacoFailed, setMonacoFailed] = useState(false)

  const { monacoTheme, editorOptions, handleEditorDidMount: onMount, focusEditor, editorRef } = useMonaco()

  // Expose focusEditor to parent via ref
  useImperativeHandle(ref, () => ({
    focus: focusEditor,
  }))

  const handleEditorDidMount = useCallback(
    (editor) => {
      onMount(editor)
    },
    [onMount]
  )

  const handleChange = useCallback(
    (value) => {
      setSourceCode(value || '')
    },
    [setSourceCode]
  )

  // Character and line counts
  const charCount = sourceCode.length
  const lineCount = sourceCode ? sourceCode.split('\n').length : 0

  // Monaco language mapping
  const monacoLanguage = language === 'python' ? 'python' : 'plaintext'

  return (
    <div className="flex flex-col gap-1.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Source Code
        </label>
        <div className="flex items-center gap-3 text-[11px] text-gray-400 dark:text-gray-500">
          <span>{lineCount} {lineCount === 1 ? 'line' : 'lines'}</span>
          <span>{charCount.toLocaleString()} chars</span>
        </div>
      </div>

      {/* Editor */}
      <div className="h-[300px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 lg:h-[calc(100vh-380px)] lg:min-h-[250px]">
        {monacoFailed ? (
          <TextareaFallback
            value={sourceCode}
            onChange={setSourceCode}
            placeholder="# Paste your Python function here"
          />
        ) : (
          <Suspense fallback={<EditorSkeleton />}>
            <MonacoEditorWrapper
              value={sourceCode}
              language={monacoLanguage}
              theme={monacoTheme}
              options={{ ...editorOptions, readOnly }}
              onChange={handleChange}
              onMount={handleEditorDidMount}
              onError={() => setMonacoFailed(true)}
            />
          </Suspense>
        )}
      </div>
    </div>
  )
})

export default SourceEditor

/**
 * Wrapper to catch Monaco initialization errors gracefully.
 */
function MonacoEditorWrapper({ value, language, theme, options, onChange, onMount, onError }) {
  return (
    <MonacoEditor
      value={value}
      language={language}
      theme={theme}
      options={options}
      onChange={onChange}
      onMount={onMount}
      loading={<EditorSkeleton />}
    />
  )
}
