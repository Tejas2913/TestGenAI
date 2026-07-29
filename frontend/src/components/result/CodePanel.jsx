/**
 * CodePanel — read-only Monaco editor for generated pytest code.
 *
 * Features: copy button, download button, theme sync, Python highlighting.
 */
import { lazy, Suspense, useMemo, useState, useCallback } from 'react'
import { useGenerationStore } from '../../stores/useGenerationStore'
import { useJobStore } from '../../stores/useJobStore'
import { useThemeStore } from '../../stores/useThemeStore'
import { usePreferencesStore } from '../../stores/usePreferencesStore'
import { copyToClipboard, downloadFile, buildTestFilename } from '../../utils/codeActions'
import { toast } from '../../stores/useToastStore'

const MonacoEditor = lazy(() => import('@monaco-editor/react'))

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    const ok = await copyToClipboard(text)
    if (ok) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      toast.success('Code copied to clipboard!')
    } else {
      toast.error('Failed to copy to clipboard.')
    }
  }, [text])

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5
                 text-xs font-medium text-gray-600 transition-all
                 hover:bg-gray-50 hover:text-gray-800
                 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300
                 dark:hover:bg-gray-700 dark:hover:text-white cursor-pointer"
      aria-label="Copy generated code"
    >
      {copied ? (
        <>
          <svg className="h-3.5 w-3.5 text-green-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
          </svg>
          Copied!
        </>
      ) : (
        <>
          <svg className="h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
            <path d="M7 3.5A1.5 1.5 0 018.5 2h3.879a1.5 1.5 0 011.06.44l3.122 3.12A1.5 1.5 0 0117 6.622V12.5a1.5 1.5 0 01-1.5 1.5h-1v-3.379a3 3 0 00-.879-2.121L10.5 5.379A3 3 0 008.379 4.5H7v-1z" />
            <path d="M4.5 6A1.5 1.5 0 003 7.5v9A1.5 1.5 0 004.5 18h7a1.5 1.5 0 001.5-1.5v-5.879a1.5 1.5 0 00-.44-1.06L9.44 6.439A1.5 1.5 0 008.378 6H4.5z" />
          </svg>
          Copy
        </>
      )}
    </button>
  )
}

function DownloadButton({ code, functionName }) {
  const handleDownload = useCallback(() => {
    const filename = buildTestFilename(functionName)
    downloadFile(code, filename)
    toast.success(`Downloaded ${filename}`)
  }, [code, functionName])

  return (
    <button
      onClick={handleDownload}
      className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5
                 text-xs font-medium text-gray-600 transition-all
                 hover:bg-gray-50 hover:text-gray-800
                 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300
                 dark:hover:bg-gray-700 dark:hover:text-white cursor-pointer"
      aria-label="Download generated code"
    >
      <svg className="h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
        <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
        <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
      </svg>
      Download
    </button>
  )
}

export default function CodePanel() {
  const jobResult = useJobStore((s) => s.result)
  const v1Result  = useGenerationStore((s) => s.result)
  const result    = jobResult ?? v1Result
  const theme  = useThemeStore((s) => s.mode)
  const fontSize = usePreferencesStore((s) => s.editorFontSize)
  const wordWrap = usePreferencesStore((s) => s.wordWrap)

  const code = result?.generated_tests_code ?? null
  const monacoTheme = theme === 'dark' ? 'vs-dark' : 'vs'

  // Parse function name — memoized
  const functionName = useMemo(() => {
    if (!result?.generated_tests_json) return null
    try {
      return JSON.parse(result.generated_tests_json)?.function_name || null
    } catch {
      return null
    }
  }, [result?.generated_tests_json])

  // Empty state
  if (!code) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <div className="mb-4 rounded-xl bg-gray-100 p-3 dark:bg-gray-800">
          <svg className="h-8 w-8 text-gray-400 dark:text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-500 dark:text-gray-400">No code generated</p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          Check the Summary tab for details.
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-gray-100 px-4 py-2 dark:border-gray-800">
        <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
          {buildTestFilename(functionName)}
        </span>
        <div className="flex items-center gap-2">
          <CopyButton text={code} />
          <DownloadButton code={code} functionName={functionName} />
        </div>
      </div>

      {/* Monaco read-only editor */}
      <div className="flex-1 min-h-0">
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center">
              <span className="text-xs text-gray-400">Loading editor...</span>
            </div>
          }
        >
          <MonacoEditor
            value={code}
            language="python"
            theme={monacoTheme}
            options={{
              readOnly: true,
              domReadOnly: true,
              lineNumbers: 'on',
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap,
              fontSize,
              padding: { top: 12, bottom: 12 },
              renderLineHighlight: 'none',
            }}
          />
        </Suspense>
      </div>
    </div>
  )
}
