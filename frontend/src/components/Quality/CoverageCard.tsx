/**
 * TestGen AI v2.2 — CoverageCard Component
 *
 * Displays Line Coverage %, Branch Coverage %, and statement breakdown counters.
 */

import React from 'react';
import { CoverageMetrics } from '../../types/quality';
import ProgressCard from '../common/ProgressCard';

export interface CoverageCardProps {
  coverage: CoverageMetrics | null;
  loading?: boolean;
  error?: Error | null;
}

export const CoverageCard: React.FC<CoverageCardProps> = ({ coverage, loading, error }) => {
  if (loading) {
    return (
      <div className="h-64 animate-pulse rounded-xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-900" />
    );
  }

  if (error || !coverage) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Coverage Analysis</h3>
        <p className="mt-3 text-xs text-gray-400">Coverage data not available.</p>
      </div>
    );
  }

  const { line_coverage_pct, branch_coverage_pct, covered_statements, missing_statements, total_statements } = coverage;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Coverage Analysis
        </h3>
        <span className="font-mono text-xs font-bold text-emerald-600 dark:text-emerald-400">
          {Math.round(line_coverage_pct)}% LINE
        </span>
      </div>

      <ProgressCard
        label="Line Coverage"
        percentage={line_coverage_pct}
        color="emerald"
        size="md"
      />

      {branch_coverage_pct !== undefined && branch_coverage_pct !== null && (
        <ProgressCard
          label="Branch Coverage"
          percentage={branch_coverage_pct}
          color="blue"
          size="sm"
        />
      )}

      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-gray-100 dark:border-gray-800 text-center">
        <div className="rounded-lg bg-gray-50 p-2 dark:bg-gray-800/50">
          <span className="block text-[10px] font-medium text-gray-400">TOTAL</span>
          <span className="font-mono text-sm font-bold text-gray-900 dark:text-white">
            {total_statements || (covered_statements + missing_statements)}
          </span>
        </div>

        <div className="rounded-lg bg-emerald-50/50 p-2 dark:bg-emerald-950/20">
          <span className="block text-[10px] font-medium text-emerald-600 dark:text-emerald-400">COVERED</span>
          <span className="font-mono text-sm font-bold text-emerald-700 dark:text-emerald-300">
            {covered_statements}
          </span>
        </div>

        <div className="rounded-lg bg-amber-50/50 p-2 dark:bg-amber-950/20">
          <span className="block text-[10px] font-medium text-amber-600 dark:text-amber-400">MISSING</span>
          <span className="font-mono text-sm font-bold text-amber-700 dark:text-amber-300">
            {missing_statements}
          </span>
        </div>
      </div>
    </div>
  );
};

export default React.memo(CoverageCard);
