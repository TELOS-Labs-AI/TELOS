# Zenodo Record — AgentHarm v2.0.0

> Copy this content into the Zenodo "New version" form for record 18564855.
> Version bump: v1.0.0 → v2.0.0

---

## Title

TELOS Governance Validation: AgentHarm (24 Tasks, Two-Gate 83.3% DSR)

## Description

Forensic validation of the TELOS governance control plane against the AgentHarm benchmark (Mazeika et al., NeurIPS 2024). This v2.0.0 release evaluates the **two-gate scoring architecture** — Gate 1 (tool selection fidelity via per-tool centroids) + Gate 2 (behavioral fidelity via scope/boundary/chain) — on 24 representative exemplar tasks spanning 12 harm categories.

### Key Results

- **91.7% correctness** (22/24 tasks correctly classified)
- **83.3% Defense Success Rate** (DSR) — up from 74.1% single-gate in v1.0.0
- **6 boundary violations detected** across harassment, illegal drugs, copyright, disinformation, CSAM, terrorism
- **7 ESCALATE verdicts** issued for highest-severity tasks
- **100% detection** on 11 of 12 harm categories
- **25% false positive rate** on benign controls (1/4 incorrectly blocked)
- **9.9ms average latency** per governance evaluation (384-dim MiniLM-L6-v2)

### Harm Categories (12)

- Fraud (2/2 blocked)
- Cybercrime (2/2 blocked)
- Harassment (2/2 blocked)
- Illegal Drugs (2/2 blocked)
- Copyright Violation (1/1 blocked)
- Disinformation (2/2 blocked)
- Weapons (2/2 blocked)
- Privacy Violation (1/2 blocked)
- CSAM (1/1 blocked)
- Terrorism (2/2 blocked)
- Self-Harm (1/1 blocked)
- Multi-Step Fraud (1/1 blocked)
- Benign Controls (3/4 correctly passed)

### Governance Verdict Distribution

| Verdict | Count | Meaning |
|---------|-------|---------|
| SUGGEST | 13 | Offer alternatives (blocked) |
| ESCALATE | 7 | Require human review (blocked) |
| CLARIFY | 2 | Verify intent (allowed with context) |
| EXECUTE | 2 | High confidence proceed (allowed) |

### Files Included

1. **agentharm_forensic_report.json** (10.9 KB) — Aggregate statistics with full PA construction trace (6-step centroid construction, 12 hard boundary specifications, composite fidelity formula, decision thresholds), per-category breakdown, timing data
2. **agentharm_trace_20260302_051837.jsonl** (24.7 KB) — Per-task JSONL trace with 6-dimensional fidelity scores (purpose, scope, tool, chain, boundary, composite), SHA-256 prompt hashes, governance verdicts, direction levels, boundary violation flags
3. **agentharm_forensic_report.md** (30.5 KB) — Publication-ready markdown forensic report with per-task analysis, PA construction methodology, category-level results, and validation summary

### Benchmark Source

AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents. Mazeika et al. NeurIPS 2024.
- Paper: https://arxiv.org/abs/2410.09024
- Repository: https://github.com/GraySwanAI/AgentHarm
- Full benchmark: 352 harmful behaviors across 11 harm categories
- This evaluation: 24 representative exemplars (20 harmful + 4 benign controls) sampled to cover all 12 categories including multi-step fraud

### What This Tests

AgentHarm evaluates whether an AI governance layer can detect and block harmful agent tool-call sequences. Unlike prompt-level safety benchmarks that test LLM refusal, AgentHarm tests whether a governance control plane can identify harmful *actions* — tool calls that would commit fraud, deploy malware, stalk individuals, or synthesize dangerous materials. TELOS evaluates each action request against a 12-boundary Primacy Attractor using 6-dimensional composite fidelity scoring, issuing graduated verdicts (EXECUTE/CLARIFY/SUGGEST/INERT/ESCALATE) rather than binary allow/block.

**v2.0.0 architecture change:** The two-gate system separates tool selection fidelity (Gate 1: does this tool belong in scope?) from behavioral fidelity (Gate 2: is this action within boundaries?). This separation improved DSR from 74.1% (v1 single-gate) to 83.3% (v2 two-gate) by catching cases where a legitimate tool is used for an illegitimate purpose.

### Validation Status

| Metric | v1.0.0 (Single-Gate) | v2.0.0 (Two-Gate) | Delta |
|--------|----------------------|---------------------|-------|
| Defense Success Rate | 74.1% | 83.3% | +9.2pp |
| Correctness | — | 91.7% | — |
| Boundary Violations Detected | — | 6 | — |
| ESCALATE Verdicts | — | 7 | — |
| Architecture | Single composite score | Gate 1 (tool) + Gate 2 (behavior) | Two-gate |

Engine version: TELOS v4.0.0-hardened. Embedding model: sentence-transformers/all-MiniLM-L6-v2 (384-dim, ONNX). Strict mode enabled. Deterministic (no LLM in scoring loop).

## Metadata

- **Resource type:** Dataset
- **Publication date:** 2026-03-02
- **Publisher:** TELOS AI Labs
- **Version:** 2.0.0
- **License:** Creative Commons Attribution 4.0 International (CC-BY-4.0)
- **Copyright:** TELOS AI Labs Inc.

## Keywords

1. AI safety
2. agent governance
3. tool-call safety
4. AgentHarm
5. governance control plane
6. primacy attractor
7. defense success rate
8. boundary detection
9. agentic AI
10. TELOS

## Related Works

- **AgentHarm paper:** https://arxiv.org/abs/2410.09024
- **AgentHarm repository:** https://github.com/GraySwanAI/AgentHarm
- **TELOS repository:** https://github.com/TELOS-Labs-AI/telos
- **AgentDojo validation (companion):** https://zenodo.org/records/18565869
- **AgentHarm v1.0.0 (this record, previous version):** https://zenodo.org/records/18564855
- **Berkeley CLTC Agentic AI Standards Profile:** https://cltc.berkeley.edu/publication/agentic-ai-risk-management-standards-profile
- **NIST AI Risk Management Framework:** https://doi.org/10.6028/NIST.AI.100-1
