# Build vs Buy -- Enterprise AI Governance

## The Component Breakdown

Building production-grade AI governance in-house requires four major components, each with significant engineering and operational cost.

### 1. Embedding Infrastructure ($200K - $500K)

Semantic governance requires understanding what an AI agent is actually doing -- not just pattern matching on keywords. This means:

- Sentence embedding models (training, fine-tuning, hosting)
- ONNX optimization for production latency requirements
- Embedding cache infrastructure
- Model versioning and rollback capability
- Inference pipeline for sub-30ms latency at scale

### 2. Governance Engine ($500K - $1M)

The core scoring engine that evaluates every agent action against purpose, scope, boundaries, and tool authorization:

- Multi-dimensional fidelity scoring (purpose, scope, boundary, tool, chain)
- 4-layer scoring cascade (keyword, embedding, SetFit classifier, composite)
- Boundary enforcement with configurable severity
- Chain continuity tracking across multi-step agent workflows
- Escalation management with human-in-the-loop integration
- Drift detection (CUSUM-based statistical monitoring)

### 3. Compliance Mapping ($100K - $300K)

Mapping governance telemetry to regulatory frameworks is not a one-time exercise -- frameworks evolve, and evidence requirements change:

- Framework analysis and requirement decomposition
- Evidence mapping (which telemetry satisfies which requirement)
- Gap analysis and coverage reporting
- Ongoing framework updates (EU AI Act, NIST, IEEE, OWASP)
- Audit-ready documentation generation

### 4. Ongoing Calibration & Maintenance ($200K+/yr)

Governance is not a deploy-and-forget system. It requires continuous calibration:

- False positive / false negative analysis
- Threshold tuning from production telemetry
- Domain-specific classifier training (SetFit)
- Boundary corpus maintenance
- Regression testing across configuration changes

## Total Cost Summary

| Approach | Year 1 Cost | Time to Production | Ongoing Cost |
|----------|-------------|-------------------|--------------|
| In-house build | $1M - $2M+ | 12 - 18 months | $200K+/yr |
| TELOS via Vultr | Governed GPU tier | Same day | Self-attuning |

## The Real Cost

The dollar comparison understates the actual risk. The real cost is **6-12 months without governance evidence** while:

- Regulators finalize enforcement frameworks (EU AI Act enforcement begins 2025-2026)
- Competitors accumulate governance telemetry and calibration data
- Enterprise customers increasingly require governance evidence in procurement
- Insurance carriers begin requiring AI governance documentation

Every month of operation generates calibration data that makes governance more accurate. Companies that deploy governance today will have 12 months of calibrated telemetry when regulators arrive. Companies that wait will start from zero.

## What "Self-Attuning" Means

TELOS governance improves from its own telemetry without manual intervention:

1. **Telemetry accumulates** -- every governance decision generates structured data
2. **Calibration runs** -- statistical analysis identifies threshold adjustments
3. **Classifiers train** -- domain-specific SetFit models learn from production data
4. **Thresholds optimize** -- false positive rates decrease as the system learns the workload
5. **Evidence compounds** -- regulatory readiness increases with every governed action

This is not a static rules engine. It is a governance system that gets better at governing the specific workload it protects.
