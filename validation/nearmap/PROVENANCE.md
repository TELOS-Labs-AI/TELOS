# Nearmap Counterfactual Dataset — Provenance Chain


### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants — not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---

**Dataset:** `nearmap_counterfactual_v1.jsonl`
**Version:** 2.0 (Phase I + RESTRICT + Drift + Adversarial v2)
**Created:** 2026-02-11 | **Updated:** 2026-02-12
**Scenarios:** 173 (131 standalone + 42 sequence steps)

## Scope: Phase I — Mechanism Validation

This dataset validates the TELOS agentic governance engine against realistic property intelligence workflows derived from publicly documented Nearmap capabilities. It is a **Phase I mechanism validation** tool — it tests whether governance math correctly differentiates between legitimate requests, scope drift, boundary violations, adversarial attacks, and off-topic noise.

**Phase I establishes:** Does the governance math work? Can cosine-similarity-based fidelity scoring, combined with boundary detection and drift tracking, produce correct governance decisions on a representative scenario corpus?

**Phase I does NOT establish:** Production-readiness, compliance certification, or adversarial robustness sufficient for deployment. The 68.9% adversarial detection rate and 46.7% false-positive rate are Phase I baselines — they document where the embedding-only approach succeeds and where it requires architectural extensions (clause-level scoring, keyword pre-filters, expanded boundary corpus). See `RESEARCH_ACTION_ITEMS.md` for the Phase 2 roadmap.

### Calibration Asymmetry

The 90.2% overall accuracy conflates two fundamentally different measurements:

- **Non-adversarial accuracy (97.7%)** measures **regression consistency** — does the engine produce the same decisions it produced when the scenarios were calibrated? This is high because Cat C/D scenarios are calibrated to the engine's actual behavior.
- **Adversarial detection rate (68.9%)** measures **security posture** — does the engine catch attacks it has never been calibrated against? This is lower because Cat E scenarios retain expected=ESCALATE even when the engine fails, documenting true detection gaps rather than masking them.

These should be read as separate metrics, not averaged.

## Independent Research Methodology

This dataset was developed through **independent counterfactual analysis** — a standard research methodology in which publicly documented product capabilities are used to construct realistic test scenarios without requiring access to proprietary systems, APIs, or internal data.

### What this means in practice

TELOS AI Labs studied publicly available Nearmap product documentation — product pages, capability descriptions, press releases, and published industry integration standards — and constructed plausible scenarios that represent the kinds of requests a property intelligence agent would encounter in regulated insurance workflows. Every scenario — every address, every score, every tool output, every property detail — is entirely fictional. No Nearmap API was called. No proprietary data was accessed. No customer information was used. No internal documents were consulted.

This is comparable to how automotive safety researchers build crash test scenarios from publicly documented vehicle specifications without access to the manufacturer's engineering files, or how cybersecurity researchers construct penetration test scenarios from published API documentation without access to the target's source code.

### Why this approach is credible

1. **We are testing our system, not theirs.** The governance engine under test is TELOS. Nearmap's capabilities define the *domain context* — the realistic backdrop against which governance decisions are measured. Whether Nearmap's actual API returns a roof score of 72 or 85 is irrelevant; what matters is whether the TELOS governance engine correctly distinguishes "retrieve a roof condition score" (legitimate) from "approve this claim based on the score" (boundary violation).

2. **Public sources are sufficient for mechanism validation.** The 7 tool definitions, 5 boundary specifications, and scoring output formats used in this dataset are all derivable from public documentation. The governance engine's decisions depend on *semantic similarity between requests and the agent's purpose/scope/boundaries* — not on the numeric accuracy of fabricated tool outputs.

3. **No consent was required because no proprietary information was used.** The relationship between this dataset and Nearmap is comparable to an academic paper that cites a product's public documentation to illustrate a research methodology — the citation requires no permission, and the research conclusions are about the methodology (TELOS governance), not the cited product.

4. **The counterfactual framing is explicit.** Every scenario is labeled as counterfactual. The dataset does not claim to represent actual Nearmap API behavior, actual property data, or actual underwriting decisions. It represents *plausible governance decision points* constructed from publicly documented workflow patterns.

### What we do NOT claim

- We do not claim Nearmap endorsement, review, or participation in this research
- We do not claim that fabricated tool outputs match actual Nearmap API responses
- We do not claim that the scenarios represent real properties, real claims, or real underwriting decisions
- We do not claim that governance decisions validated against this dataset constitute Nearmap product certification or compliance assessment

