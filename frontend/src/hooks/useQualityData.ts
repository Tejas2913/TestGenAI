/**
 * TestGen AI v2.2 — Custom Hook: useQualityData
 *
 * Responsibilities:
 *   1. Fetches quality evaluation sub-resource endpoints (`/quality`, `/mutation-summary`, `/smells`).
 *   2. Maintains independent fault-isolated loading and error states for each card.
 *   3. Exposes typed quality metrics data to presentation components.
 *   4. Contains NO polling logic.
 */

import { useEffect, useState, useCallback } from 'react';
import { qualityApi } from '../api/qualityApi';
import {
  QualityMetrics,
  MutationSummary,
  TestSmellSummary,
} from '../types/quality';

export interface UseQualityDataReturn {
  quality: QualityMetrics | null;
  mutation: MutationSummary | null;
  smells: TestSmellSummary | null;
  loadingQuality: boolean;
  loadingMutation: boolean;
  loadingSmells: boolean;
  errorQuality: Error | null;
  errorMutation: Error | null;
  errorSmells: Error | null;
  refetchAll: () => Promise<void>;
}

export function useQualityData(
  jobId: string | null | undefined,
  isJobCompleted: boolean = false
): UseQualityDataReturn {
  const [quality, setQuality] = useState<QualityMetrics | null>(null);
  const [mutation, setMutation] = useState<MutationSummary | null>(null);
  const [smells, setSmells] = useState<TestSmellSummary | null>(null);

  const [loadingQuality, setLoadingQuality] = useState<boolean>(false);
  const [loadingMutation, setLoadingMutation] = useState<boolean>(false);
  const [loadingSmells, setLoadingSmells] = useState<boolean>(false);

  const [errorQuality, setErrorQuality] = useState<Error | null>(null);
  const [errorMutation, setErrorMutation] = useState<Error | null>(null);
  const [errorSmells, setErrorSmells] = useState<Error | null>(null);

  const fetchQuality = useCallback(async (id: string) => {
    setLoadingQuality(true);
    setErrorQuality(null);
    try {
      const data = await qualityApi.getJobQuality(id);
      setQuality(data);
    } catch (err: any) {
      setErrorQuality(err instanceof Error ? err : new Error('Failed to load quality metrics'));
    } finally {
      setLoadingQuality(false);
    }
  }, []);

  const fetchMutation = useCallback(async (id: string) => {
    setLoadingMutation(true);
    setErrorMutation(null);
    try {
      const data = await qualityApi.getJobMutationSummary(id);
      setMutation(data);
    } catch (err: any) {
      setErrorMutation(err instanceof Error ? err : new Error('Failed to load mutation summary'));
    } finally {
      setLoadingMutation(false);
    }
  }, []);

  const fetchSmells = useCallback(async (id: string) => {
    setLoadingSmells(true);
    setErrorSmells(null);
    try {
      const data = await qualityApi.getJobSmells(id);
      setSmells(data);
    } catch (err: any) {
      setErrorSmells(err instanceof Error ? err : new Error('Failed to load test smell diagnostic summary'));
    } finally {
      setLoadingSmells(false);
    }
  }, []);

  const fetchAll = useCallback(async () => {
    if (!jobId) return;
    // Fault isolation: fetch endpoints concurrently without failing all if one errors
    await Promise.allSettled([
      fetchQuality(jobId),
      fetchMutation(jobId),
      fetchSmells(jobId),
    ]);
  }, [jobId, fetchQuality, fetchMutation, fetchSmells]);

  useEffect(() => {
    if (jobId && isJobCompleted) {
      fetchAll();
    }
  }, [jobId, isJobCompleted, fetchAll]);

  return {
    quality,
    mutation: mutation ?? quality?.mutation ?? null,
    smells: smells ?? quality?.smells ?? null,
    loadingQuality,
    loadingMutation,
    loadingSmells,
    errorQuality,
    errorMutation,
    errorSmells,
    refetchAll: fetchAll,
  };
}

export default useQualityData;
