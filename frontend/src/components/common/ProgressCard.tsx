/**
 * TestGen AI v2.2 — Reusable ProgressCard Component
 *
 * Displays a labeled progress bar with numeric percentage and status color.
 */

import React from 'react';

export interface ProgressCardProps {
  label: string;
  percentage: number;
  sublabel?: string;
  color?: 'blue' | 'emerald' | 'amber' | 'purple' | 'red';
  size?: 'sm' | 'md' | 'lg';
}

const COLOR_MAP = {
  blue: 'bg-blue-600 dark:bg-blue-500',
  emerald: 'bg-emerald-600 dark:bg-emerald-500',
  amber: 'bg-amber-500 dark:bg-amber-400',
  purple: 'bg-purple-600 dark:bg-purple-500',
  red: 'bg-red-600 dark:bg-red-500',
};

const HEIGHT_MAP = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

export const ProgressCard: React.FC<ProgressCardProps> = ({
  label,
  percentage,
  sublabel,
  color = 'blue',
  size = 'md',
}) => {
  const clamped = Math.max(0, Math.min(100, Math.round(percentage)));

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between text-xs font-medium text-gray-700 dark:text-gray-300">
        <span>{label}</span>
        <span className="font-mono font-semibold">{clamped}%</span>
      </div>

      <div
        className={`w-full overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800 ${HEIGHT_MAP[size]}`}
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${COLOR_MAP[color]}`}
          style={{ width: `${clamped}%` }}
        />
      </div>

      {sublabel && (
        <p className="text-[11px] text-gray-500 dark:text-gray-400">{sublabel}</p>
      )}
    </div>
  );
};

export default ProgressCard;
