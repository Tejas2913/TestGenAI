/**
 * TestGen AI v2.2 — Dashboard Section Configurations
 *
 * Centralized layout order configuration for dashboard widget composition.
 */

export interface DashboardSectionConfig {
  id: string;
  title: string;
  gridSpan: string; // Tailwind grid span classes
  order: number;
}

export const DASHBOARD_SECTIONS: DashboardSectionConfig[] = [
  {
    id: 'summary',
    title: 'Job Summary',
    gridSpan: 'col-span-12',
    order: 1,
  },
  {
    id: 'timeline',
    title: 'Pipeline Timeline',
    gridSpan: 'col-span-12',
    order: 2,
  },
  {
    id: 'quality',
    title: 'Overall Quality',
    gridSpan: 'col-span-12 md:col-span-6 lg:col-span-3',
    order: 3,
  },
  {
    id: 'coverage',
    title: 'Coverage Analysis',
    gridSpan: 'col-span-12 md:col-span-6 lg:col-span-3',
    order: 4,
  },
  {
    id: 'mutation',
    title: 'Mutation Testing',
    gridSpan: 'col-span-12 md:col-span-6 lg:col-span-3',
    order: 5,
  },
  {
    id: 'smells',
    title: 'Test Smells',
    gridSpan: 'col-span-12 md:col-span-6 lg:col-span-3',
    order: 6,
  },
  {
    id: 'mutants_table',
    title: 'Mutation Analysis Details',
    gridSpan: 'col-span-12',
    order: 7,
  },
];
