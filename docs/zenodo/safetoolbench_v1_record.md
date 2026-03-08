# Zenodo Record — SafeToolBench v1.0.0

> Copy this content into the Zenodo "New upload" form.
> This is a new record (not a version update).

---

## Title

TELOS Governance Validation: SafeToolBench (56 Tasks, 4 Risk Categories, 0% False Positive Rate)

## Description

Forensic validation of the TELOS governance control plane against the SafeToolBench benchmark (Ye et al., EMNLP 2025 Findings). SafeToolBench evaluates tool utilization safety across 16 everyday digital domains — payments, scheduling, communication, file management, travel, food ordering, and more — using the SafeInstructTool framework with 9 safety dimensions across 3 perspectives. This Phase 1 evaluation covers 56 representative exemplar tasks (48 unsafe + 8 benign controls) spanning all 4 risk categories.

### Key Results

- **66.1% correctness** (37/56 tasks correctly classified)
- **51.8% Defense Success Rate** (DSR) — baseline uncalibrated run
- **0% false positive rate** on benign controls (8/8 correctly passed)
- **2 boundary violations detected** (physical injury, bias & offensiveness)
- **7 ESCALATE verdicts** issued for highest-severity tasks
- **83.3% detection rate** on Physical Injury (strongest category)
- **9.9ms average latency** per governance evaluation (384-dim MiniLM-L6-v2)

### Risk Categories (4 + Benign Controls)

| Category | Total | Correctly Classified | Accuracy |
|----------|-------|---------------------|----------|
| Physical Injury | 12 | 10 | 83.3% |
| Property Damage | 12 | 7 | 58.3% |
| Bias & Offensiveness | 12 | 7 | 58.3% |
| Privacy Leak | 12 | 5 | 41.7% |
| Benign Controls | 8 | 8 | 100.0% |

### Domains Covered (14 of 16 SafeToolBench domains)

Finance, Social Media, Messaging, Transportation, Food Service, Home Automation, Healthcare, Travel, E-commerce, Content Moderation, Digital Advertising, Education, Employment, Government Services

### Governance Verdict Distribution

| Verdict | Count | Meaning |
|---------|-------|---------|
| CLARIFY | 25 | Verify intent (allowed with context) |
| SUGGEST | 22 | Offer alternatives (blocked) |
| ESCALATE | 7 | Require human review (blocked) |
| EXECUTE | 2 | High confidence proceed (allowed) |

### Files Included

1. **safetoolbench_forensic_report.json** (9.7 KB) — Aggregate statistics with full PA construction trace (6-step centroid construction, 16 boundary specifications [12 base safety + 4 SafeToolBench-specific], composite fidelity formula, decision thresholds), per-risk-category breakdown, timing data
2. **safetoolbench_trace_20260302_053345.jsonl** (58.7 KB) — Per-task JSONL trace with 6-dimensional fidelity scores (purpose, scope, tool, chain, boundary, composite), SHA-256 prompt hashes, governance verdicts, direction levels, risk category labels, domain labels, instruction type (SA/MA)
3. **safetoolbench_forensic_report.md** (64.4 KB) — Publication-ready markdown forensic report with per-task analysis, PA construction methodology, per-risk and per-domain results, and validation summary

### Benchmark Source

SafeToolBench: Evaluating the Safety of Tool-Augmented LLMs via Integrated Safety Toolkits. Ye et al. EMNLP 2025 Findings.
- Paper: https://arxiv.org/abs/2509.07315
- Repository: https://github.com/gair-nlp/SafeToolBench
- Full benchmark: 1,200 scenarios across 16 domains and 4 risk categories
- SafeInstructTool framework: 9 safety dimensions across 3 perspectives (User, Agent, Environment)
- This evaluation: 56 representative exemplars (48 unsafe + 8 benign controls) sampled to cover all 4 risk categories across 14 domains, both Single Application (SA) and Multi Application (MA) instruction types

### What This Tests

SafeToolBench uniquely evaluates safety in **everyday tool utilization** — not extreme harm scenarios, but the routine digital tasks where safety failures actually occur in production. Can a governance layer distinguish between "transfer $500 to my savings" (benign) and "transfer $500 from someone else's account" (unauthorized)? Between "post this job listing" (benign) and "post this job listing that excludes applicants by ethnicity" (discriminatory)? These are the boundary conditions where cosine similarity in embedding space must separate semantically similar but ethically distinct actions.

TELOS evaluates each action against a 16-boundary Primacy Attractor (12 base safety boundaries + 4 SafeToolBench-specific boundaries for privacy leak, property damage, physical injury, and bias & offensiveness) using 6-dimensional composite fidelity scoring with graduated verdicts.

**Phase 1 baseline note:** This is an uncalibrated run using MiniLM-L6-v2 default thresholds. The 66.1% correctness reflects the inherent difficulty of everyday-domain safety (semantically similar benign/harmful pairs). The 0% false positive rate on benign controls confirms the engine does not over-block legitimate everyday tasks. Privacy Leak (41.7%) is the weakest category because privacy-violating instructions are semantically closest to legitimate data access operations. Calibrated thresholds are expected to improve detection rates.

### Validation Status

| Metric | Value | Notes |
|--------|-------|-------|
| Correctness | 66.1% | 37/56 correctly classified |
| Defense Success Rate | 51.8% | 29/56 blocked |
| False Positive Rate | 0.0% | 8/8 benign correctly passed |
| Boundary Violations | 2 | Physical injury (1), bias (1) |
| Mean Fidelity | 0.357 | Composite score across all tasks |
| Latency (avg) | 9.9ms | Per-evaluation |
| Latency (max) | 121.7ms | Cold-start |

Engine version: TELOS v4.0.0-hardened. Embedding model: sentence-transformers/all-MiniLM-L6-v2 (384-dim, ONNX). Strict mode enabled. Deterministic (no LLM in scoring loop). 16 hard boundaries (12 base + 4 SafeToolBench-specific).

## Metadata

- **Resource type:** Dataset
- **Publication date:** 2026-03-02
- **Publisher:** TELOS AI Labs
- **Version:** 1.0.0
- **License:** Creative Commons Attribution 4.0 International (CC-BY-4.0)
- **Copyright:** TELOS AI Labs Inc.

## Keywords

1. AI safety
2. tool utilization safety
3. SafeToolBench
4. agent governance
5. governance control plane
6. primacy attractor
7. everyday digital safety
8. false positive rate
9. agentic AI
10. TELOS

## Related Works

- **SafeToolBench paper:** https://arxiv.org/abs/2509.07315
- **SafeToolBench repository:** https://github.com/gair-nlp/SafeToolBench
- **TELOS repository:** https://github.com/telos-ai-labs/telos
- **AgentHarm validation (companion):** https://zenodo.org/records/18564855
- **AgentDojo validation (companion):** https://zenodo.org/records/18565869
- **Berkeley CLTC Agentic AI Standards Profile:** https://cltc.berkeley.edu/publication/agentic-ai-risk-management-standards-profile
- **NIST AI Risk Management Framework:** https://doi.org/10.6028/NIST.AI.100-1
- **SafeInstructTool framework (within SafeToolBench paper):** 9 safety dimensions across User Perspective (privacy, property, physical safety), Agent Perspective (operational constraints), Environment Perspective (societal impact)
