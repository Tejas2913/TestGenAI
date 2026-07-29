/**
 * WelcomeState — onboarding experience shown when no generation exists.
 *
 * Displays a polished welcome message with a "Paste Example" button
 * that populates the editor with a sample function.
 */
import Button from '../common/Button'
import {
  SAMPLE_SOURCE_CODE,
  SAMPLE_SPECIFICATION,
  SAMPLE_LANGUAGE,
  SAMPLE_FRAMEWORK,
} from '../../utils/sampleFunction'
import { useGenerationStore } from '../../stores/useGenerationStore'

export default function WelcomeState() {
  const setSourceCode = useGenerationStore((s) => s.setSourceCode)
  const setSpecification = useGenerationStore((s) => s.setSpecification)
  const setLanguage = useGenerationStore((s) => s.setLanguage)
  const setFramework = useGenerationStore((s) => s.setFramework)

  const handleLoadExample = () => {
    setSourceCode(SAMPLE_SOURCE_CODE)
    setSpecification(SAMPLE_SPECIFICATION)
    setLanguage(SAMPLE_LANGUAGE)
    setFramework(SAMPLE_FRAMEWORK)
  }

  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      {/* Icon */}
      <div className="mb-6">
        <div className="inline-flex rounded-2xl bg-blue-50 p-4 dark:bg-blue-900/20">
          <svg
            className="h-12 w-12 text-blue-500 dark:text-blue-400"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M14.447 3.027a.75.75 0 01.527.92l-4.5 16.5a.75.75 0 01-1.448-.394l4.5-16.5a.75.75 0 01.921-.526zM16.72 6.22a.75.75 0 011.06 0l5.25 5.25a.75.75 0 010 1.06l-5.25 5.25a.75.75 0 11-1.06-1.06L21.44 12l-4.72-4.72a.75.75 0 010-1.06zM7.28 6.22a.75.75 0 010 1.06L2.56 12l4.72 4.72a.75.75 0 11-1.06 1.06L.97 12.53a.75.75 0 010-1.06l5.25-5.25a.75.75 0 011.06 0z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      </div>

      {/* Title */}
      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
        Welcome to TestGen <span className="text-blue-600 dark:text-blue-400">AI</span>
      </h2>

      {/* Description */}
      <p className="mt-3 max-w-md text-sm leading-relaxed text-gray-500 dark:text-gray-400">
        Generate production-ready unit tests from Python source code
        and natural language specifications.
      </p>

      {/* CTA */}
      <div className="mt-6 flex flex-col items-center gap-3">
        <Button variant="primary" size="lg" onClick={handleLoadExample}>
          Paste Example
        </Button>
        <p className="text-xs text-gray-400 dark:text-gray-500">
          or start typing your own function in the editor.
        </p>
      </div>

      {/* Tip */}
      <div className="mt-8 rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-gray-800 dark:bg-gray-900">
        <p className="text-xs text-gray-500 dark:text-gray-400">
          <span className="font-medium text-gray-600 dark:text-gray-300">Tip:</span>{' '}
          Press{' '}
          <kbd className="mx-0.5 rounded border border-gray-300 bg-white px-1.5 py-0.5 font-mono text-[10px] dark:border-gray-600 dark:bg-gray-800">
            Ctrl+Enter
          </kbd>{' '}
          to generate tests instantly.
        </p>
      </div>
    </div>
  )
}
