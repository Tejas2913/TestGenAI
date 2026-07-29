# TestGen AI v2.2 — System Architecture Specification

**Version**: 2.2.0  
**Status**: Frozen Baseline Architecture  
**Author**: TestGen AI Architecture Review Board  

---

## 1. Executive Architecture Summary

TestGen AI v2.2 expands the v2.1 baseline by introducing a comprehensive **Quality Evaluation Subsystem**. While v2.1 focused on generating, sandboxing, and self-healing tests, v2.2 introduces static test smell detection, pluggable mutation operator execution, weighted quality scoring, and a dedicated presentation dashboard.

The architecture enforces strict decoupling:
- **`JobEngine`**: Manages async job state transitions, atomic claiming, and startup recovery.
- **`GenerationWorkflow`**: Orchestrates the 8-stage generation lifecycle.
- **`QualityPipeline`**: Coordinates smell detection, mutant generation, mutant execution, and scoring.
- **React Frontend**: Pure presentation layer consuming REST endpoints.

---

## 2. Overall System Architecture

```mermaid
graph TD
    Client[React Quality Dashboard] -->|REST API JSON| API[FastAPI V2 Router]
    API -->|Auth & Validate| Auth[JWT & API Key Middleware]
    Auth -->|Submit Job| JobRepo[Job Repository SQLite/Postgres]
    JobRepo -->|Async Task| Workflow[GenerationWorkflow Orchestrator]
    
    subgraph Execution Pipeline
        Workflow -->|1. Prompt Build| Gemini[Gemini LLM Provider]
        Workflow -->|2. Container Exec| Docker[Docker Sandbox Runner]
        Workflow -->|3. Statements| Coverage[Coverage.py Engine]
        Workflow -->|4. Repair Loop| SelfHeal[Self-Healing Engine]
        Workflow -->|5-7. Quality Pipeline| QualityPipe[QualityPipeline]
    end

    subgraph Quality Subsystem
        QualityPipe -->|Static AST| Smell[TestSmellDetector Strategy]
        QualityPipe -->|Mutant Gen| MutRunner[MutationRunner Strategy]
        MutRunner -->|Container Exec| MutExec[MutationExecutionService]
        QualityPipe -->|Weighted Score| QualityEng[QualityEngine]
    end

    Workflow -->|8. Checkpoint| Persistence[Database Persistence Layer]
```

---

## 3. Backend Layered Architecture

```mermaid
graph TB
    subgraph Presentation Layer
        Router[FastAPI API V2 Routers]
        Schema[Pydantic V2 Schemas]
    end

    subgraph Orchestration Layer
        GenWorkflow[GenerationWorkflow Coordinator]
        QualPipeline[QualityPipeline Aggregator]
        JobEng[JobEngine Lifecycle]
    end

    subgraph Domain & Strategy Layer
        SmellDetector[TestSmellDetector]
        Rules[Smell Rules: Assertion, Magic, Empty, Verbose...]
        MutationRunner[MutationRunner]
        Operators[Operators: Arithmetic, Comparison, Boolean...]
        MutationExec[MutationExecutor: DockerExecutor]
        Scorer[QualityEngine]
    end

    subgraph Infrastructure Layer
        DockerSandbox[Docker Container Sandbox]
        CoverEngine[Coverage.py Runner]
        LLM[Gemini Provider Client]
        Database[(SQLAlchemy Database)]
    end

    Router --> GenWorkflow
    GenWorkflow --> QualPipeline
    QualPipeline --> SmellDetector
    SmellDetector --> Rules
    QualPipeline --> MutationRunner
    MutationRunner --> Operators
    MutationRunner --> MutationExec
    MutationExec --> DockerSandbox
    QualPipeline --> Scorer
    GenWorkflow --> Database
```

---

## 4. GenerationWorkflow & QualityPipeline Sequence

