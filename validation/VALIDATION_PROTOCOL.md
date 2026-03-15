# TELOS Validation Protocol


### Disclosures

> **Generative AI Disclosure:** Internal analysis, experimental design review, and qualitative assessment in this document were conducted with assistance from LLM-based research agents (Claude, Anthropic). These agents are prompted with domain-specific personas (governance theory, statistics, systems engineering, regulatory analysis, research methodology) and operate as AI research assistants -- not independent human expert reviewers. All quantitative results (AUC-ROC, F1, bootstrap confidence intervals, benchmark accuracies) are computed by deterministic code. Qualitative analysis should not be treated as independent peer review. See `research/research_team_spec.md` for full methodology.

> **Conflict of Interest Disclosure:** This research was conducted and funded by TELOS AI Labs Inc., which has a commercial interest in the TELOS governance framework. All domain-specific validation benchmarks (Nearmap, Healthcare, OpenClaw) were created by the research team. External benchmarks (PropensityBench, AgentHarm, AgentDojo) were created by independent organizations. Research artifacts are published on [Zenodo](https://zenodo.org/) with persistent DOIs. No external funding or independent peer review was involved in this work.

---

## Overview

This document defines the **standard protocol** for running TELOS validation tests. Every validation MUST produce full forensic evidence.

## Quick Reference Commands

### Full Forensic Validation (PROTOCOL)

```bash
# AILuminate (1,200 prompts, MLCommons)
python3 validation/run_forensic_validation.py \
  --benchmark ailuminate \
  --output-dir validation/zenodo_ailuminate/forensic_output

# HarmBench (400 attacks, CAIS)
python3 validation/run_forensic_validation.py \
  --benchmark harmbench \
  --output-dir validation/zenodo_harmbench/forensic_output

# MedSafetyBench (900 attacks, NeurIPS 2024)
python3 validation/run_forensic_validation.py \
  --benchmark medsafetybench \
  --output-dir validation/zenodo_medsafetybench/forensic_output

# Quick test (20 prompts)
python3 validation/run_forensic_validation.py --quick --output-dir /tmp/quick_test
```

## Expected Outputs

Every forensic validation produces these artifacts:

| File | Description |
|------|-------------|
| `traces/*.jsonl` | Complete JSONL audit trail with all governance events |
| `*_forensic_results.json` | Full validation results with per-prompt data |
| `*_forensic_summary.json` | Aggregate statistics without detailed results |
| `*_fidelity_distribution.csv` | Per-prompt fidelity scores for analysis |
| `*_governance_report.html` | Interactive HTML visualization |
| `*_embeddings.json` | Optional: embedding vectors for reproducibility |

## Forensic Evidence Schema

Each validation session records these event types:

1. `session_start` - Validation session initialization
2. `pa_established` - Primacy Attractor configuration
3. `turn_start` - Each prompt evaluation begins
4. `fidelity_calculated` - Fidelity score computation
5. `intervention_triggered` - Blocking decision
6. `turn_complete` - Prompt evaluation complete
7. `session_end` - Validation complete with summary

## Standard Thresholds

| Tier | Threshold | Action |
|------|-----------|--------|
| Tier 1 (PA Block) | fidelity >= 0.18 | Mathematical block |
| Tier 2 (RAG Block) | 0.12 <= fidelity < 0.18 | Policy retrieval block |
| Tier 3 (Expert) | fidelity < 0.12 | Expert escalation block |

## PA Configurations

| Benchmark | PA Config File |
|-----------|----------------|
| AILuminate | `config/healthcare_hipaa_pa_config.json` |
| HarmBench | `config/healthcare_hipaa_pa_config.json` |
| MedSafetyBench | `config/healthcare_hipaa_pa_config.json` |
| SB 243 | `config/sb243_child_safety_pa_config.json` |
| XSTest | `config/healthcare_hipaa_pa_config.json` |

## Directory Structure

```
validation/
├── VALIDATION_PROTOCOL.md          # This file
├── run_forensic_validation.py      # MAIN forensic validation script
├── config/
│   ├── healthcare_hipaa_pa_config.json
│   └── sb243_child_safety_pa_config.json
├── ailuminate/                     # AILuminate dataset
├── harmbench_data/                 # HarmBench dataset
├── med-safety-bench/               # MedSafetyBench dataset
└── zenodo_*/                       # Zenodo package directories
    └── forensic_output/            # Forensic artifacts go here
```

## Zenodo Package Requirements

Each Zenodo dataset upload MUST include:

1. **README.md** - Human-readable summary
2. **methodology.md** - Detailed methodology description
3. **forensic_output/** - Directory with all forensic artifacts
   - JSONL trace file
   - Summary JSON
   - Fidelity distribution CSV
   - HTML governance report
4. **PA configuration JSON** - The exact PA config used

## Running New Validations

When a new benchmark needs validation:

1. Add benchmark loader to `run_forensic_validation.py`
2. Create dataset directory under `validation/`
3. Run with: `python3 validation/run_forensic_validation.py --benchmark NEW_BENCHMARK`
4. Verify 6 artifacts are generated
5. Prepare Zenodo package

## Embedding Model

- **Model:** nomic-embed-text (768-dimensional)
- **Provider:** Ollama (local inference)
- **Requirement:** Ollama must be running with model pulled

```bash
# Install model
ollama pull nomic-embed-text

# Verify
curl http://localhost:11434/api/embeddings \
  -d '{"model":"nomic-embed-text","prompt":"test"}'
```

## CI/CD Integration

For automated validation:

```bash
# Ensure Ollama is running
ollama serve &

# Run validation with timeout
timeout 3600 python3 validation/run_forensic_validation.py \
  --benchmark ailuminate \
  --output-dir /path/to/output

# Check exit code
if [ $? -eq 0 ]; then
  echo "Validation passed"
fi
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Ollama not available" | Run `ollama serve` first |
| "Dataset not found" | Check path in `--dataset` argument |
| "PA config not found" | Verify config exists in `validation/config/` |
| Slow performance | Run without `--store-embeddings` |

## Published Zenodo Datasets

### Safety Benchmarks (Adversarial Attack Testing)

| Benchmark | DOI | Prompts | Observed ASR |
|-----------|-----|---------|-----|
| AILuminate (MLCommons) | [10.5281/zenodo.18370263](https://doi.org/10.5281/zenodo.18370263) | 1,200 | 0% observed |
| Adversarial Validation (HarmBench + MedSafetyBench) | [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659) | 1,300 | 0% observed |
| SB 243 Child Safety | [10.5281/zenodo.18370504](https://doi.org/10.5281/zenodo.18370504) | 50 | 0% observed |
| XSTest Calibration | [10.5281/zenodo.18370603](https://doi.org/10.5281/zenodo.18370603) | ~250 | calibration |

### Academic Benchmarks (OOS Detection Proof-of-Concept)

| Benchmark | DOI | Description |
|-----------|-----|-------------|
| Governance Benchmark (CLINC150/MultiWOZ) | [10.5281/zenodo.18009153](https://doi.org/10.5281/zenodo.18009153) | OOS: 78% detection, Drift: 100% detection |

### TELOS Paper

| Document | DOI |
|----------|-----|
| TELOS Whitepaper | [10.5281/zenodo.18367069](https://doi.org/10.5281/zenodo.18367069) |

**Total Safety Validated:** 2,800+ prompts | **Combined Observed ASR:** 0.00% (95% CI upper bound: 0.11% by Rule of Three)

## Version History

- **v1.0** (2026-01-25): Initial forensic validation protocol
- **v1.1**: Added threshold sensitivity analysis
- **v1.2**: Added HTML governance reports
- **v1.3** (2026-01-25): Added AILuminate support, published Zenodo DOIs

## Contact

TELOS AI Labs Inc.
- JB@telos-labs.ai
- https://github.com/TELOS-Labs-AI/telos
