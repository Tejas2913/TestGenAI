/**
 * TestGen AI v2.2 — QualityDashboard Container Component
 *
 * Responsibilities:
 *   1. Coordinates custom hooks (`useJobPolling` & `useQualityData`).
 *   2. Composes presentation widgets wrapped in `ErrorBoundary` for fault isolation.
 *   3. Handles loading, empty, partial result, and error states gracefully.
 *   4. Contains NO business logic or calculations — pure presentation layer.
 */

import React from 'react';
import useJobPolling from '../../hooks/useJobPolling';
import useQualityData from '../../hooks/useQualityData';

import QualityCard from './QualityCard';
import CoverageCard from './CoverageCard';
import MutationCard from './MutationCard';
import SmellCard from './SmellCard';
import PipelineTimeline from './PipelineTimeline';
import MutationTable from './MutationTable';
import ErrorBoundary from '../common/ErrorBoundary';
import StatusBadge from '../common/StatusBadge';

export interface QualityDashboardProps {
  jobId?: string | null;
}

export const QualityDashboard: React.FC<QualityDashboardProps> = ({ jobId }) => {
  const { job, isPolling, error: pollError } = useJobPolling(jobId);
  const isJobCompleted = job?.status === 'completed' || job?.status === 'partial';

  const {
    quality,
    mutation,
    smells,
    loadingQuality,
    loadingMutation,
    loadingSmells,
    errorQuality,
    errorMutation,
    errorSmells,
  } = useQualityData(jobId, isJobCompleted);

  // Empty state
  if (!jobId) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 p-8 text-center dark:border-gray-800">
        <svg className="h-10 w-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="mt-3 text-sm font-semibold text-gray-900 dark:text-white">No Job Selected</h3>
        <p className="mt-1 text-xs text-gray-500">Submit a generation job or select a job from history to view quality diagnostics.</p>
      </div>
    );
  }

  // Error state for overall polling failure
  if (pollError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center dark:border-red-900/40 dark:bg-red-950/20">
        <h3 className="text-sm font-bold text-red-800 dark:text-red-300">Failed to Load Job Status</h3>
        <p className="mt-1 text-xs text-red-600 dark:text-red-400">{pollError.message}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Job Summary Banner */}
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-gray-900 dark:text-white">
              Job Diagnostics <span className="font-mono text-xs font-normal text-gray-400">#{jobId}</span>
            </h2>
            {job && <StatusBadge status={job.status} variant={job.status.toUpperCase() as any} />}
          </div>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Created: {job?.created_at ? new Date(job.created_at).toLocaleString() : 'N/A'}
          </p>
        </div>

        {isPolling && (
          <div className="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
            <div className="h-2 w-2 animate-ping rounded-full bg-blue-500" />
            Polling pipeline status...
          </div>
        )}
      </div>

      {/* 2. Pipeline Timeline */}
      <ErrorBoundary fallbackTitle="Pipeline Timeline Error">
        <PipelineTimeline job={job} />
      </ErrorBoundary>

      {/* 3. Grid of Metric Cards (Fault Isolated) */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-4">
        <ErrorBoundary fallbackTitle="Quality Card Error">
          <QualityCard quality={quality} loading={loadingQuality} error={errorQuality} />
        </ErrorBoundary>

        <ErrorBoundary fallbackTitle="Coverage Card Error">
          <CoverageCard
            coverage={
              quality?.breakdown
                ? {
                    line_coverage_pct: quality.breakdown.coverage_score,
                    covered_statements: 0,
                    missing_statements: 0,
                    total_statements: 0,
                  }
                : (job?.coverage_line_pct !== undefined && job?.coverage_line_pct !== null)
                ? {
                    line_coverage_pct: job.coverage_line_pct,
                    branch_coverage_pct: job.coverage_branch_pct ?? undefined,
                    covered_statements: job.coverage_covered_statements || 0,
                    missing_statements: job.coverage_missing_statements || 0,
                    total_statements: job.coverage_total_statements || 0,
                  }
                : null
            }
            loading={loadingQuality && !job?.coverage_line_pct}
            error={job?.coverage_line_pct !== undefined && job?.coverage_line_pct !== null ? null : errorQuality}
          />
        </ErrorBoundary>

        <ErrorBoundary fallbackTitle="Mutation Card Error">
          <MutationCard mutation={mutation} loading={loadingMutation} error={errorMutation} />
        </ErrorBoundary>

        <ErrorBoundary fallbackTitle="Smell Card Error">
          <SmellCard smells={smells} loading={loadingSmells} error={errorSmells} />
        </ErrorBoundary>
      </div>

      {/* 4. Mutation Details Table */}
      <ErrorBoundary fallbackTitle="Mutation Table Error">
        <MutationTable mutants={[]} />
      </ErrorBoundary>
    </div>
  );
};

export default React.memo(QualityDashboard);
