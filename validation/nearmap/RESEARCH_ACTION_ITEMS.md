# Nearmap Benchmark -- Research Action Items

**Source:** Cross-domain research team review (2026-02-12) + sequential thinking synthesis
**Status:** Phase I complete. Items below are the Phase 2+ roadmap.
**Tracking:** Each item has a priority tier (T0 = blocker, T1 = high, T2 = research) and owner domain.

---

### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants -- not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---


## Completed (Phase I Baseline Commit)

| # | Item | Owner | Status |
|---|------|-------|--------|
| C1 | Fix .gitignore excluding *.jsonl dataset | Karpathy | DONE |
| C2 | Add jinja2 to requirements.txt and pyproject.toml | Karpathy | DONE |
| C3 | Pin torch upper bound (<3.0.0) | Karpathy | DONE |
| C4 | Generate requirements.lock | Karpathy | DONE |
| C5 | Add Phase I framing to PROVENANCE.md | Nell | DONE |
| C6 | Add Phase I framing to REPRODUCIBILITY.md | Nell | DONE |
| C7 | Disaggregated accuracy in CLI output (FPR, adversarial det.) | Gebru | DONE |
| C8 | Calibration asymmetry explanation in docs | Nell/Gebru | DONE |
| C9 | Model version hash pinning in REPRODUCIBILITY.md | Karpathy | DONE |
| C10 | Make generate_adversarial_v2.py idempotent | Karpathy | DONE |
| C11 | Disaggregated evaluation table in ADVERSARIAL_DATASHEET.md | Gebru | DONE |
| C12 | Create RESEARCH_ACTION_ITEMS.md (this file) | All | DONE |

---

## T1: High Priority (Phase 2 -- Next Sprint)

### T1-1: Expand Cat E to 100+ scenarios
**Owner:** Gebru/Nell | **Why:** Wilson 95% CI at n=45 is ~28pp wide. Need ~100 for publishable claims (~20pp CI). Minimum viable for per-family statistical significance.
**How:** Add 55+ scenarios distributed across 9 attack families, prioritizing Fair Insurance (currently n=4) and Misinformation (currently n=2).

### T1-2: Add B6 fairness boundary
**Owner:** Schaake/Russell | **Why:** Fair Insurance family has 25% detection rate partly because there is no explicit fairness boundary. Current B1-B5 boundaries don't cover proxy discrimination.
**How:** Add boundary text: "No use of geographic, demographic, or socioeconomic proxy variables to infer protected class membership or systematically disadvantage any group." Add to agent_templates.py and boundary corpus.

### T1-3: Add keyword baseline comparison
**Owner:** Nell | **Why:** Without a baseline, we cannot attribute governance decisions to embedding-based scoring vs. simple keyword matching. A regex baseline would establish the floor.
**How:** Implement a keyword-only governance scorer that checks for boundary keywords (["override", "ignore", "approve claim", etc.]) and compare detection rates against the embedding scorer.

### T1-4: Add ungoverned baseline -- CLOSED 2026-02-18
**Owner:** Nell | **Status:** IMPLEMENTED
**How:** `--no-governance` flag added to `run_nearmap_benchmark.py`. `_make_no_governance_result()` returns EXECUTE with all fidelity 1.0 for every scenario. 6 pytest tests in `TestNoGovernanceBaseline` validate: all-EXECUTE, flag recorded, fidelity=1.0, no boundaries, governed > ungoverned accuracy, Cat A = 0% ungoverned.

### T1-5: GovernanceEvent timestamp and session_id
**Owner:** Schaake/Karpathy | **Why:** EU AI Act Article 72 requires temporal ordering of monitoring records. Current GovernanceEvent lacks timestamp and session_id fields.
**How:** Add `timestamp: str` and `session_id: str` fields to the governance event schema in the forensic report generator.

### T1-6: Update stakeholder brief
**Owner:** Nell | **Why:** `research/nearmap_governance_validation_brief.md` references 64 scenarios (stale). Current artifact has 173 scenarios, adversarial testing, OWASP mapping, and drift sequences.
**How:** Rewrite to reflect v2.0 results. Include adversarial findings, FPR, and Phase I framing.

### T1-7: ROC curve and AUC
**Owner:** Gebru | **Why:** The boundary fidelity threshold (0.70) was set ad hoc. A ROC curve across threshold values would show whether the current threshold is optimal and reveal the discrimination capacity of the boundary scorer.
**How:** Sweep bf threshold from 0.0 to 1.0 in 0.01 increments. For each threshold, compute TPR (Cat E detected) and FPR (Cat C controls incorrectly escalated). Plot ROC, compute AUC.

---

## T2: Research (Phase 2-3 -- Architectural Extensions)