### What we DO claim

- The scenarios are **domain-realistic**: they reflect the kinds of requests insurance professionals make when using property intelligence platforms, as documented in public industry literature
- The governance engine's decisions are **reproducible**: the same input always produces the same output (deterministic sentence-transformer embeddings, no external API calls)
- The adversarial scenarios are **research-grounded**: each maps to a published attack taxonomy (OWASP LLM Top 10 2025, OWASP Agentic Top 10 2026, NIST AI 100-2, NAIC FACTS) with documented provenance
- The known gaps are **honestly reported**: 17 governance failures (14 adversarial evasions + 3 boundary detection gaps) and 7 false positives are documented as security findings, not hidden as calibration artifacts

## 6-Layer Provenance Chain

### Layer 1: Public Source

All scenario content is derived from publicly available Nearmap documentation:

| Source | Type | URL |
|--------|------|-----|
| Nearmap Product Pages | Public website | nearmap.com/products |
| Nearmap ImpactResponse | Public product documentation | nearmap.com/solutions/insurance |
| Nearmap AI Feature Extraction | Public capability descriptions | nearmap.com/ai |
| NAIC Model Bulletin on AI | Public regulatory document | naic.org |
| ITEL Process Documentation | Public industry standard | itel.com |
| NOAA Storm Reports | Public data | ncdc.noaa.gov |
| CAL FIRE VHFHSZ Maps | Public data | fire.ca.gov |

**No proprietary data, no Nearmap API responses, no customer data, no internal documents.**

### Layer 2: Capability Extraction

From public sources, the following capabilities were extracted and encoded into the dataset:

- **7 tool definitions:** property_lookup, aerial_image_retrieve, roof_condition_score, peril_risk_score, generate_property_report, request_material_sample, submit_itel_analysis
- **5 boundary specifications:** No binding decisions (NAIC), no PII access, no overriding adjusters, no premium quotes, no autonomous repair authorization
- **Scoring outputs:** RSI 0-100, RCCS per-attribute breakout, peril scores, detection counts
- **Property types:** Residential, commercial (with RCCS), multi-family (multi-building)
- **Peril types:** Hail, wind, wildfire, equipment damage, multi-peril

### Layer 3: Scenario Construction

Each scenario was constructed by:

1. Selecting a property type, peril type, and target governance decision
2. Writing a natural language request that an underwriter or adjuster would plausibly make
3. Crafting tool output text that reflects realistic Nearmap-style responses
4. Assigning a boundary enforcement category (A/B/C/D)
5. Including SB 24-205 cohort_metadata fields where applicable

Construction principles:
- Requests use natural insurance industry language
- Tool outputs include realistic data (addresses, scores, detections)
- Boundary violations reference specific boundary text from the agent template
- All addresses are fictional (no real property data)
- All numeric data is fabricated for demonstration purposes

### Layer 4: Request Sequence

Scenarios are organized into:
- **131 standalone scenarios:** Each tests one governance decision point independently (83 original + 33 Cat E adversarial + 15 Cat C false-positive controls)
- **42 sequential scenarios (5 groups):** Tests chain continuity, SAAI drift tier transitions, boundary violations during drift, drift recovery lifecycle, and adversarial escalation chains

| Sequence | Steps | Purpose |
|----------|-------|---------|
| SEQ-HAIL-001 | 4 | Chain continuity across multi-step hail workflow |
| SEQ-DRIFT-GRADUAL | 10 | All 3 SAAI thresholds in order (WARNING → RESTRICT → BLOCK) |
| SEQ-DRIFT-BOUNDARY | 12 | Boundary violation during active drift accumulation |
| SEQ-DRIFT-RECOVERY | 16 | Full lifecycle: BLOCK → acknowledge → resume → re-BLOCK |
| SEQ-ADV-ESCALATION | 4 | Adversarial graduated escalation chain (Cat E chain exploitation) |

Request ordering within standalone scenarios is randomized at runtime.

### Layer 5: Governance Telemetry

For each scenario, the benchmark runner captures:
- Purpose fidelity (cosine similarity to PA purpose)
- Scope fidelity (cosine similarity to PA scope)
- Tool fidelity (semantic tool ranking score)
- Chain SCI (semantic continuity index)
- Boundary fidelity (inverted boundary similarity)
- Effective fidelity (weighted composite)
- Decision tier (EXECUTE/CLARIFY/ESCALATE)
- SAAI drift level and magnitude

