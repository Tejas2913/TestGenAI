/**
 * TestGen AI v2.2 — Custom Hook: useJobPolling
 *
 * Responsibilities:
 *   1. Manages polling interval (2000ms).
 *   2. Listens for terminal state transitions (`completed`, `failed`, `partial`, `cancelled`).
 *   3. Cancels in-flight requests and clears timers on component unmount.
 *   4. Contains NO API aggregation or quality score calculations.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { qualityApi } from '../api/qualityApi';
import { JobSummary } from '../types/quality';

const TERMINAL_STATES = new Set(['completed', 'failed', 'partial', 'cancelled']);
const DEFAULT_POLL_INTERVAL_MS = 2000;

export interface UseJobPollingOptions {
  intervalMs?: number;
  enabled?: boolean;
}

export interface UseJobPollingReturn {
  job: JobSummary | null;
  isPolling: boolean;
  error: Error | null;
  stopPolling: () => void;
  refetch: () => Promise<void>;
}

export function useJobPolling(
  jobId: string | null | undefined,
  options: UseJobPollingOptions = {}
): UseJobPollingReturn {
  const { intervalMs = DEFAULT_POLL_INTERVAL_MS, enabled = true } = options;

  const [job, setJob] = useState<JobSummary | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const isCancelledRef = useRef<boolean>(false);

  const clearPollTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stopPolling = useCallback(() => {
    isCancelledRef.current = true;
    clearPollTimer();
    setIsPolling(false);
  }, [clearPollTimer]);

  const fetchJobStatus = useCallback(async () => {
    if (!jobId || isCancelledRef.current) return;

    try {
      const data = await qualityApi.getJobDetails(jobId);
      if (isCancelledRef.current) return;

      setJob(data);
      setError(null);

      if (TERMINAL_STATES.has(data.status)) {
        setIsPolling(false);
        clearPollTimer();
      } else {
        setIsPolling(true);
        timerRef.current = setTimeout(fetchJobStatus, intervalMs);
      }
    } catch (err: any) {
      if (isCancelledRef.current) return;
      setError(err instanceof Error ? err : new Error(err?.message || 'Polling error'));
      setIsPolling(false);
      clearPollTimer();
    }
  }, [jobId, intervalMs, clearPollTimer]);

  useEffect(() => {
    if (!jobId || !enabled) {
      setIsPolling(false);
      return;
    }

    isCancelledRef.current = false;
    setIsPolling(true);
    fetchJobStatus();

    return () => {
      isCancelledRef.current = true;
      clearPollTimer();
    };
  }, [jobId, enabled, fetchJobStatus, clearPollTimer]);

  return {
    job,
    isPolling,
    error,
    stopPolling,
    refetch: fetchJobStatus,
  };
}

export default useJobPolling;