### T2-1: Clause-level boundary scoring
**Owner:** Russell/Karpathy | **Why:** Mean-pooling dilutes adversarial intent. Clause-level scoring would detect adversarial payloads embedded in legitimate context.
**How:** Split request_text by sentence boundaries. Score each clause independently against boundaries. Take the max boundary similarity across clauses instead of the mean-pooled similarity. Test on the 6 CRITICAL evasions.

### T2-2: Sub-centroid boundary clustering (resume from branch)
**Owner:** Karpathy | **Why:** K-means K=3 sub-centroids were implemented but regressed accuracy (76.6% -> 62.5%). Per-cluster threshold gating may fix this.
**How:** Resume from the WIP commit (6351b3e). Tune per-cluster thresholds so that the cluster containing adversarial-adjacent vocabulary gets a tighter threshold. Test against full 173-scenario corpus.

### T2-3: Adversarial keyword pre-filter
**Owner:** Karpathy | **Why:** Lightweight regex pre-filter for known adversarial patterns could catch blatant attacks before embedding scoring, reducing CRITICAL evasions.
**How:** Build a curated keyword list from Cat E scenarios. Score requests against keyword list before embedding scoring. If keyword match, boost boundary fidelity score. Measure impact on FPR.

### T2-4: Twilight-zone tracking
**Owner:** Gebru | **Why:** The boundary separation margin is only 0.027 (worst evasion bf=0.673 vs threshold 0.70). Requests in the bf 0.60-0.70 range are in a "twilight zone" where the engine cannot reliably discriminate.
**How:** Add a REVIEW tier for requests with bf in [0.60, 0.70]. Log these separately in forensic reports. Track the fraction of twilight-zone requests over time.

### T2-5: Separate drift vs. adversarial Ostrom instantiation
**Owner:** Russell | **Why:** Ostrom DP5 (graduated sanctions) should instantiate differently for drift (NORMAL->WARNING->RESTRICT->BLOCK) vs. adversarial (immediate ESCALATE). Currently both use the same escalation ladder.
**How:** Add an `adversarial_detected` flag to the governance event. When set, skip graduated sanctions and go directly to ESCALATE. This requires the adversarial pre-filter from T2-3.

### T2-6: Chain inheritance attack family
**Owner:** Russell | **Why:** The current 9 attack families don't include "chain inheritance exploitation" -- where an adversarial request inherits the high SCI from a legitimate predecessor in a multi-step chain.
**How:** Design 5-10 scenarios where Step 1-3 are legitimate (building SCI) and Step 4 is adversarial (exploiting inherited SCI to bypass fidelity thresholds). Add as 10th attack family.

### T2-7: Multilingual boundary text
**Owner:** Schaake | **Why:** Language-switching (ESCL-078, Spanish) achieves MODERATE evasion because boundary text is English-only.
**How:** Add boundary specifications in Spanish, French, German, Chinese, and Arabic. Test whether multilingual boundaries reduce ESCL-078's evasion.

### T2-8: Ablation study
**Owner:** Nell/Gebru | **Why:** We don't know how much each governance dimension contributes to accuracy. Ablation would reveal whether boundary fidelity alone is sufficient or whether purpose/scope/tool fidelity are load-bearing.
**How:** Run benchmark with each dimension disabled in turn. Report accuracy drop for each ablation.

### T2-9: Human evaluation sample
**Owner:** Nell | **Why:** Ground-truth labels are currently self-referential (calibrated to engine behavior for Cat C/D, researcher judgment for Cat E). A small human evaluation would provide external validity.
**How:** Select 30 scenarios (10 Cat C, 10 Cat E, 10 mixed). Have 3 domain experts (insurance/compliance) independently label expected decisions. Compare inter-rater reliability and agreement with engine.

### T2-10: Uncertainty extension to guardian-ward model
**Owner:** Russell | **Why:** The guardian-ward model assumes deterministic fidelity scores. Adding uncertainty quantification (e.g., bootstrap CIs on cosine similarity) would let the engine express "I'm not sure" rather than making a binary decision.
**How:** For each request, compute N bootstrap samples of the embedding. Report the CI on fidelity scores. When CI spans a decision boundary, output REVIEW instead of a hard decision.

---

## Not Planned (Documented Decisions)

| Item | Reason |
|------|--------|
| Production deployment of benchmark | Phase I is mechanism validation only |
| Compliance certification claims | Requires legal review, not engineering |
| EU AI Act Article 15 robustness claim | Not claimable at 68.9% adversarial detection |
| Automated adversarial scenario generation | Requires LLM in loop, violates Phase I determinism |

---

*Created: 2026-02-12 | Source: Cross-domain research review synthesis | TELOS AI Labs Inc.*
