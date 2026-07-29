/**
 * SpecEditor — multiline specification textarea.
 *
 * Connected to GenerationStore. Autosaved via useAutosave.
 * Resizable, character counter, placeholder guidance.
 */
import { useCallback } from 'react'
import { useGenerationStore } from '../../stores/useGenerationStore'

const MAX_CHARS = 50_000

export default function SpecEditor() {
  const specification = useGenerationStore((s) => s.specification)
  const setSpecification = useGenerationStore((s) => s.setSpecification)

  const charCount = specification.length
  const isOverLimit = charCount > MAX_CHARS

  const handleChange = useCallback(
    (e) => {
      setSpecification(e.target.value)
    },
    [setSpecification]
  )

  return (
    <div className="flex flex-col gap-1.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <label
          htmlFor="spec-editor"
          className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400"
        >
          Specification
          <span className="ml-1.5 font-normal normal-case tracking-normal text-gray-400 dark:text-gray-500">
            (optional)
          </span>
        </label>
        <span
          className={`text-[11px] ${
            isOverLimit
              ? 'font-medium text-red-500'
              : 'text-gray-400 dark:text-gray-500'
          }`}
        >
          {charCount.toLocaleString()}{isOverLimit ? ` / ${MAX_CHARS.toLocaleString()} max` : ' chars'}
        </span>
      </div>

      {/* Textarea */}
      <textarea
        id="spec-editor"
        value={specification}
        onChange={handleChange}
        placeholder="Describe the expected behavior, edge cases, and testing requirements..."
        rows={3}
        className="w-full resize-y rounded-lg border border-gray-200 bg-white px-3 py-2.5
                   text-sm text-gray-900 placeholder:text-gray-400
                   transition-colors
                   hover:border-gray-300
                   focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none
                   dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100
                   dark:placeholder:text-gray-500
                   dark:hover:border-gray-600 dark:focus:border-blue-400 dark:focus:ring-blue-400"
        style={{ minHeight: '72px', maxHeight: '200px' }}
        spellCheck={false}
        aria-label="Test specification"
      />

      {/* Validation message */}
      {isOverLimit && (
        <p className="text-xs text-red-500" role="alert">
          Specification exceeds {MAX_CHARS.toLocaleString()} character limit.
        </p>
      )}
    </div>
  )
}
