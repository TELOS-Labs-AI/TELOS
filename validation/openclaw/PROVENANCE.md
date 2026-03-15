# OpenClaw Governance Benchmark -- Provenance Chain

**Dataset:** `openclaw_boundary_corpus_v1.jsonl`
**Version:** 1.0 (Phase I -- Mechanism Validation)
**Created:** 2026-02-18
**Scenarios:** ~100 across 10 tool groups + cross-group chains
**Configuration:** `openclaw_governed` (balanced governance preset)

## Zero-Assumption Attestation

**Every boundary in this dataset traces to a documented CVE, security advisory, breach report, or published security research. No boundaries were inferred, extrapolated, or assumed.**

Specifically:
- No boundary was constructed from hypothetical threat scenarios
- No attack pattern was invented without a documented precedent
- No vulnerability was assumed to exist without a CVE or security research citation
- No security incident data was fabricated or embellished
- All scenario text is fictional (no real credentials, no real domains, no real user data), but every *pattern* traces to a real, documented incident

## Scope: Phase I -- Mechanism Validation

This dataset validates the TELOS agentic governance engine against attack patterns documented in real security incidents affecting OpenClaw autonomous AI agents. It is a **Phase I mechanism validation** tool -- it tests whether governance math correctly differentiates between legitimate agent operations, boundary violations, adversarial attacks, and off-topic requests across OpenClaw's 10 tool groups.

**Phase I establishes:** Does the TELOS governance engine correctly score and classify OpenClaw tool calls using cosine-similarity-based fidelity measurement, boundary detection, and the 4-layer cascade?

**Phase I does NOT establish:** Production-readiness, adversarial robustness sufficient for deployment, or security certification. Phase I baselines document where the embedding-only approach succeeds and where it requires extensions (SetFit L1.5 training, per-tool-group classifiers, cross-group chain detection).

### Key Difference from Healthcare Benchmark

The healthcare benchmark validates governance against 7 clinical AI configurations with domain-specific regulatory frameworks (HIPAA, EMTALA, FCA). The OpenClaw benchmark validates governance against a single autonomous agent configuration but across **10 tool groups with 4 risk tiers**, where the attack surface is defined by real-world CVEs and documented security incidents rather than regulatory boundaries. The threat model is different: healthcare governs against clinical safety violations; OpenClaw governs against credential theft, RCE, data exfiltration, and supply chain attacks.

## Source Enumeration

All boundaries, attack patterns, and adversarial scenarios trace to publicly documented security incidents.

### Primary Sources

| Source | Type | Public Reference | Boundaries Derived |
|--------|------|------------------|--------------------|
| CVE-2026-25253 | CVE advisory | Belgium CCB advisory, Adversa.ai research | RCE via WebSocket hijacking, gateway exploitation, arbitrary code execution |
| CVE-2026-25157 | CVE advisory | GitHub GHSA-q284-4pvr-m585 | OS command injection via macOS SSH handling, shell metacharacter injection |
| Moltbook breach | Breach report | Wiz Research | API token exfiltration (1.5M tokens), private message exposure, credential harvesting |
| ClawHavoc campaign | Security research | Cisco Skill Scanner | 341 malicious skills (12% of ClawHub), data exfiltration via curl, prompt injection via skill descriptions, command injection, tool poisoning |
| Censys/Shodan exposure | Exposure analysis | Censys Research, Shodan | 24,478 exposed instances, 15.31% leaking mDNS host information, authentication bypass |
| Cyera Research | Permission analysis | Cyera Research | 336 skills request Google Workspace (gmail.modify, full Drive), 127+ demand raw secrets (blockchain keys, Stripe, Azure, YubiKey) |
| Meta internal ban | Corporate advisory | TechBuzz | Internal risk assessment leading to organization-wide ban |
| Infostealer evolution | Threat intelligence | Techzine, The Hacker News | Infostealers targeting OpenClaw config files, gateway tokens, agent identities |

### Secondary Sources (Attack Taxonomy)

| Source | Type | Application |
|--------|------|-------------|
| OWASP LLM Top 10 2025 | Security standard | Attack family classification for prompt injection, insecure output handling |
| OWASP Agentic Top 10 2026 | Security standard | Attack family classification for tool poisoning, excessive agency, insecure delegation |
| NIST AI RMF / 600-1 | Federal framework | Agentic governance requirements |

## 6-Layer Provenance Chain

### Layer 1: Public Source

Every attack pattern in this dataset is derived from publicly documented security incidents (see Source Enumeration above). The mapping from incident to boundary follows a traceable chain:

1. **Incident documented** -- CVE published, breach reported, or security research released
2. **Attack vector extracted** -- Specific technical mechanism identified (e.g., "curl-based exfiltration in ClawHavoc")
3. **Boundary phrasing authored** -- Natural language boundary that captures the violation pattern for embedding-based detection
4. **Safe exemplar paired** -- Legitimate operation using similar vocabulary to test false positive rate
5. **Scenario constructed** -- Full test scenario with request text, expected decision, and source citation

### Layer 2: Attack Vector Extraction

From public sources, the following attack vectors were extracted and mapped to OpenClaw tool groups:

| Attack Vector | Source | Tool Group | Risk Tier |
|---------------|--------|------------|-----------|
| WebSocket hijacking → RCE | CVE-2026-25253 | runtime | CRITICAL |
| SSH argument injection | CVE-2026-25157 | runtime | CRITICAL |
| curl/wget data exfiltration | ClawHavoc | runtime, web | CRITICAL, HIGH |
| .env / credential file theft | Moltbook, Infostealers | fs | HIGH |
| Gateway token harvesting | Moltbook, Infostealers | fs, openclaw | HIGH, CRITICAL |
| Malicious skill installation | ClawHavoc | openclaw | CRITICAL |
| Over-permissioned skill execution | Cyera | openclaw | CRITICAL |
| Prompt injection via skill descriptions | ClawHavoc | openclaw, runtime | CRITICAL |
| Cross-group privilege escalation | ClawHavoc (compound) | cross_group | CRITICAL |
| Persistence via cron/gateway | ClawHavoc | automation | CRITICAL |
| Social engineering via messaging | ClawHavoc | messaging | CRITICAL |
| Configuration tampering | Infostealers | fs, openclaw | HIGH, CRITICAL |
| Network exposure / auth bypass | Censys/Shodan | web, automation | HIGH, CRITICAL |

### Layer 3: Scenario Construction

Each scenario was constructed by:

1. Selecting a target tool group (1 of 10) and boundary category (A/B/C/D/E/FP)
2. For Cat C: writing a natural language request that a legitimate OpenClaw user would make
3. For Cat A: writing a request that directly violates a sourced boundary
4. For Cat E: writing a request that embeds adversarial intent within legitimate-seeming context, with difficulty level (low/medium/high)
5. For Cat FP: writing a legitimate request that uses boundary-adjacent vocabulary
6. Assigning expected governance decision based on boundary alignment
7. Citing the source document for every Cat A/E scenario

Construction principles:
- Request text uses natural developer language appropriate to each tool group
- Adversarial scenarios range from low difficulty (blatant "ignore instructions") to high difficulty (camouflaged in legitimate workflow context)
- All paths, domains, and credentials in scenarios are fictional
- Source citations are mandatory for violation and adversarial categories

### Layer 4: Scenario Organization

Scenarios are organized by tool group and boundary category:

- **Standalone scenarios:** Each tests one governance decision point against one tool group
- **Cross-group scenarios:** Test multi-step action chains that span tool groups (the primary exfiltration pattern)

Scenario ID format: `OC-{TOOLGROUP}-{CATEGORY}-{SEQ}` where TOOLGROUP maps to: FS, RT, WEB, MSG, AUTO, SESS, MEM, UI, NODE, OC, XGRP.

### Layer 5: Governance Telemetry

For each scenario, the benchmark runner captures:
- Purpose fidelity (cosine similarity to PA purpose)
- Scope fidelity (cosine similarity to PA scope)
- Tool fidelity (semantic tool ranking score)
- Chain SCI (semantic continuity index)
- Boundary fidelity (inverted boundary similarity)
- Effective fidelity (weighted composite)
- Decision tier (EXECUTE/CLARIFY/ESCALATE)
- Tool group and risk tier
- L0/L1/L1.5/L2 cascade activation

### Layer 6: Audit Trail

All results are written to `benchmark_results.json` with:
- Per-scenario pass/fail with expected vs actual decisions
- Full governance telemetry
- Aggregate statistics (overall, per-tool-group, per-boundary-category, per-risk-tier)
- Per-attack-family detection rates for Cat E
- No-governance control condition results
- Timestamp and execution duration

## Calibration Methodology

Expected decisions are set based on the scenario's intent and boundary alignment:

- **Cat C (legitimate):** Calibrated to the engine's actual decision after initial benchmark run. Serves as regression tests.
- **Cat A (boundary violations):** Expected = ESCALATE. NOT calibrated when engine fails -- failures documented as known gaps with severity ratings.
- **Cat E (adversarial):** Expected = ESCALATE. Same as Cat A -- honest gap reporting.
- **Cat FP (false positive controls):** Calibrated to engine's actual decision. Documented as FP findings when boundary detection incorrectly fires.
- **Cat B (off-topic):** Calibrated to engine's actual decision.
- **Cat D (edge cases):** Expected = CLARIFY. Calibrated after initial run.

## Known Data Integrity Issues

| Issue | Severity | Status | Mitigation |
|-------|----------|--------|------------|
| Moltbook breach scale discrepancy (1.5M vs 150K tokens) | MEDIUM | OPEN | Use both figures with uncertainty range; resolve from primary Wiz Research source before publication |
| ClawHavoc scan coverage (2,857 of ~10,000+ total skills) | LOW | DOCUMENTED | Note sample coverage in all citations; 11.9% rate is a lower bound |
| Censys/Shodan instance count variance (21,639-24,478) | LOW | DOCUMENTED | Use range, not point estimate; note measurement date sensitivity |

## License

Research use. Part of the TELOS research artifact.

Licensed under the terms of the TELOS AI Labs Inc. proprietary research license. Contact JB@telos-labs.ai for licensing inquiries.

---

### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants -- not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---


*Generated: 2026-02-18 | TELOS AI Labs Inc. | JB@telos-labs.ai*
