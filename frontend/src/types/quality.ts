/**
 * TestGen AI v2.2 — Quality Evaluation Domain Type Definitions
 *
 * Strongly typed TypeScript interfaces for API responses, dashboard metrics,
 * coverage analysis, mutation testing, test smells, and pipeline stage states.
 */

/** Job summary metadata returned by backend GET /api/v2/jobs/{jobId} */
export interface JobSummary {
  job_id: string;
  status: 'pending' | 'processing' | 'quality_running' | 'completed' | 'failed' | 'partial' | 'cancelled';
  repository?: string;
  generated_tests?: number;
  execution_time_ms?: number;
  retry_count: number;
  last_checkpoint?: string | null;
  checkpoint_updated_at?: string | null;
  generation_id?: string | null;
  error_code?: string | null;
  error_detail?: string | null;
  created_at: string;
  updated_at: string;
}

/** Quality score rating classification */
export type QualityRating = 'EXCELLENT' | 'GOOD' | 'FAIR' | 'POOR' | 'UNKNOWN';

/** Sub-score breakdowns for overall quality */
export interface QualityBreakdown {
  coverage_score: number;
  mutation_score: number;
  smell_hygiene_score: number;
  semantic_score: number;
}

/** Mutation testing summary metrics */
export interface MutationSummary {
  total_mutants: number;
  killed_mutants: number;
  survived_mutants: number;
  timeout_mutants: number;
  incompatible_mutants: number;
  mutation_score_pct: number;
  duration_ms: number;
}

/** Individual mutant diagnostic detail */
export type MutantStatus = 'KILLED' | 'SURVIVED' | 'TIMEOUT' | 'ERROR';

export interface MutantDetail {
  id: string;
  operator: string;
  category: string;
  status: MutantStatus;
  line_number: number;
  description: string;
}

/** Test smell diagnostics summary */
export interface TestSmellSummary {
  total_smells: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
}

/** Overall Quality Metrics response payload from /quality sub-resource */
export interface QualityMetrics {
  overall_score: number;
  rating: QualityRating;
  pipeline_status: 'COMPLETED' | 'PARTIAL' | 'FAILED' | 'SKIPPED';
  breakdown: QualityBreakdown;
  mutation?: MutationSummary | null;
  smells?: TestSmellSummary | null;
}

/** Code coverage metrics structure */
export interface CoverageMetrics {
  line_coverage_pct: number;
  branch_coverage_pct?: number | null;
  covered_statements: number;
  missing_statements: number;
  total_statements: number;
}

/** Pipeline stage execution state */
export type PipelineStageStatus = 'pending' | 'running' | 'completed' | 'skipped' | 'failed';

export interface PipelineStage {
  id: string;
  label: string;
  description: string;
  status: PipelineStageStatus;
}

/** Consolidated Dashboard state response wrapper */
export interface DashboardData {
  job: JobSummary | null;
  quality: QualityMetrics | null;
  coverage: CoverageMetrics | null;
  mutation: MutationSummary | null;
  smells: TestSmellSummary | null;
  mutants: MutantDetail[];
}