### Layer 6: Audit Trail

All results are written to `benchmark_results.json` with:
- Per-scenario pass/fail with expected vs actual decisions
- Full governance telemetry for each scenario
- Aggregate statistics (overall accuracy, per-decision, per-tool, per-boundary)
- Sequence group results with chain continuity analysis
- Timestamp and execution duration

## Calibration Methodology

Expected decisions were initially set based on the scenario's intent (e.g., a legitimate property lookup should EXECUTE, an adversarial prompt injection should ESCALATE). After each benchmark expansion, scenarios are calibrated against the governance engine's actual behavior with sentence-transformer embeddings. Calibration notes are embedded in each scenario's `description` field.

**Calibration philosophy:**

- **Cat C (legitimate) and Cat D (edge case):** Calibrated to the engine's actual decision. These scenarios serve as regression tests — if the engine's behavior changes, the test catches it.
- **Cat A (boundary violations) and Cat E (adversarial):** Expected decisions are NOT calibrated to the engine's actual decision when the engine fails to detect the violation. Instead, they are kept as expected=ESCALATE and documented as **known gaps**. This ensures the dataset honestly measures the engine's security posture rather than retroactively defining failures as successes.
- **Cat C false-positive controls:** Calibrated to the engine's actual decision and documented as false-positive findings when boundary detection incorrectly fires on legitimate requests.

### Version History

**v1.0 (2026-02-11):** 76 standalone scenarios (Cat A-D), initial calibration. 37 scenarios calibrated from original intent.

**v1.2 (2026-02-12):** Added 12 Cat A boundary expansion, 38 drift sequence steps, 12 Cat E adversarial (ad-hoc). 5 known gaps (ESCL-003, ESCL-005, ESCL-006, ESCL-074, ESCL-075).

**v2.0 (2026-02-12):** Research-grounded adversarial expansion. Cross-domain research team review produced unified taxonomy (9 attack families). Added 33 new Cat E scenarios (ESCL-076 through ESCL-108), 15 Cat C false-positive controls (CTRL-001 through CTRL-015), attack_metadata backfill on 12 existing Cat E. Total: 173 scenarios, 17 known gaps (3 boundary + 14 adversarial), 7 false positives.

## Statistical Properties

| Metric | Value |
|--------|-------|
| Total scenarios | 173 |
| EXECUTE | 22 (12.7%) |
| CLARIFY | 28 (16.2%) |
| (SUGGEST/INERT removed) | Remapped to CLARIFY/ESCALATE in 3-verdict model |
| ESCALATE | 104 (60.1%) |
| Category A (direct violation) | 23 |
| Category B (indirect/off-topic) | 42 |
| Category C (legitimate + controls) | 53 |
| Category D (edge case) | 10 |
| Category E (adversarial) | 45 |
| Property types | 3 (residential, commercial, multi-family) |
| Peril types | 5 (hail, wind, wildfire, equipment, multi-peril) |
| Tools exercised | 7/7 |
| Sequence groups | 5 (46 steps total) |
| Attack families (Cat E) | 9/9 |
| False-positive controls | 15 |
| Overall accuracy | 90.2% (156/173) |
| Non-adversarial accuracy | 97.7% (125/128) |
| Adversarial detection rate | 68.9% (31/45) |
| CRITICAL evasions (EXECUTE on Cat E) | 6 |
| MODERATE evasions (CLARIFY on Cat E) | 8 |
| False-positive rate (controls) | 46.7% (7/15) |
| Known gaps (total) | 17 (3 boundary + 14 adversarial) |

## No Proprietary Data Attestation

This dataset contains **zero proprietary data** from Nearmap, Inc. or any other entity. All scenario content — addresses, property details, tool outputs, scores, and recommendations — is entirely fictional and constructed solely from publicly documented product capabilities. The dataset demonstrates TELOS governance mechanisms using realistic but fabricated scenarios. See the "Independent Research Methodology" section above for the full methodological justification.

## License

Research use. Part of the TELOS research artifact.

Licensed under the terms of the TELOS AI Labs Inc. proprietary research license. Contact JB@telos-labs.ai for licensing inquiries.
