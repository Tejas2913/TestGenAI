/**
 * TestGen AI v2.2 — MutationTable Component
 *
 * Interactive table displaying generated mutant details.
 * Features:
 *   - Status filtering (`ALL`, `KILLED`, `SURVIVED`, `TIMEOUT`, `ERROR`).
 *   - Multi-column sorting by line number, category, and status.
 *   - Responsive table layout with accessible ARIA markup.
 */

import React, { useState, useMemo } from 'react';
import { MutantDetail, MutantStatus } from '../../types/quality';
import StatusBadge from '../common/StatusBadge';

export interface MutationTableProps {
  mutants?: MutantDetail[];
}

type SortField = 'line_number' | 'category' | 'status';
type SortOrder = 'asc' | 'desc';

export const MutationTable: React.FC<MutationTableProps> = ({ mutants = [] }) => {
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sortField, setSortField] = useState<SortField>('line_number');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  // Filter mutants by status
  const filteredMutants = useMemo(() => {
    if (!mutants || mutants.length === 0) return [];
    if (statusFilter === 'ALL') return mutants;
    return mutants.filter((m) => m.status.toUpperCase() === statusFilter);
  }, [mutants, statusFilter]);

  // Sort mutants by field
  const sortedMutants = useMemo(() => {
    return [...filteredMutants].sort((a, b) => {
      let valueA: any = a[sortField];
      let valueB: any = b[sortField];

      if (typeof valueA === 'string') {
        valueA = valueA.toLowerCase();
        valueB = valueB.toLowerCase();
      }

      if (valueA < valueB) return sortOrder === 'asc' ? -1 : 1;
      if (valueA > valueB) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredMutants, sortField, sortOrder]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const statusCounts = useMemo(() => {
    const counts = { ALL: mutants.length, KILLED: 0, SURVIVED: 0, TIMEOUT: 0, ERROR: 0 };
    mutants.forEach((m) => {
      const st = m.status.toUpperCase() as keyof typeof counts;
      if (counts[st] !== undefined) counts[st]++;
    });
    return counts;
  }, [mutants]);

  const FILTER_TABS: Array<{ id: string; label: string; count: number }> = [
    { id: 'ALL', label: 'All', count: statusCounts.ALL },
    { id: 'KILLED', label: 'Killed', count: statusCounts.KILLED },
    { id: 'SURVIVED', label: 'Survived', count: statusCounts.SURVIVED },
    { id: 'TIMEOUT', label: 'Timeout', count: statusCounts.TIMEOUT },
    { id: 'ERROR', label: 'Error', count: statusCounts.ERROR },
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Mutation Detail Diagnostics
        </h3>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800" role="tablist">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={statusFilter === tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
                statusFilter === tab.id
                  ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
                  : 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'
              }`}
            >
              {tab.label} <span className="ml-1 opacity-60">({tab.count})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-800">
        <table className="w-full text-left text-xs" aria-label="Mutants Detail Table">
          <thead className="bg-gray-50 text-gray-500 uppercase tracking-wider dark:bg-gray-800/60 dark:text-gray-400">
            <tr>
              <th className="px-4 py-2.5 font-semibold">Mutant ID</th>
              <th
                className="px-4 py-2.5 font-semibold cursor-pointer hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort('category')}
              >
                Category {sortField === 'category' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th
                className="px-4 py-2.5 font-semibold cursor-pointer hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort('status')}
              >
                Status {sortField === 'status' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th
                className="px-4 py-2.5 font-semibold cursor-pointer hover:text-gray-700 dark:hover:text-gray-200"
                onClick={() => handleSort('line_number')}
              >
                Line {sortField === 'line_number' ? (sortOrder === 'asc' ? '↑' : '↓') : ''}
              </th>
              <th className="px-4 py-2.5 font-semibold">Description</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
            {sortedMutants.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-gray-400">
                  No mutants match the selected filter.
                </td>
              </tr>
            ) : (
              sortedMutants.map((mutant) => (
                <tr
                  key={mutant.id}
                  className="hover:bg-gray-50/50 dark:hover:bg-gray-800/40 transition-colors"
                >
                  <td className="px-4 py-2.5 font-mono text-[11px] font-medium text-gray-800 dark:text-gray-200">
                    {mutant.id}
                  </td>
                  <td className="px-4 py-2.5 font-medium text-gray-700 dark:text-gray-300">
                    {mutant.category || mutant.operator}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={mutant.status} variant={mutant.status as MutantStatus} size="sm" />
                  </td>
                  <td className="px-4 py-2.5 font-mono text-gray-600 dark:text-gray-400">
                    Line {mutant.line_number}
                  </td>
                  <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 max-w-md truncate">
                    {mutant.description}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default React.memo(MutationTable);
