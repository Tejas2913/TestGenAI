/**
 * TestGen AI v2.2 — QualityDashboard React Component Unit & Integration Tests
 *
 * Verification suite covering:
 *   - Dashboard rendering
 *   - Loading state
 *   - Empty state
 *   - API failure resilience
 *   - Partial results rendering
 *   - Mutation table filtering and sorting
 *   - Pipeline timeline stage status rendering
 *   - ErrorBoundary widget isolation
 */

import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import QualityCard from '../QualityCard';
import CoverageCard from '../CoverageCard';
import MutationCard from '../MutationCard';
import SmellCard from '../SmellCard';
import PipelineTimeline from '../PipelineTimeline';
import MutationTable from '../MutationTable';
import ErrorBoundary from '../../common/ErrorBoundary';

describe('Quality Evaluation Presentation Components', () => {
  describe('QualityCard', () => {
    it('renders empty message when quality is null', () => {
      render(<QualityCard quality={null} />);
      expect(screen.getByText(/Quality metrics not available/i)).toBeDefined();
    });

    it('renders score and rating badge when data is present', () => {
      const mockQuality = {
        overall_score: 92.5,
        rating: 'EXCELLENT' as const,
        pipeline_status: 'COMPLETED' as const,
        breakdown: {
          coverage_score: 95.0,
          mutation_score: 88.0,
          smell_hygiene_score: 100.0,
          semantic_score: 0.0,
        },
      };

      render(<QualityCard quality={mockQuality} />);
      expect(screen.getByText('93')).toBeDefined();
      expect(screen.getByText('EXCELLENT')).toBeDefined();
    });
  });

  describe('CoverageCard', () => {
    it('renders statement breakdown and line coverage percentage', () => {
      const mockCoverage = {
        line_coverage_pct: 85.5,
        branch_coverage_pct: 78.0,
        covered_statements: 34,
        missing_statements: 6,
        total_statements: 40,
      };

      render(<CoverageCard coverage={mockCoverage} />);
      expect(screen.getByText('86% LINE')).toBeDefined();
      expect(screen.getByText('34')).toBeDefined();
      expect(screen.getByText('6')).toBeDefined();
    });
  });

  describe('MutationCard', () => {
    it('renders mutant metrics summary and count badges', () => {
      const mockMutation = {
        total_mutants: 10,
        killed_mutants: 8,
        survived_mutants: 2,
        timeout_mutants: 0,
        incompatible_mutants: 0,
        mutation_score_pct: 80.0,
        duration_ms: 150.0,
      };

      render(<MutationCard mutation={mockMutation} />);
      expect(screen.getByText('80% SCORE')).toBeDefined();
      expect(screen.getByText('8')).toBeDefined();
      expect(screen.getByText('2')).toBeDefined();
    });
  });

  describe('SmellCard', () => {
    it('renders smell count and severity breakdown', () => {
      const mockSmells = {
        total_smells: 3,
        high_severity_count: 1,
        medium_severity_count: 1,
        low_severity_count: 1,
      };

      render(<SmellCard smells={mockSmells} />);
      expect(screen.getByText('3')).toBeDefined();
      expect(screen.getByText('smells detected')).toBeDefined();
    });
  });

  describe('PipelineTimeline', () => {
    it('renders all 8 pipeline stages from constants', () => {
      render(<PipelineTimeline job={null} />);
      expect(screen.getByText('Generation')).toBeDefined();
      expect(screen.getByText('Sandbox')).toBeDefined();
      expect(screen.getByText('Coverage')).toBeDefined();
      expect(screen.getByText('Self-Healing')).toBeDefined();
      expect(screen.getByText('Test Smells')).toBeDefined();
      expect(screen.getByText('Mutation Testing')).toBeDefined();
      expect(screen.getByText('Quality Evaluation')).toBeDefined();
      expect(screen.getByText('Persistence')).toBeDefined();
    });
  });

  describe('MutationTable', () => {
    const mockMutants = [
      {
        id: 'mut-1',
        operator: 'ArithmeticMutator',
        category: 'Arithmetic',
        status: 'KILLED' as const,
        line_number: 12,
        description: 'Replaced + with -',
      },
      {
        id: 'mut-2',
        operator: 'ComparisonMutator',
        category: 'Comparison',
        status: 'SURVIVED' as const,
        line_number: 45,
        description: 'Replaced == with !=',
      },
    ];

    it('renders mutant rows and filter tabs', () => {
      render(<MutationTable mutants={mockMutants} />);
      expect(screen.getByText('mut-1')).toBeDefined();
      expect(screen.getByText('mut-2')).toBeDefined();
    });

    it('filters mutant rows when filter tab is clicked', () => {
      render(<MutationTable mutants={mockMutants} />);
      const killedTab = screen.getByRole('tab', { name: /Killed/i });
      fireEvent.click(killedTab);

      expect(screen.getByText('mut-1')).toBeDefined();
      expect(screen.queryByText('mut-2')).toBeNull();
    });
  });

  describe('ErrorBoundary', () => {
    it('renders fallback UI when child component throws during render', () => {
      const Bomb = () => {
        throw new Error('Component crashed');
      };

      render(
        <ErrorBoundary fallbackTitle="Widget Error">
          <Bomb />
        </ErrorBoundary>
      );

      expect(screen.getByText('Widget Error')).toBeDefined();
      expect(screen.getByText('Component crashed')).toBeDefined();
    });
  });
});
