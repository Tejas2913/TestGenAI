/**
 * GenerateButton — submit button with loading state and keyboard shortcut hint.
 *
 * Disabled when source code is empty or already generating.
 * Click handler is a placeholder — backend integration in Phase F3.
 */
import { useGenerationStore } from '../../stores/useGenerationStore'
import Button from '../common/Button'
import Tooltip from '../common/Tooltip'

export default function GenerateButton({ onClick }) {
  const sourceCode = useGenerationStore((s) => s.sourceCode)
  const isGenerating = useGenerationStore((s) => s.isGenerating)

  const isEmpty = !sourceCode.trim()
  const isDisabled = isEmpty || isGenerating

  return (
    <div className="flex flex-col items-start gap-1">
      <Tooltip text={isEmpty ? 'Paste source code first' : 'Generate tests (Ctrl+Enter)'}>
        <Button
          variant="primary"
          size="md"
          onClick={onClick}
          disabled={isDisabled}
          isLoading={isGenerating}
          className="min-w-[160px]"
          aria-label="Generate tests"
        >
          {isGenerating ? 'Generating...' : '▶ Generate Tests'}
        </Button>
      </Tooltip>
      <span className="text-[10px] text-gray-400 dark:text-gray-500">
        <kbd className="rounded border border-gray-200 bg-gray-50 px-1 py-0.5 font-mono dark:border-gray-700 dark:bg-gray-800">
          Ctrl+Enter
        </kbd>
      </span>
    </div>
  )
}
