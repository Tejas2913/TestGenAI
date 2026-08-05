/**
 * TestGen AI v2.2 — QualityCard Component
 *
 * Visualizes overall Quality Score (0-100), rating badge, and sub-score progress indicators.
 */

import React from 'react';
import { QualityMetrics } from '../../types/quality';
import ProgressCard from '../common/ProgressCard';
import StatusBadge from '../common/StatusBadge';

export interface QualityCardProps {
  quality: QualityMetrics | null;
  loading?: boolean;
  error?: Error | null;
}

export const QualityCard: React.FC<QualityCardProps> = ({ quality, loading, error }) => {
  if (loading) {
    return (
      <div className="h-64 animate-pulse rounded-xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-900" />
    );
  }

  if (error || !quality) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Overall Quality</h3>
          <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            NOT EVALUATED
          </span>
        </div>
        <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
          Advanced Quality Evaluation was not enabled for this job.
        </p>
      </div>
    );
  }

  const { overall_score, rating, breakdown } = quality;

  const scoreColor =
    overall_score >= 90 ? 'emerald' : overall_score >= 75 ? 'blue' : overall_score >= 60 ? 'amber' : 'red';

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Overall Quality Score
        </h3>
        <StatusBadge status={rating} variant={rating} />
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-4xl font-extrabold tracking-tight text-gray-900 dark:text-white">
          {Math.round(overall_score)}
        </span>
        <span className="text-sm font-semibold text-gray-400 dark:text-gray-500">/ 100</span>
      </div>

      {breakdown && (
        <div className="space-y-2.5 pt-2 border-t border-gray-100 dark:border-gray-800">
          <ProgressCard
            label="Coverage Score"
            percentage={breakdown.coverage_score || 0}
            color="emerald"
            size="sm"
          />
          <ProgressCard
            label="Mutation Score"
            percentage={breakdown.mutation_score || 0}
            color="blue"
            size="sm"
          />
          <ProgressCard
            label="Smell Hygiene"
            percentage={breakdown.smell_hygiene_score || 0}
            color="purple"
            size="sm"
          />
        </div>
      )}
    </div>
  );
};

export default React.memo(QualityCard);
