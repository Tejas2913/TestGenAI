/**
 * TestGen AI v2.2 — SmellCard Component
 *
 * Visualizes Total Smells, High / Medium / Low severity badges, and diagnostic smell hygiene rating.
 */

import React from 'react';
import { TestSmellSummary } from '../../types/quality';
import StatusBadge from '../common/StatusBadge';

export interface SmellCardProps {
  smells: TestSmellSummary | null;
  loading?: boolean;
  error?: Error | null;
}

export const SmellCard: React.FC<SmellCardProps> = ({ smells, loading, error }) => {
  if (loading) {
    return (
      <div className="h-64 animate-pulse rounded-xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-900" />
    );
  }

  if (error || !smells) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Test Smells</h3>
        <p className="mt-3 text-xs text-gray-400">Test smell diagnostics not available.</p>
      </div>
    );
  }

  const { total_smells, high_severity_count, medium_severity_count, low_severity_count } = smells;

  const hygieneStatus = total_smells === 0 ? 'EXCELLENT' : total_smells <= 2 ? 'GOOD' : 'POOR';

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Test Smell Analysis
        </h3>
        <StatusBadge status={hygieneStatus} variant={hygieneStatus} size="sm" />
      </div>

      <div className="flex items-baseline justify-between">
        <div>
          <span className="text-3xl font-extrabold tracking-tight text-gray-900 dark:text-white">
            {total_smells}
          </span>
          <span className="ml-2 text-xs font-medium text-gray-500 dark:text-gray-400">
            smells detected
          </span>
        </div>
      </div>

      <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-800">
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            High Severity
          </span>
          <span className="font-mono font-semibold text-red-600 dark:text-red-400">
            {high_severity_count}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
            <span className="h-2 w-2 rounded-full bg-amber-500" />
            Medium Severity
          </span>
          <span className="font-mono font-semibold text-amber-600 dark:text-amber-400">
            {medium_severity_count}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            Low Severity
          </span>
          <span className="font-mono font-semibold text-blue-600 dark:text-blue-400">
            {low_severity_count}
          </span>
        </div>
      </div>
    </div>
  );
};

export default React.memo(SmellCard);
