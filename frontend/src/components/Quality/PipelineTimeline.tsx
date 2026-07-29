/**
 * TestGen AI v2.2 — PipelineTimeline Component
 *
 * Visual progression timeline for the 8-stage TestGen AI pipeline.
 * Renders dynamically from PIPELINE_STAGES constant.
 */

import React from 'react';
import { PIPELINE_STAGES, PipelineStageConfig } from '../../constants/pipelineStages';
import { JobSummary } from '../../types/quality';

export interface PipelineTimelineProps {
  job: JobSummary | null;
}

export const PipelineTimeline: React.FC<PipelineTimelineProps> = ({ job }) => {
  const getStageStatus = (stage: PipelineStageConfig): 'completed' | 'running' | 'pending' | 'failed' => {
    if (!job) return 'pending';

    const status = job.status;
    const checkpoint = (job.last_checkpoint || '').toLowerCase();

    if (status === 'completed') return 'completed';
    if (status === 'failed') return 'failed';

    if (status === 'running' || status === 'quality_running') {
      if (checkpoint.includes(stage.id)) return 'running';
      // If checkpoint has moved past this stage order
      const stageIdx = PIPELINE_STAGES.findIndex((s) => s.id === stage.id);
      const checkpointIdx = PIPELINE_STAGES.findIndex((s) => checkpoint.includes(s.id));
      if (checkpointIdx >= 0 && stageIdx < checkpointIdx) return 'completed';
      if (stageIdx === checkpointIdx + 1) return 'running';
    }

    return 'pending';
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
          Pipeline Orchestration Timeline
        </h3>
        <span className="text-xs text-gray-400 font-mono">8 STAGES</span>
      </div>

      <div className="relative flex items-center justify-between gap-1 overflow-x-auto py-2">
        {PIPELINE_STAGES.map((stage, idx) => {
          const status = getStageStatus(stage);

          let circleStyle = 'bg-gray-100 text-gray-400 border-gray-300 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-500';
          let icon = <span className="text-xs">{idx + 1}</span>;

          if (status === 'completed') {
            circleStyle = 'bg-emerald-500 text-white border-emerald-500 dark:bg-emerald-600';
            icon = (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
              </svg>
            );
          } else if (status === 'running') {
            circleStyle = 'bg-blue-600 text-white border-blue-600 animate-pulse';
            icon = (
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
            );
          } else if (status === 'failed') {
            circleStyle = 'bg-red-500 text-white border-red-500';
            icon = (
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
              </svg>
            );
          }

          return (
            <div key={stage.id} className="flex flex-1 flex-col items-center text-center min-w-[90px]">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full border font-bold shadow-sm transition-all ${circleStyle}`}
                title={`${stage.label}: ${stage.description}`}
              >
                {icon}
              </div>
              <span className="mt-2 text-[11px] font-semibold text-gray-800 dark:text-gray-200 truncate max-w-[85px]">
                {stage.label}
              </span>
              <span className="text-[9px] text-gray-400 dark:text-gray-500 capitalize">{status}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default React.memo(PipelineTimeline);
