/**
 * useBackendStatus — polls /health every 30s.
 * Stops when tab is hidden, resumes when visible.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import client from '../api/client'

const POLL_INTERVAL = 30_000

export function useBackendStatus() {
  const [apiConnected, setApiConnected] = useState(null)   // null = unknown
  const [llmReady, setLlmReady]         = useState(null)
  const [version, setVersion]           = useState(null)
  const timerRef = useRef(null)

  const check = useCallback(async () => {
    try {
      const data = await client.get('/health')
      setApiConnected(data.database !== false)
      setLlmReady(data.llm_provider === true)
      setVersion(data.version ?? null)
    } catch {
      setApiConnected(false)
      setLlmReady(false)
    }
  }, [])

  useEffect(() => {
    // Initial check
    check()

    const start = () => {
      timerRef.current = setInterval(check, POLL_INTERVAL)
    }
    const stop = () => {
      clearInterval(timerRef.current)
    }

    const onVisibility = () => {
      if (document.hidden) {
        stop()
      } else {
        check()
        start()
      }
    }

    start()
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      stop()
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [check])

  return { apiConnected, llmReady, version }
}
