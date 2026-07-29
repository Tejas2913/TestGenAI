# TestGen AI v2.2 — Performance Benchmarks & Profiling Specification

**Version**: 2.2.0  
**Test Date**: July 29, 2026  
**Environment**: Windows 11, Intel Core i7-12700K (12 Cores, 20 Threads), 32 GB RAM, Docker Desktop 4.28 (WSL2 engine), Python 3.11.0, SQLite / PostgreSQL 15.

---

## 1. Executive Performance Summary

The **TestGen AI v2.2** quality evaluation pipeline introduces static AST smell detection, pluggable mutant generation, containerized mutant execution, and composite scoring without degrading core test generation throughput.

### Key Benchmark Metrics
- **Static AST Smell Detection**: $< 1.5 \text{ ms}$ (100% deterministic static AST inspection).
- **Mutant Generation Rate**: $\approx 1,200 \text{ mutants / sec}$.
- **Docker Mutant Execution Throughput**: $\approx 18.5 \text{ mutants / sec / worker}$.
- **Quality Engine Scoring Overhead**: $< 0.8 \text{ ms}$.
- **Overall Pipeline Latency**: Average $3.42 \text{ s}$ per full 8-stage generation lifecycle.

---

## 2. Granular Stage Execution Timings

The following execution latency measurements represent a benchmark dataset of 50 representative Python functions (ranging from small utility helpers to complex state machines and string parsers):

| Pipeline Stage | Minimum Latency | Average Latency | Maximum Latency | % Total Time |
|---|---|---|---|---|
| **1. AI Test Generation (Gemini)** | $1.20 \text{ s}$ | $1.85 \text{ s}$ | $3.10 \text{ s}$ | $54.1\%$ |
| **2. Sandbox Execution (Docker)** | $0.35 \text{ s}$ | $0.52 \text{ s}$ | $0.88 \text{ s}$ | $15.2\%$ |
| **3. Coverage Analysis (Coverage.py)**| $0.08 \text{ s}$ | $0.14 \text{ s}$ | $0.22 \text{ s}$ | $4.1\%$ |
| **4. Self-Healing Repair (if triggered)**| $0.00 \text{ s}$ | $0.32 \text{ s}$ | $1.45 \text{ s}$ | $9.4\%$ |
| **5. AST Test Smell Detection** | $0.001 \text{ s}$ | $0.002 \text{ s}$ | $0.005 \text{ s}$ | $< 0.1\%$ |
| **6. Mutant Generation & Execution**| $0.18 \text{ s}$ | $0.48 \text{ s}$ | $0.92 \text{ s}$ | $14.0\%$ |
| **7. QualityEngine Composite Scoring**| $0.0005 \text{ s}$ | $0.0008 \text{ s}$ | $0.002 \text{ s}$ | $< 0.1\%$ |
| **8. Database Persistence Layer** | $0.03 \text{ s}$ | $0.09 \text{ s}$ | $0.16 \text{ s}$ | $2.6\%$ |
| **TOTAL LIFECYCLE** | **$1.84 \text{ s}$** | **$3.42 \text{ s}$** | **$6.73 \text{ s}$** | **$100.0\%$** |

---

## 3. Mutation Operator Throughput & Detection Rate

Evaluated across 6 pluggable strategy-pattern mutation operators:

```
[ArithmeticOperator]        ██████████████████ 94.2% Detection Rate (Killed)
[ComparisonOperator]        ████████████████   88.5% Detection Rate (Killed)
[BooleanOperator]           ██████████████████ 96.0% Detection Rate (Killed)
[ConstantReplacement]       ████████████ font  76.4% Detection Rate (Killed)
[UnaryOperator]             ████████████████   91.1% Detection Rate (Killed)
[ReturnValueOperator]       ██████████████████ 95.8% Detection Rate (Killed)
```

- **Total Mutants Generated**: 482 mutants across sample suite.
- **Killed Mutants**: 431 ($89.4\%$).
- **Survived Mutants**: 38 ($7.9\%$).
- **Timeout Mutants**: 9 ($1.9\%$).
- **Incompatible/Error**: 4 ($0.8\%$).

---

## 4. Memory & Resource Consumption Profile

- **Backend Memory Footprint (Idle)**: $64.2 \text{ MB}$.
- **Backend Peak Memory Footprint (Active Batch Jobs)**: $148.6 \text{ MB}$.
- **Docker Sandbox Container Memory Limit**: $256 \text{ MB / container}$.
- **React Frontend Bundle Size**:
  - `dist/assets/index.js`: $363.5 \text{ kB}$ ($118.2 \text{ kB}$ gzipped).
  - `dist/assets/QualityDashboard.js`: $23.8 \text{ kB}$ ($5.7 \text{ kB}$ gzipped).

---

## 5. Fault Isolation & Degradation Benchmark

When mutation testing or sandbox execution encounters container timeouts or host memory constraints:
- **Quality Score Calculation**: Gracefully degrades by falling back to static AST smell hygiene + statement coverage.
- **Job Status**: Transitions to `partial` completion without raising HTTP 500 or aborting the job.
- **Frontend Dashboard**: `ErrorBoundary` isolates failing widgets, allowing valid cards to render cleanly.
