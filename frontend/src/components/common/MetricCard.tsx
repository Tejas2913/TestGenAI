/**
 * TestGen AI v2.2 — Reusable MetricCard Component
 *
 * Displays a metric title, formatted numeric value, optional icon, and trend/subtext.
 */

import React from 'react';

export interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  badge?: React.ReactNode;
  icon?: React.ReactNode;
  accentColor?: 'blue' | 'emerald' | 'amber' | 'purple' | 'red' | 'indigo' | 'gray';
  loading?: boolean;
}

const ACCENT_STYLES = {
  blue: 'border-l-4 border-l-blue-500 bg-blue-50/30 dark:bg-blue-950/20',
  emerald: 'border-l-4 border-l-emerald-500 bg-emerald-50/30 dark:bg-emerald-950/20',
  amber: 'border-l-4 border-l-amber-500 bg-amber-50/30 dark:bg-amber-950/20',
  purple: 'border-l-4 border-l-purple-500 bg-purple-50/30 dark:bg-purple-950/20',
  red: 'border-l-4 border-l-red-500 bg-red-50/30 dark:bg-red-950/20',
  indigo: 'border-l-4 border-l-indigo-500 bg-indigo-50/30 dark:bg-indigo-950/20',
  gray: 'border-l-4 border-l-gray-400 bg-gray-50/50 dark:bg-gray-900/50',
};

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  badge,
  icon,
  accentColor = 'gray',
  loading = false,
}) => {
  return (
    <div
      className={`rounded-xl border border-gray-200 p-4 shadow-sm transition-all dark:border-gray-800 ${
        ACCENT_STYLES[accentColor]
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          {title}
        </span>
        {icon && <div className="text-gray-400 dark:text-gray-500">{icon}</div>}
      </div>

      <div className="mt-2 flex items-baseline justify-between">
        {loading ? (
          <div className="h-8 w-20 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
        ) : (
          <div className="text-2xl font-bold tracking-tight text-gray-900 dark:text-white">
            {value}
          </div>
        )}
        {badge}
      </div>

      {subtitle && (
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{subtitle}</p>
      )}
    </div>
  );
};

export default MetricCard;
