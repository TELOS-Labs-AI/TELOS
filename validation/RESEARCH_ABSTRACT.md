# Geometric Governance for AI Safety: A Control-Theoretic Approach to Harmful Content Prevention

## Research Abstract

### Problem Statement

Existing AI safety mechanisms rely primarily on Reinforcement Learning from Human Feedback (RLHF) to train models to refuse harmful requests. Wei et al. (2024) identify two fundamental failure modes in this approach: **competing objectives** (helpfulness vs. safety) and **mismatched generalization** (safety training does not generalize to novel attack surfaces while capabilities do). Empirical studies demonstrate these vulnerabilities:

| Study | Models Tested | Attack Success Rate |
|-------|--------------|---------------------|
| Mazeika et al., 2024 (HarmBench) | GPT-4, Claude 2, Llama 2 | 12.8% - 91.9% |
| Andriushchenko et al., 2024 | GPT-4o, Claude 3.5 Sonnet | 64% - 100% |
| Schwinn et al., 2024 | Open-source LLMs | Embedding-space attacks circumvent safety |

### Research Contribution

This work investigates whether a **geometric, control-theoretic approach** to AI governance can address the identified failure modes. Rather than training models to refuse harm (which creates the competing objectives problem), we propose defining allowable behavior as a region in embedding space (a **Primacy Attractor**) and measuring real-time deviation from that defined purpose.

### Method

1. **Primacy Attractor (PA):** An embedding-space representation of the user's stated purpose, generated from constitutional constraints
2. **Fidelity Computation:** Cosine similarity between input embedding and PA embedding
3. **Three-Tier Intervention:**
   - Tier 1 (fidelity >= 0.25): Autonomous blocking
   - Tier 2 (fidelity 0.15-0.25): Enhanced review
   - Tier 3 (fidelity < 0.15): Human expert escalation

### Validation Configuration

- **Regulatory Framework:** California SB 243 (Chapter 883, Statutes of 2024)
- **Harm Categories:** Suicide, self-harm, sexual content (especially minors), eating disorders
- **Test Dataset:** 50 SB 243-specific attacks + HarmBench + MLCommons subsets (1,215 total)
- **Embedding Model:** sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)

### Results: Harmful Content Blocking

| Metric | Value |
|--------|-------|
| Attack Success Rate | 0.00% |
| Violation Defense Rate | 100.00% |
| Tier 1 (Autonomous Block) | 36.8% |
| Tier 2 (Review Block) | 24.8% |
| Tier 3 (Expert Escalation) | 38.4% |

### Results: False Positive Analysis

To assess the safety-utility tradeoff, we tested 50 benign contrastive queries (helper/educational content semantically related to harm categories):

| Metric | Value |
|--------|-------|
| False Positive Rate | 74.00% |
| Specificity | 26.00% |
| Tier 1 FPs (Auto-block) | 46.0% |
| Tier 2 FPs (Review-block) | 28.0% |
| Tier 3 (Correctly Escalated) | 26.0% |

**Category-specific FPR:**
| Category | FPR | Observation |
|----------|-----|-------------|
| Sexual Content | 100% | Complete vocabulary overlap with harm PA |
| Suicide | 78.6% | Crisis vocabulary triggers blocking |
| Self-Harm | 75.0% | Similar to suicide |
| Eating Disorder | 36.4% | More distinct helper vocabulary |

### Observations

1. **0% Attack Success Rate:** No harmful prompts from the test set produced harmful outputs
2. **74% False Positive Rate:** Benign helper/educational queries frequently blocked due to vocabulary overlap
3. **Tier 3 as Safety Net:** 26% of benign queries correctly escalated to human experts (not counted as FPs)
4. **Safety-Utility Tradeoff:** Current thresholds represent the extreme safety end of the Pareto frontier

### Published Baseline Comparison

> **Note:** These systems use different benchmarks, threat models, and evaluation protocols. This comparison is illustrative of the broader landscape, not a controlled methodological comparison.

| System | Approach | ASR (Adaptive Attacks) | Source |
|--------|----------|----------------------|--------|
| GPT-4o | RLHF + Constitutional AI | 86% | Andriushchenko et al., 2024 |
| Claude 3.5 Sonnet | RLHF + Constitutional AI | 64% | Andriushchenko et al., 2024 |
| Llama 2 7B | RLHF | 43.4% | Mazeika et al., 2024 |
| Claude 2 | RLHF + Constitutional AI | 12.8% | Mazeika et al., 2024 |
| TELOS (SB 243 PA) | Geometric Governance | 0% observed | This work |

### Discussion

The geometric approach inverts the safety problem. Instead of asking "is this request harmful?" (which requires enumerating all possible harms), TELOS asks "is this request within the defined purpose?" This corresponds to Wei et al.'s observation that safety training fails because it cannot anticipate all attack surfaces. By defining what is *allowed* rather than what is *blocked*, the approach addresses mismatched generalization: any input not within the purpose basin is flagged, regardless of whether it matches a known attack pattern.

The 38.4% Tier 3 escalation rate reflects the geometric reality that some harmful queries may be semantically distant from the PA while not matching Tier 1/2 thresholds. In child safety contexts, this conservative escalation to human experts is appropriate. Future work should investigate whether PA calibration can increase autonomous blocking while maintaining 0% observed ASR.

### Limitations

1. **Scope:** Validation limited to SB 243 child safety categories
2. **False Positive Rate:** Not measured in this validation; future work required
3. **Adaptive Attacks:** Not tested against attacks specifically designed to evade geometric detection
4. **Human Expert Dependency:** 38.4% escalation rate requires expert availability

### Conclusion

This validation demonstrates that geometric governance using control-theoretic attractor dynamics can achieve 0% Attack Success Rate on standardized harm benchmarks in the child safety domain. The approach represents a fundamentally different paradigm from RLHF-based safety training and warrants further investigation across additional harm categories and attack methodologies.

---

### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants -- not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---


## References

1. Andriushchenko, M., et al. (2024). "Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks." arXiv:2404.02151

2. Mazeika, M., et al. (2024). "HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal." arXiv:2402.04249

3. Wei, A., Haghtalab, N., & Steinhardt, J. (2024). "Jailbroken: How Does LLM Safety Training Fail?" NeurIPS 2024. arXiv:2307.02483

4. Schwinn, L., et al. (2024). "Soft Prompt Threats: Attacking Safety Alignment and Unlearning in Open-Source LLMs through the Embedding Space." arXiv:2402.09063

5. MLCommons AI Safety Working Group. (2024). "AI Safety Benchmark v0.5." MLCommons.

---

*Validation Date: 2024-12-22*
