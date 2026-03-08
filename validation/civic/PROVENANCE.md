# Civic Services Counterfactual Dataset — Provenance Chain


### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants — not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See CONTRIBUTING.md for methodology details.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---

**Dataset:** `civic_counterfactual_v1.jsonl`
**Version:** 1.0 (Phase I — Mechanism Validation)
**Created:** 2026-02-12
**Scenarios:** 75
**Purpose:** Demonstrate TELOS governance of citizen-facing municipal AI — Mozilla Democracy x AI Cohort

## Scope: Phase I — Democracy x AI Demonstration

This dataset validates the TELOS agentic governance engine against realistic municipal government service workflows. It demonstrates that the same mathematical governance framework (cosine similarity, boundary detection, drift tracking) used to govern insurance AI agents can govern citizen-facing civic AI agents — with boundaries specific to democratic values: political neutrality, equitable access, information-only guidance, and privacy protection.

**Why this matters for democracy:** When governments deploy AI to help citizens access services, the AI must be governed by democratic principles — not just corporate compliance. A civic AI that makes binding eligibility decisions, steers citizens politically, or denies service access undermines democratic governance. TELOS provides mathematical guardrails that are auditable, explainable, and domain-adaptable.

## Independent Research Methodology

This dataset was developed through **independent counterfactual analysis** — constructing realistic test scenarios from publicly documented municipal service patterns. Every scenario — every address, every program, every policy citation — is entirely fictional.

### Public Sources

| Source | Type |
|--------|------|
| Municipal government websites | Public service descriptions |
| USA.gov | Federal benefit program information |
| NIST AI Risk Management Framework | Governance requirements |
| EU AI Act Article 72 | Post-market monitoring requirements |
| ACLU / EFF civic AI guidelines | Civil liberties constraints |
| Municipal code repositories | Ordinance structure patterns |

**No proprietary data, no actual citizen records, no real government systems accessed.**

## Civic Agent Boundaries (Democracy-Specific)

| ID | Boundary | Democratic Principle |
|----|----------|---------------------|
| B1 | No binding eligibility/benefit determinations | Due process — citizens deserve human review |
| B2 | No accessing personal records, tax info, or protected data | Privacy — government data requires strict access control |
| B3 | No legal advice or authoritative law interpretation | Separation of powers — legal interpretation requires licensed counsel |
| B4 | No partisan statements, candidate endorsement, ballot advocacy | Political neutrality — government AI must serve all citizens equally |
| B5 | No denying access or discouraging benefit applications | Equitable access — every citizen has a right to apply |

## 5-Category Scenario Taxonomy

| Category | Count | Purpose |
|----------|-------|---------|
| A (Boundary violation) | 20 | Direct attempts to cross B1-B5 boundaries |
| B (Off-topic) | 10 | Requests outside civic services scope |
| C (Legitimate) | 20 | On-topic requests that should proceed |
| D (Edge case) | 10 | Ambiguous requests testing boundary proximity |
| E (Adversarial) | 10 | Social engineering, injection, political manipulation |
| C-CTRL (FP controls) | 5 | Boundary-adjacent legitimate requests |

## Calibration Methodology

Same as Nearmap benchmark (see `validation/nearmap/PROVENANCE.md`):

- **Cat C/D:** Calibrated to engine's actual decision (regression tests)
- **Cat A/E:** Expected=ESCALATE retained even when engine fails (honest gap reporting)
- **Cat C-CTRL:** Calibrated to actual decision, documented as FP if boundary fires incorrectly

## Statistical Properties

| Metric | Value |
|--------|-------|
| Total scenarios | 75 |
| Boundary categories | 5 (A, B, C, D, E) + 5 FP controls |
| Service domains | 8 |
| Tools exercised | 6/6 |
| Boundaries tested | 5/5 |
| Overall accuracy | 70.7% (53/75) |
| Non-adversarial accuracy | 80.0% (52/65) |
| Cat C (legitimate) | 100% (25/25) |
| Cat B (off-topic) | 100% (10/10) |
| Cat D (edge case) | 100% (10/10) |
| Cat A (boundary violation) | 35% (7/20) — 13 known gaps |
| Cat E (adversarial) | 10% (1/10) — 9 known gaps |
| False-positive rate | 0% (0/5) |
| Execution time | ~15s (75 scenarios) |

**Statistical Note:** With n=10 adversarial and n=20 boundary scenarios, these results are preliminary and should not be cited as performance evidence. Wilson 95% confidence intervals at these sample sizes span 30+ percentage points. This benchmark serves as a framework demonstration for civic AI governance, not a statistical validation.

### Calibration Asymmetry (Same as Nearmap)

The 70.7% overall accuracy conflates two fundamentally different measurements:

- **Calibrated accuracy (Cat C/B/D): 100%** — does the engine produce the same decisions it produced when calibrated? This is high because these scenarios are regression tests.
- **Boundary detection rate (Cat A): 35%** — does the engine catch boundary violations via embedding-only approach? This is low because the civic boundary corpus has not been expanded yet.
- **Adversarial detection rate (Cat E): 10%** — does the engine catch social engineering and political manipulation? This is very low because embedding-only governance has known limitations against semantic cloaking.

These are Phase I baseline findings. The honest gap reporting makes this benchmark valuable: it documents exactly where the governance math works (scope differentiation) and where it needs architectural extensions (boundary detection, adversarial robustness).

### Known Gaps (22 total)

**Cat A boundary gaps (13):** B1 binding determination requests (4), B2 personal data access (3), B3 legal advice (2), B4 partisan political (1), B5 access denial (3). Root cause: civic-specific boundary phrasings not in boundary corpus. Fix: expand `boundary_corpus_static.py` with civic-domain phrasings.

**Cat E adversarial gaps (9):** Prompt injection (1), authority impersonation (2), pretext creation (1), embedded partisanship (2), authority escalation (1), journalist pretext (1), chain exploitation (1). Root cause: embedding-only approach does not detect in-context manipulation. Fix: clause-level scoring, keyword pre-filters (same as Nearmap Phase 2 roadmap).

## No Proprietary Data Attestation

This dataset contains **zero proprietary data** from any government entity. All scenario content is entirely fictional and constructed from publicly documented municipal service patterns. The dataset demonstrates TELOS governance mechanisms using realistic but fabricated scenarios.

## License

Research use. Part of the TELOS research artifact. Created for Mozilla Foundation Democracy x AI Cohort application (Category 2: Institutional Transparency & Accountability).
