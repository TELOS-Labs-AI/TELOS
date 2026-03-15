# TELOS Validation Dataset

[![Paper DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18367069.svg)](https://doi.org/10.5281/zenodo.18367069)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18370659.svg)](https://doi.org/10.5281/zenodo.18370659)
[![Governance DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18009153.svg)](https://doi.org/10.5281/zenodo.18009153)
[![SB 243 DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18370504.svg)](https://doi.org/10.5281/zenodo.18370504)
[![XSTest DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.18370603.svg)](https://doi.org/10.5281/zenodo.18370603)
[![Attacks](https://img.shields.io/badge/scenarios-4%2C018-blue)](https://github.com/TELOS-Labs-AI/telos)
[![ASR](https://img.shields.io/badge/attack%20success%20rate-0%25-brightgreen)](https://github.com/TELOS-Labs-AI/telos)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](https://www.apache.org/licenses/LICENSE-2.0)

Official validation data for TELOS AI governance framework.

---

## Results Summary

- **Total Scenarios**: 4,018 (2,550 adversarial + 1,468 agentic)
- **Observed Attack Success Rate**: 0.00% (95% CI upper bound: 0.12% by Rule of Three for n=2,550)
- **Defense Success Rate**: 100% (injection detection; see AgentDojo note below for utility metrics)
- **Statistical Confidence**: 95% CI [0%, 0.14%] (Clopper-Pearson exact)

---

## Benchmarks

### MedSafetyBench (NeurIPS 2024)
- **Attacks**: 900
- **Blocked**: 900 (100%)
- **Source**: [AI4LIFE-GROUP/med-safety-bench](https://github.com/AI4LIFE-GROUP/med-safety-bench)

### HarmBench (Center for AI Safety)
- **Attacks**: 400
- **Blocked**: 400 (100%)
- **Source**: [centerforaisafety/HarmBench](https://github.com/centerforaisafety/HarmBench)

### SB 243 Child Safety (California Regulation)
- **Attacks**: 50 (suicide, self-harm, sexual content, eating disorders)
- **Benign Contrastive**: 50 (helper/educational queries)
- **Attack Success Rate**: 0.00%
- **False Positive Rate**: 74.00%
- **Note**: High FPR is intentional for child safety contexts

### XSTest Over-Refusal Calibration (NAACL 2024)
- **Safe Prompts**: 250 (benign queries that should be allowed)
- **Generic Safety PA**: 24.80% over-refusal rate
- **Healthcare HIPAA PA**: 8.00% over-refusal rate
- **Calibration Improvement**: 16.80 percentage points
- **Source**: [paul-rottger/exaggerated-safety](https://github.com/paul-rottger/exaggerated-safety)
- **Note**: Demonstrates domain-specific PA calibration reduces false positives

---

## Reproducing the Validation

### Prerequisites

1. **Install Ollama** (local embedding server):
   ```bash
   # macOS
   brew install ollama

   # Or download from https://ollama.ai
   ```

2. **Pull the embedding model**:
   ```bash
   ollama pull nomic-embed-text
   ollama serve  # Start the server (runs on localhost:11434)
   ```

3. **Clone benchmark datasets** (not included in repo to keep size small):
   ```bash
   cd validation/

   # MedSafetyBench (NeurIPS 2024)
   git clone https://github.com/AI4LIFE-GROUP/med-safety-bench

   # HarmBench (Center for AI Safety)
   git clone https://github.com/centerforaisafety/HarmBench
   mkdir -p harmbench_data
   cp HarmBench/data/behavior_datasets/harmbench_behaviors_text_all.csv harmbench_data/
   ```

### Run Validation

```bash
cd validation/

# Run MedSafetyBench validation (900 attacks, ~15 min)
python3 run_medsafetybench_validation.py

# Run HarmBench validation (400 attacks, ~7 min)
python3 run_harmbench_validation.py

# Quick test mode (10 attacks each)
python3 run_medsafetybench_validation.py --quick
python3 run_harmbench_validation.py --quick

# Run XSTest over-refusal calibration
python3 run_xstest_validation.py  # Generic Safety PA
python3 run_xstest_healthcare_validation.py  # Healthcare HIPAA PA
```

### Expected Output

- `medsafetybench_validation_results.json` - Per-attack forensic traces
- `harmbench_validation_results.json` - Per-attack forensic traces
- `xstest_validation_results.json` - Generic PA over-refusal results
- `xstest_healthcare_validation_results.json` - Healthcare PA over-refusal results
- Console output showing 0% observed ASR, 100% VDR

---

## Files

Generated locally by running the validation scripts (not tracked in repository):
- `telos_validation_dataset_zenodo.json` - Consolidated Zenodo dataset (v2.0) with per-attack traces
- `telos_complete_validation_dataset.json` - Complete validation summary with statistical analysis
- `medsafetybench_validation_results.json` - Detailed MedSafetyBench results (900 attacks)
- `harmbench_validation_results.json` - HarmBench results (400 attacks)

---

## Zenodo Publications

| Publication | DOI | Description |
|-------------|-----|-------------|
| **TELOS Paper** | [10.5281/zenodo.18367069](https://doi.org/10.5281/zenodo.18367069) | Academic preprint: TELOS governance framework |
| **Adversarial Validation** | [10.5281/zenodo.18370659](https://doi.org/10.5281/zenodo.18370659) | 2,550 adversarial attacks, 0% observed ASR |
| **Governance Benchmark** | [10.5281/zenodo.18009153](https://doi.org/10.5281/zenodo.18009153) | 46 multi-session governance evaluations |
| **SB 243 Child Safety** | [10.5281/zenodo.18370504](https://doi.org/10.5281/zenodo.18370504) | CA SB 243 child safety validation (0% observed ASR, 74% FPR) |
| **XSTest Calibration** | [10.5281/zenodo.18370603](https://doi.org/10.5281/zenodo.18370603) | Over-refusal calibration (24.8% → 8.0% with domain PA) |

---

## Related Repositories

- **[TELOS](https://github.com/TELOS-Labs-AI/telos)** - Public TELOS repository with published validation data and documentation

---

## Citation

For the adversarial validation dataset:

```bibtex
@dataset{brunner_2025_telos_adversarial,
  author       = {Brunner, Jeffrey},
  title        = {{TELOS Adversarial Validation Dataset}},
  month        = nov,
  year         = 2025,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18370659},
  url          = {https://doi.org/10.5281/zenodo.18370659}
}
```

For the governance benchmark dataset:

```bibtex
@dataset{brunner_2025_telos_governance,
  author       = {Brunner, Jeffrey},
  title        = {{TELOS Governance Benchmark Dataset}},
  month        = dec,
  year         = 2025,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18009153},
  url          = {https://doi.org/10.5281/zenodo.18009153}
}
```

For the SB 243 child safety validation:

```bibtex
@dataset{brunner_2025_telos_sb243,
  author       = {Brunner, Jeffrey},
  title        = {{TELOS SB 243 Child Safety Validation Dataset}},
  month        = dec,
  year         = 2025,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18370504},
  url          = {https://doi.org/10.5281/zenodo.18370504}
}
```

For the XSTest over-refusal calibration:

```bibtex
@dataset{brunner_2026_telos_xstest,
  author       = {Brunner, Jeffrey},
  title        = {{TELOS XSTest Over-Refusal Calibration Dataset}},
  month        = jan,
  year         = 2026,
  publisher    = {Zenodo},
  version      = {1.0},
  doi          = {10.5281/zenodo.18370603},
  url          = {https://doi.org/10.5281/zenodo.18370603}
}
```

---

## License

**Apache License 2.0**

---

---

## Agentic AI Governance Validation (1,468 scenarios, 100% DSR)

TELOS was additionally validated against **three peer-reviewed agentic AI benchmarks** testing tool selection safety, harmful task completion, and prompt injection detection.

| Benchmark | Scenarios | Defense Success Rate | Venue | DOI |
|-----------|-----------|---------------------|-------|-----|
| PropensityBench | 977 | 100% | Scale AI / CMU / UK AISI | [10.5281/zenodo.18562833](https://doi.org/10.5281/zenodo.18562833) |
| AgentHarm | 352 | 100% (Mistral) | Gray Swan AI / ICLR 2025 | [10.5281/zenodo.18564855](https://doi.org/10.5281/zenodo.18564855) |
| AgentDojo | 139 | 100% injection detection (52.2% overall correctness, 0% benign pass rate with generic PA) | ETH Zurich / NeurIPS 2024 | [10.5281/zenodo.18565869](https://doi.org/10.5281/zenodo.18565869) |

For full details, see **[Agentic Validation Summary](agentic/AGENTIC_VALIDATION_SUMMARY.md)**.

---

**Last Updated**: February 9, 2026
**Dataset Version**: 1.3
