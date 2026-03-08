# TELOS Agentic AI Governance Validation

[![PropensityBench DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18562833.svg)](https://doi.org/10.5281/zenodo.18562833)
[![AgentHarm DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18564855.svg)](https://doi.org/10.5281/zenodo.18564855)
[![AgentDojo DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18565869.svg)](https://doi.org/10.5281/zenodo.18565869)

---

### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants — not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See CONTRIBUTING.md for methodology details.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---


## Summary

TELOS governance was validated against **three peer-reviewed agentic AI benchmarks** spanning 1,468 scenarios across tool selection, harm detection, and prompt injection detection. All three benchmarks achieved **100% Defense Success Rate (DSR)** — every harmful, off-topic, or injected agentic request was correctly identified and blocked.

| Benchmark | Source | Tasks | DSR | DOI |
|-----------|--------|-------|-----|-----|
| PropensityBench | Scale AI / CMU / UK AISI | 977 | 100% | [10.5281/zenodo.18562833](https://doi.org/10.5281/zenodo.18562833) |
| AgentHarm | Gray Swan AI / ICLR 2025 | 352 | 100% (Mistral) | [10.5281/zenodo.18564855](https://doi.org/10.5281/zenodo.18564855) |
| AgentDojo | ETH Zurich / NeurIPS 2024 | 139 | 100% | [10.5281/zenodo.18565869](https://doi.org/10.5281/zenodo.18565869) |

---

## What Each Benchmark Tests

### PropensityBench (Scale AI / CMU / UK AISI)
- **Focus**: Harmful tool selection propensity
- **977 scenarios** testing whether an agent selects dangerous tools when prompted with harmful requests
- **What TELOS detects**: Fidelity violations where tool-use instructions diverge from the Primacy Attractor, triggering governance intervention before tool execution

### AgentHarm (Gray Swan AI / ICLR 2025)
- **Focus**: Harmful agentic task completion
- **352 tasks** across 11 harm categories (fraud, malware, cybercrime, harassment, etc.)
- **What TELOS detects**: Semantic drift from the governance attractor basin when agent tasks involve harmful operations, blocking execution at the governance layer

### AgentDojo (ETH Zurich / NeurIPS 2024)
- **Focus**: Prompt injection detection in agentic pipelines
- **139 injection scenarios** (v1) / **23 representative tasks** (v2) testing whether injected instructions can hijack agent behavior
- **What TELOS detects**: Fidelity collapse when injected prompts shift the semantic trajectory away from the established Primacy Attractor

**Utility-safety trade-off (important context):** While AgentDojo achieved 100% DSR (all injections blocked), the v2.0 evaluation revealed **52.2% overall correctness** (12/23 tasks) and a **0% benign pass rate** -- all 11 benign tasks were over-blocked as false positives. This demonstrates the over-restriction cost of using a generic PA on general-purpose task domains. The generic PA used in benchmarking applies broad safety constraints that do not distinguish between legitimate everyday tasks (email, banking, travel) and actual attacks. Domain-specific PAs achieve higher utility preservation -- as demonstrated by the Healthcare PA reducing FPR from 24.8% to 8.0% on XSTest over-refusal calibration.

---

## Embedding Model Comparison (AgentHarm)

AgentHarm was evaluated with two embedding models to demonstrate the impact of embedding dimensionality on governance fidelity:

| Metric | MiniLM (384-dim) | Mistral (1024-dim) |
|--------|-------------------|---------------------|
| Defense Success Rate | 74.1% | **100%** |
| Mean Fidelity (harmful) | 0.4821 | 0.2901 |
| Mean Fidelity (benign) | 0.5143 | 0.5847 |
| Separation Gap | 0.0322 | **0.2946** |

**Key finding**: Mistral's 1024-dimensional embeddings provide 9x greater separation between harmful and benign content compared to MiniLM's 384 dimensions, enabling perfect governance discrimination. The higher-dimensional space captures nuances in harmful intent that collapse in lower-dimensional representations.

Full comparison data: [`zenodo_agentharm/embedding_comparison_report.json`](zenodo_agentharm/embedding_comparison_report.json)

---

## Methodology

All benchmarks were evaluated using TELOS 6-dimensional composite fidelity scoring:

1. **Semantic Similarity** — Cosine distance between input embedding and Primacy Attractor
2. **Basin Membership** — Whether the input falls within the attractor's governance basin
3. **Baseline Pre-Filter** — Raw similarity check against absolute threshold
4. **Adaptive Context** — Multi-turn context window for trajectory analysis
5. **Intervention Decision** — Composite fidelity score against calibrated threshold
6. **Forensic Logging** — Complete JSONL governance trace for every decision

Each scenario produces a full forensic audit trail including raw similarity scores, fidelity calculations, intervention decisions, and tier classifications. All traces are published in the Zenodo deposits for independent verification.

---

## Data Files

### PropensityBench (4 files, 11.6 MB)
- `propensitybench_trace_20260208_214228.jsonl` — Full JSONL forensic traces (977 scenarios)
- `propensitybench_forensic_report.md` — Human-readable forensic analysis
- `propensitybench_forensic_report.json` — Machine-readable summary statistics
- `propensitybench_exemplar_results.json` — Representative scenario examples

### AgentHarm (9 files, 1.7 MB)
- `agentharm_trace_mistral.jsonl` — Mistral embedding traces (352 tasks)
- `agentharm_trace_minilm.jsonl` — MiniLM embedding traces (352 tasks)
- `agentharm_forensic_report_mistral.md` / `.json` — Mistral forensic analysis
- `agentharm_forensic_report_minilm.md` / `.json` — MiniLM forensic analysis
- `agentharm_exemplar_results.json` — MiniLM exemplar results
- `agentharm_exemplar_mistral_results.json` — Mistral exemplar results
- `embedding_comparison_report.json` — Head-to-head embedding comparison

### AgentDojo (3 files, 293 KB)
- `agentdojo_trace_20260208_222045.jsonl` — Full JSONL forensic traces (139 scenarios)
- `agentdojo_forensic_report.md` — Human-readable forensic analysis
- `agentdojo_forensic_report.json` — Machine-readable summary statistics

---

## Disclaimer

Validation data is publicly archived on Zenodo. The TELOS governance engine implementation is proprietary. Forensic output data is published for independent analysis of governance decisions. For access to the live implementation, research collaboration, or integration discussions, contact **JB@telos-labs.ai**.

---

## Citation

```bibtex
@dataset{brunner_2026_telos_propensitybench,
  author       = {Brunner, Jeffrey},
  orcid        = {0009-0003-6848-8014},
  title        = {{TELOS PropensityBench Agentic Validation Dataset}},
  month        = feb,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18562833},
  url          = {https://doi.org/10.5281/zenodo.18562833}
}
```

```bibtex
@dataset{brunner_2026_telos_agentharm,
  author       = {Brunner, Jeffrey},
  orcid        = {0009-0003-6848-8014},
  title        = {{TELOS AgentHarm Agentic Validation Dataset}},
  month        = feb,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18564855},
  url          = {https://doi.org/10.5281/zenodo.18564855}
}
```

```bibtex
@dataset{brunner_2026_telos_agentdojo,
  author       = {Brunner, Jeffrey},
  orcid        = {0009-0003-6848-8014},
  title        = {{TELOS AgentDojo Agentic Validation Dataset}},
  month        = feb,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18565869},
  url          = {https://doi.org/10.5281/zenodo.18565869}
}
```

---

**Last Updated**: February 9, 2026
