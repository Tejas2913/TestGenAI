/**
 * TestGen AI v2.2 — Quality API Layer
 *
 * Stateless API service wrapping FastAPI v2 Quality and Job endpoints via clientV2.
 * Strictly presentation layer wrapper; zero business logic.
 */

import { clientV2 } from './client';
import {
  JobSummary,
  QualityMetrics,
  MutationSummary,
  TestSmellSummary,
} from '../types/quality';

export const qualityApi = {
  /**
   * Fetch async job lifecycle details and embedded quality metrics.
   * GET /api/v2/jobs/{jobId}
   */
  getJobDetails: async (jobId: string): Promise<JobSummary> => {
    return clientV2.get(`/jobs/${jobId}`);
  },

  /**
   * Fetch Quality Metrics sub-resource.
   * GET /api/v2/jobs/{jobId}/quality
   */
  getJobQuality: async (jobId: string): Promise<QualityMetrics> => {
    return clientV2.get(`/jobs/${jobId}/quality`);
  },

  /**
   * Fetch Mutation Testing Summary sub-resource.
   * GET /api/v2/jobs/{jobId}/mutation-summary
   */
  getJobMutationSummary: async (jobId: string): Promise<MutationSummary> => {
    return clientV2.get(`/jobs/${jobId}/mutation-summary`);
  },

  /**
   * Fetch Test Smells Summary sub-resource.
   * GET /api/v2/jobs/{jobId}/smells
   */
  getJobSmells: async (jobId: string): Promise<TestSmellSummary> => {
    return clientV2.get(`/jobs/${jobId}/smells`);
  },
};

export default qualityApi;