```mermaid
sequenceDiagram
    autonumber
    participant User as React Dashboard / API Client
    participant API as FastAPI Router (/api/v2/jobs)
    participant Workflow as GenerationWorkflow
    participant Pipeline as QualityPipeline
    participant Smell as TestSmellDetector
    participant MutRunner as MutationRunner
    participant MutExec as MutationExecutor
    participant Engine as QualityEngine
    participant DB as Database Repository

    User->>API: POST /api/v2/jobs/generate
    API->>DB: Create Job (status=pending)
    API-->>User: HTTP 202 Accepted (job_id)

    rect rgb(240, 248, 255)
        note over Workflow: Async Execution Pipeline
        Workflow->>Workflow: Stage 1: AI Test Generation (Gemini)
        Workflow->>Workflow: Stage 2: Sandbox Execution (Docker)
        Workflow->>Workflow: Stage 3: Coverage Analysis (Coverage.py)
        Workflow->>Workflow: Stage 4: Self-Healing (if needed)
        
        Workflow->>Pipeline: Stage 5-7: execute_quality_pipeline()
        
        Pipeline->>Smell: detect_smells(test_code)
        Smell-->>Pipeline: TestSmellSummary & Diagnostics
        
        Pipeline->>MutRunner: generate_mutants(source_code)
        MutRunner-->>Pipeline: List[MutantDetail]
        
        Pipeline->>MutExec: execute_mutants(mutants)
        MutExec-->>Pipeline: MutationSummary (killed, survived, timeout)
        
        Pipeline->>Engine: calculate_quality_score(coverage, mutation, smells)
        Engine-->>Pipeline: CompositeQualityResult (overall_score, rating)
        
        Pipeline-->>Workflow: CompositeQualityResult
        Workflow->>DB: Stage 8: Persist Generation & Job (status=completed)
    end

    User->>API: GET /api/v2/jobs/{job_id}/quality
    API->>DB: Fetch Generation Quality Record
    API-->>User: QualityMetricsResponse JSON
```

---

## 5. Mutation Framework (Strategy & Open/Closed Design)

```mermaid
classDiagram
    class MutationOperator {
        <<abstract>>
        +name: str
        +mutate(node: ast.AST)* List[Mutant]
        +supports_node(node: ast.AST)* bool
    }

    class ArithmeticOperator {
        +mutate(node: ast.BinOp) List[Mutant]
    }
    class ComparisonOperator {
        +mutate(node: ast.Compare) List[Mutant]
    }
    class BooleanOperator {
        +mutate(node: ast.BoolOp) List[Mutant]
    }
    class ConstantReplacementOperator {
        +mutate(node: ast.Constant) List[Mutant]
    }
    class UnaryOperator {
        +mutate(node: ast.UnaryOp) List[Mutant]
    }
    class ReturnValueOperator {
        +mutate(node: ast.Return) List[Mutant]
    }

    MutationOperator <|-- ArithmeticOperator
    MutationOperator <|-- ComparisonOperator
    MutationOperator <|-- BooleanOperator
    MutationOperator <|-- ConstantReplacementOperator
    MutationOperator <|-- UnaryOperator
    MutationOperator <|-- ReturnValueOperator

    class MutationRunner {
        -operators: List[MutationOperator]
        +generate_mutants(source_code: str) List[Mutant]
    }

    MutationRunner o-- MutationOperator
```

---

## 6. React Component Hierarchy

```mermaid
graph TD
    App[App.jsx / Router] --> Protected[ProtectedRoute]
    Protected --> Layout[AppLayout]
    Layout --> Workspace[DashboardPage / JobDetails]
    
    Workspace --> ResultPanel[ResultPanel.jsx]
    ResultPanel --> Tabs[Tab Bar: Summary | Quality | Tests | Code | Sandbox]
    
    Tabs --> QualityDash[QualityDashboard.tsx Container]
    QualityDash --> ErrorBound[ErrorBoundary.tsx]
    
    ErrorBound --> Banner[Job Summary Banner]
    ErrorBound --> Timeline[PipelineTimeline.tsx]
    ErrorBound --> QCard[QualityCard.tsx]
    ErrorBound --> CCard[CoverageCard.tsx]
    ErrorBound --> MCard[MutationCard.tsx]
    ErrorBound --> SCard[SmellCard.tsx]
    ErrorBound --> MTable[MutationTable.tsx]
    
    QCard --> ProgressCard[ProgressCard.tsx]
    QCard --> StatusBadge[StatusBadge.tsx]
    CCard --> ProgressCard
    MCard --> ProgressCard
    SCard --> StatusBadge
    MTable --> StatusBadge
```

---

## 7. Database Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    USERS ||--o{ JOBS : owns
    USERS ||--o{ API_KEYS : possesses
    JOBS ||--o| GENERATIONS : produces
    
    USERS {
        uuid id PK
        string email UK
        string hashed_password
        boolean is_active
        datetime created_at
    }
    
    API_KEYS {
        uuid id PK
        uuid user_id FK
        string key_hash UK
        string name
        boolean is_active
        datetime created_at
    }

    JOBS {
        string id PK
        uuid user_id FK
        string status
        string generation_id FK
        int retry_count
        string last_checkpoint
        string error_code
        string error_detail
        datetime created_at
        datetime updated_at
    }

    GENERATIONS {
        string id PK
        text source_code
        text generated_tests_code
        float quality_score
        string quality_rating
        float coverage_line_pct
        float mutation_score
        int killed_mutants
        int survived_mutants
        int smell_count
        text smell_breakdown_json
        datetime created_at
    }
```
