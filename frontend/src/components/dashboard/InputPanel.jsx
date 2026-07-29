/**
 * InputPanel — left side of the dashboard.
 *
 * Composes: SourceEditor + SpecEditor + ConfigBar + GenerateButton.
 * Connected to autosave, keyboard shortcuts, and generation (Phase F3).
 */
import { useRef, useCallback, useEffect } from 'react'
import SourceEditor from '../editor/SourceEditor'
import SpecEditor from '../editor/SpecEditor'
import ConfigBar from './ConfigBar'
import GenerateButton from './GenerateButton'
import ErrorAlert from '../common/ErrorAlert'
import { useGenerationStore, selectGeneratedCode } from '../../stores/useGenerationStore'
import { useGenerate } from '../../hooks/useGenerate'
import { useAutosave, loadDraft } from '../../hooks/useAutosave'
import { useKeyboardShortcuts } from '../../hooks/useKeyboardShortcuts'
import { copyToClipboard } from '../../utils/codeActions'
import { toast } from '../../stores/useToastStore'
import {
  SAMPLE_SOURCE_CODE,
  SAMPLE_SPECIFICATION,
  SAMPLE_LANGUAGE,
  SAMPLE_FRAMEWORK,
} from '../../utils/sampleFunction'

export default function InputPanel() {
  const editorRef = useRef(null)

  const setSourceCode = useGenerationStore((s) => s.setSourceCode)
  const setSpecification = useGenerationStore((s) => s.setSpecification)
  const setLanguage = useGenerationStore((s) => s.setLanguage)
  const setFramework = useGenerationStore((s) => s.setFramework)
  const generatedCode = useGenerationStore(selectGeneratedCode)

  // --- Generation hook (Phase F3) ---
  const { generate, error, clearError } = useGenerate()

  // --- Autosave ---
  useAutosave()

  // Restore draft on mount
  useEffect(() => {
    const draft = loadDraft()
    if (draft) {
      if (draft.sourceCode) setSourceCode(draft.sourceCode)
      if (draft.specification) setSpecification(draft.specification)
      if (draft.language) setLanguage(draft.language)
      if (draft.framework) setFramework(draft.framework)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // --- Load example ---
  const handleLoadExample = useCallback(() => {
    setSourceCode(SAMPLE_SOURCE_CODE)
    setSpecification(SAMPLE_SPECIFICATION)
    setLanguage(SAMPLE_LANGUAGE)
    setFramework(SAMPLE_FRAMEWORK)
  }, [setSourceCode, setSpecification, setLanguage, setFramework])

  // --- Focus editor ---
  const handleFocusEditor = useCallback(() => {
    editorRef.current?.focus()
  }, [])

  // --- Copy generated code ---
  const handleCopyCode = useCallback(async () => {
    if (generatedCode) {
      const ok = await copyToClipboard(generatedCode)
      if (ok) toast.success('Code copied to clipboard!')
      else toast.error('Failed to copy to clipboard.')
    }
  }, [generatedCode])

  // --- Keyboard shortcuts ---
  useKeyboardShortcuts({
    onGenerate: generate,
    onFocusEditor: handleFocusEditor,
    onLoadExample: handleLoadExample,
    onCopyCode: handleCopyCode,
  })

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto p-4">
      {/* Error display */}
      {error && (
        <ErrorAlert
          message={error.message}
          onRetry={generate}
          onDismiss={clearError}
        />
      )}

      {/* Source code editor */}
      <div className="flex-1 min-h-0">
        <SourceEditor ref={editorRef} />
      </div>

      {/* Specification */}
      <SpecEditor />

      {/* Config + Generate */}
      <div className="flex items-end justify-between gap-3 pt-1">
        <ConfigBar />
        <GenerateButton onClick={generate} />
      </div>
    </div>
  )
}
