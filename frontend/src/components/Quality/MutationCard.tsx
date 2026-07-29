/**
 * TestGen AI v2.2 — MutationCard Component
 *
 * Visualizes Mutation Score %, Killed, Survived, Timeout, and Error mutants metrics.
 */

import React from 'react';
import { MutationSummary } from '../../types/quality';
import ProgressCard from '../common/ProgressCard';

export interface MutationCardProps {
  mutation: MutationSummary | null;
  loading?: boolean;
  error?: Error | null;
}

export const MutationCard: React.FC<MutationCardProps> = ({ mutation, loading, error }) => {
  if (loading) {
    return (
      <div className="h-64 animate-pulse rounded-xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-900" />
    );
  }

  if (error || !mutation) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Mutation Testing</h3>
        <p className="mt-3 text-xs text-gray-400">Mutation metrics not available.</p>
      </div>
    );
  }

  const {
    total_mutants,
    killed_mutants,
    survived_mutants,
    timeout_mutants,
    incompatible_mutants,
    mutation_score_pct,
  } = mutation;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Mutation Testing
        </h3>
        <span className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400">
          {Math.round(mutation_score_pct)}% SCORE
        </span>
      </div>

      <ProgressCard
        label="Mutants Killed"
        percentage={mutation_score_pct}
        color="blue"
        size="md"
        sublabel={`${killed_mutants} of ${total_mutants} mutants killed`}
      />

      <div className="grid grid-cols-4 gap-1.5 pt-2 border-t border-gray-100 dark:border-gray-800 text-center">
        <div className="rounded bg-emerald-50/60 p-1.5 dark:bg-emerald-950/20">
          <span className="block text-[9px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase">KILLED</span>
          <span className="font-mono text-xs font-bold text-emerald-700 dark:text-emerald-300">
            {killed_mutants}
          </span>
        </div>

        <div className="rounded bg-red-50/60 p-1.5 dark:bg-red-950/20">
          <span className="block text-[9px] font-semibold text-red-600 dark:text-red-400 uppercase">SURVIVED</span>
          <span className="font-mono text-xs font-bold text-red-700 dark:text-red-300">
            {survived_mutants}
          </span>
        </div>

        <div className="rounded bg-amber-50/60 p-1.5 dark:bg-amber-950/20">
          <span className="block text-[9px] font-semibold text-amber-600 dark:text-amber-400 uppercase">TIMEOUT</span>
          <span className="font-mono text-xs font-bold text-amber-700 dark:text-amber-300">
            {timeout_mutants}
          </span>
        </div>

        <div className="rounded bg-purple-50/60 p-1.5 dark:bg-purple-950/20">
          <span className="block text-[9px] font-semibold text-purple-600 dark:text-purple-400 uppercase">ERROR</span>
          <span className="font-mono text-xs font-bold text-purple-700 dark:text-purple-300">
            {incompatible_mutants}
          </span>
        </div>
      </div>
    </div>
  );
};

export default React.memo(MutationCard);
