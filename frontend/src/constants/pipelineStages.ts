/**
 * TestGen AI v2.2 — Centralized Pipeline Stage Definitions
 *
 * Export 8 pipeline stage definitions for dynamic timeline rendering.
 * Never hardcode pipeline stages inside UI components.
 */

export interface PipelineStageConfig {
  id: string;
  label: string;
  description: string;
  order: number;
}

export const PIPELINE_STAGES: PipelineStageConfig[] = [
  {
    id: 'generation',
    label: 'Generation',
    description: 'Gemini-powered AST test generation',
    order: 1,
  },
  {
    id: 'sandbox',
    label: 'Sandbox',
    description: 'Docker sandbox test execution',
    order: 2,
  },
  {
    id: 'coverage',
    label: 'Coverage',
    description: 'Coverage.py statement & branch analysis',
    order: 3,
  },
  {
    id: 'self_healing',
    label: 'Self-Healing',
    description: 'Automated repair prompt retry cycle',
    order: 4,
  },
  {
    id: 'smells',
    label: 'Test Smells',
    description: 'Static AST smell detection rules',
    order: 5,
  },
  {
    id: 'mutation',
    label: 'Mutation Testing',
    description: 'Pluggable operator mutant generation & execution',
    order: 6,
  },
  {
    id: 'quality_eval',
    label: 'Quality Evaluation',
    description: 'QualityEngine scoring & rating aggregation',
    order: 7,
  },
  {
    id: 'persistence',
    label: 'Persistence',
    description: 'Database checkpoint & result persistence',
    order: 8,
  },
];
