# Changelog — TestGen AI

All notable changes to TestGen AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.2.0] - 2026-07-29

### Added (Quality Evaluation Subsystem & React Quality Dashboard)
- **Phase 1: Domain Scaffolding & Data Models**
  - Extended domain dataclasses and schemas: `TestSmellDiagnostic`, `TestSmellSummary`, `MutantDetail`, `MutationSummary`, `QualityBreakdown`, `CompositeQualityResult`.
  - Added abstract base classes: `MutationProvider` (ABC) and `MutationExecutor` (ABC).
  - Extended `app/core/config.py` with v2.2 quality evaluation flags (`ENABLE_QUALITY_EVALUATION`, `ENABLE_MUTATION_TESTING`, `MAX_MUTANTS`, `EXECUTION_TIMEOUT`).
- **Phase 2: Static AST Test Smell Detector**
  - Open/Closed Principle rule-based smell detector under `app/services/smell_rules/`.
  - Detection rules: `AssertionRouletteRule`, `DuplicateAssertionRule`, `EmptyTestRule`, `MagicNumbersRule`, `VerboseTestRule`, `ConditionalLogicRule`.
  - Guaranteed 0ms execution time (100% deterministic static AST inspection).
- **Phase 3: QualityEngine Scoring**
  - Weighted composite scoring algorithm: Coverage (40%), Mutation Score (40%), Smell Hygiene (20%).
  - Categorized rating assignment: `EXCELLENT` (>= 90), `GOOD` (75–89), `FAIR` (60–74), `POOR` (< 60).
- **Phase 4: Pluggable Mutation Operators**
  - Pluggable strategy-pattern mutation operators under `app/services/mutation_operators/`:
    - `ArithmeticOperator`: Swaps binary arithmetic operators (`+`, `-`, `*`, `/`, `%`, `**`).
    - `ComparisonOperator`: Swaps relational operators (`==`, `!=`, `<`, font `<=`, `>`, font `>=`).
    - `BooleanOperator`: Flips logical operations (`and` ↔ `or`).
    - `ConstantReplacementOperator`: Mutates numerical constants and string literals.
    - `UnaryOperator`: Inverts unary operations (`-x` ↔ `+x`, `not x`).
    - `ReturnValueOperator`: Replaces function return expressions with dummy fallbacks (`None`, `0`, `""`, `False`).
- **Phase 5: Mutation Execution Abstraction**
  - Decoupled `MutationExecutionService` abstraction (`app/services/mutation_execution/`).
  - Supported execution environments: `DockerExecutor` and local fallback runner.
- **Phase 6: Quality Pipeline & Workflow Orchestration**
  - Introduced `QualityPipeline` coordinator to aggregate smell detection, mutant generation, mutant execution, and quality scoring.
  - Decoupled `GenerationWorkflow` service from `JobEngine` to preserve single-responsibility job lifecycle management.
- **Phase 7: Quality Evaluation APIs & Integration**
  - REST endpoints:
    - `GET /api/v2/jobs/{job_id}` (embedded `quality_metrics`)
    - `GET /api/v2/jobs/{job_id}/quality`
    - `GET /api/v2/jobs/{job_id}/mutation-summary`
    - `GET /api/v2/jobs/{job_id}/smells`
  - 100% backward compatible API contracts.
- **Phase 8: React Quality Dashboard Presentation Layer**
  - Modern, responsive React dashboard built with TypeScript, Tailwind CSS, and Vite.
  - Reusable presentation components: `QualityCard`, `CoverageCard`, `MutationCard`, `SmellCard`, `PipelineTimeline`, `MutationTable`.
  - Custom hooks: `useJobPolling` (2s interval, unmount cleanup) and `useQualityData` (fault-isolated fetching).
  - Multi-column filtering (`ALL`, `KILLED`, `SURVIVED`, `TIMEOUT`, `ERROR`) and sorting on `MutationTable`.
  - Component-level `ErrorBoundary` for fault isolation.

### Changed
- Refactored `JobEngine` to delegate workflow execution to `GenerationWorkflow`.
- Enhanced structural logging across all backend services (`structlog`).

---

## [2.1.0] - 2026-07-21

### Added (Async Jobs, Auth, Sandbox, Coverage & Self-Healing)
- Async job engine (`/api/v2/jobs/generate` and `/api/v2/jobs/{job_id}`).
- JWT authentication (`/api/v2/auth/register`, `/api/v2/auth/login`) and API Key management (`/api/v2/auth/keys`).
- Isolated Docker sandbox execution environment.
- Statement & branch code coverage analysis via `Coverage.py`.
- Automated Self-Healing retry loop with repair prompt construction and failure classification.

---

## [1.0.0] - 2026-07-07

### Added (Core AI Test Generation)
- Initial Gemini 1.5 Pro / Flash powered unit test generation for Python (`pytest`).
- Structured JSON response parsing and AST validation.
