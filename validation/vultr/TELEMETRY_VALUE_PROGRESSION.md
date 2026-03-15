# Telemetry Value Progression

## The Compounding Effect

TELOS governance generates telemetry that feeds calibration, which improves governance, which generates better telemetry. This compounding loop means the value of deploying governance increases over time -- and the cost of waiting grows with every month of missed telemetry.

## Day 1

From the first governed action, the customer has:

- **Full audit trail** -- every agent action scored and recorded in structured JSONL
- **Governance receipts** -- cryptographic evidence of every governance decision (verdict, fidelity score, dimension breakdown, boundary status)
- **Boundary enforcement** -- hard boundaries active immediately (no training period required for boundary detection)
- **Compliance evidence** -- audit events map directly to framework requirements across 11 regulatory standards
- **Visibility** -- real-time view of what agents are doing, not just what they report

Day 1 value is not speculative. The audit trail exists. The boundary enforcement works. The compliance evidence accumulates. This is demonstrable in the review surface simulation.

## Month 3

With ~90 days of production telemetry:

- **CUSUM drift detection calibrated** -- statistical change-point detection tuned to the customer's actual workload patterns, not generic defaults
- **False positive rate refined** -- the system has learned which actions are routine for this specific agent in this specific domain
- **Entrainment patterns accumulating** -- the governance engine recognizes patterns of legitimate multi-step workflows
- **First calibration pass complete** -- initial threshold adjustments based on real production data (not training data, not synthetic scenarios)
- **Operational patterns emerging** -- the system understands what "normal" looks like for this customer's agents

## Month 12

With a full year of production telemetry:

- **PA fully calibrated from 10K+ decisions** -- the Purpose Artifact has been refined against thousands of real governance decisions, not dozens of test scenarios
- **Custom SetFit classifier trained** -- a domain-specific boundary classifier trained on the customer's actual boundary violations and legitimate actions
- **Optimized thresholds** -- false positive and false negative rates driven down by production telemetry analysis
- **12 months of regulatory evidence on file** -- when regulators arrive, the customer has a year of governance evidence ready for review
- **Governance that understands the workload** -- the system is no longer applying generic governance; it governs this specific agent with this specific tool set in this specific domain

## The Timeline Asymmetry

| Starting Point | When Regulators Arrive |
|----------------|----------------------|
| Deployed 12 months ago | 12 months of calibrated evidence. SetFit trained. Thresholds optimized. Audit trail complete. |
| Deployed 3 months ago | Basic calibration started. Some evidence accumulated. Still in early calibration phase. |
| Deploying now | Day 1 capabilities only. No calibration. No domain-specific classifiers. Starting from zero. |

The asymmetry is not linear -- it compounds. A 12-month head start does not produce 4x the value of a 3-month head start. It produces calibrated governance that a 3-month deployment cannot replicate by running faster.

## What Accumulates

| Telemetry Type | How It Compounds |
|----------------|-----------------|
| Governance decisions | Each scored action refines the statistical model of "normal" for this agent |
| Boundary violations | Real violations train the SetFit classifier better than synthetic examples |
| False positives | Identified false positives directly improve threshold calibration |
| Chain patterns | Multi-step workflow patterns reduce false escalations for legitimate sequences |
| Drift episodes | Historical drift data improves CUSUM sensitivity and specificity |

## What Does Not Transfer

This calibration data is **non-transferable**:

- Cannot be bootstrapped from another customer's telemetry (different agent, different domain, different boundaries)
- Cannot be synthesized from test scenarios (production patterns differ from test patterns)
- Cannot be accelerated by running more agents (calibration requires temporal distribution, not volume)

The only way to have 12 months of calibrated governance is to have been running governance for 12 months.
