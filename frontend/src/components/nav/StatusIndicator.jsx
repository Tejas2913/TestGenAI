/**
 * StatusIndicator — live backend + LLM status badges.
 * Polls /health every 30s via useBackendStatus.
 * Stops polling when tab is hidden.
 */
import { useBackendStatus } from '../../hooks/useBackendStatus'

function Dot({ ok }) {
  if (ok === null) {
    return <span className="h-2 w-2 rounded-full bg-gray-300 dark:bg-gray-600 animate-pulse" aria-hidden="true" />
  }
  return (
    <span
      className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`}
      aria-hidden="true"
    />
  )
}

export default function StatusIndicator() {
  const { apiConnected, llmReady, version } = useBackendStatus()

  const apiLabel = apiConnected === null ? 'Checking…' : apiConnected ? 'Connected' : 'Disconnected'
  const llmLabel = llmReady === null ? 'Checking…' : llmReady ? 'Ready' : 'Not configured'

  return (
    <div className="hidden items-center gap-2 md:flex" aria-label="Backend status">
      {/* API badge */}
      <span
        className="inline-flex items-center gap-1 rounded-md bg-gray-50 px-2 py-1 text-xs font-medium dark:bg-gray-800"
        title={`API: ${apiLabel}`}
      >
        <Dot ok={apiConnected} />
        <span className="text-gray-600 dark:text-gray-300">API</span>
      </span>

      {/* LLM badge */}
      <span
        className="inline-flex items-center gap-1 rounded-md bg-gray-50 px-2 py-1 text-xs font-medium dark:bg-gray-800"
        title={`LLM: ${llmLabel}`}
      >
        <Dot ok={llmReady} />
        <span className="text-gray-600 dark:text-gray-300">LLM</span>
      </span>

      {/* Prompt version */}
      {version && (
        <span className="rounded-md bg-gray-50 px-2 py-1 text-xs font-medium text-gray-500 dark:bg-gray-800 dark:text-gray-400">
          v{version}
        </span>
      )}
    </div>
  )
}
