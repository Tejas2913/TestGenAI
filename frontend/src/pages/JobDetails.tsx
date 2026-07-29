/**
 * TestGen AI v2.2 — JobDetails Page Component
 *
 * Page component responsible for routing parameter extraction (`jobId`) and layout composition.
 */

import React from 'react';
import { useParams, Link } from 'react-router-dom';
import QualityLayout from '../layouts/QualityLayout';
import QualityDashboard from '../components/Quality/QualityDashboard';

export const JobDetails: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();

  return (
    <QualityLayout>
      <div className="flex items-center justify-between border-b border-gray-200 pb-4 dark:border-gray-800">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white">
            Quality Evaluation Dashboard
          </h1>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Comprehensive AST smell diagnostics, coverage analysis, and mutation testing results.
          </p>
        </div>

        <Link
          to="/"
          className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition-all hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-750"
        >
          ← Back to Workspace
        </Link>
      </div>

      <QualityDashboard jobId={jobId} />
    </QualityLayout>
  );
};

export default JobDetails;
