/**
 * DashboardPage — main workspace page.
 *
 * Desktop: SplitPane with InputPanel (left) and ResultPanel (right).
 * Mobile: stacked layout.
 *
 * Phase 5: isGenerating now driven by useJobStore (async job state)
 * rather than useGenerationStore. The welcome state is shown only
 * when the editor is empty, no job is in flight, and no result exists.
 */
import SplitPane from '../components/common/SplitPane'
import InputPanel from '../components/dashboard/InputPanel'
import WelcomeState from '../components/dashboard/WelcomeState'
import ResultPanel from '../components/result/ResultPanel'
import { useGenerationStore } from '../stores/useGenerationStore'
import { useJobStore, selectIsActive } from '../stores/useJobStore'

export default function DashboardPage() {
  // Source code from editor store (controls welcome state)
  const sourceCode = useGenerationStore((s) => s.sourceCode)

  // Job store drives the result and active states
  const jobResult = useJobStore((s) => s.result)
  const isActive  = useJobStore(selectIsActive)

  // Legacy V1 result (history / deep link)
  const v1Result = useGenerationStore((s) => s.result)

  const hasResult = !!(jobResult ?? v1Result)

  // Show welcome state only when the editor is empty and nothing is running
  const showWelcome = !hasResult && !isActive && !sourceCode.trim()

  const rightPanel = showWelcome ? <WelcomeState /> : <ResultPanel />

  return (
    <div className="h-full">
      {/* Desktop: split pane */}
      <div className="hidden h-full lg:block">
        <SplitPane
          left={<InputPanel />}
          right={rightPanel}
        />
      </div>

      {/* Mobile/Tablet: stacked layout */}
      <div className="flex h-full flex-col overflow-auto lg:hidden">
        <InputPanel />
        <div className="min-h-[300px] border-t border-gray-200 dark:border-gray-800">
          {rightPanel}
        </div>
      </div>
    </div>
  )
}
