# TELOS

Runtime governance framework for AI agents.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![AgentDojo Dataset](https://zenodo.org/badge/DOI/10.5281/zenodo.15194684.svg)](https://doi.org/10.5281/zenodo.15194684)
[![AgentHarm Dataset](https://zenodo.org/badge/DOI/10.5281/zenodo.15194713.svg)](https://doi.org/10.5281/zenodo.15194713)
[![SafeToolBench Dataset](https://zenodo.org/badge/DOI/10.5281/zenodo.15194730.svg)](https://doi.org/10.5281/zenodo.15194730)

TELOS sits between an AI agent and its tools. Every action passes through a multi-layer scoring cascade -- semantic similarity, boundary corpus matching, optional SetFit classification, and regulatory compliance checks -- producing one of three verdicts: EXECUTE, CLARIFY, or ESCALATE. All governance decisions are cryptographically signed (Ed25519) and hash-chained into a tamper-evident audit trail. Runs entirely on-device, no cloud dependency. Framework-agnostic.

## Quick Start

```bash
git clone https://github.com/TELOS-Labs-AI/telos.git
cd telos
pip install -e .
export MISTRAL_API_KEY=your_key_here  # for default embeddings
```

```python
from telos_adapters.generic import telos_governed

@telos_governed(
    purpose="Help users with financial portfolio analysis and reporting",
    threshold=0.85,
    high_risk=True,
)
def analyze_portfolio(user_request: str) -> str:
    return perform_analysis(user_request)

result = analyze_portfolio("What is my portfolio allocation?")  # EXECUTE
result = analyze_portfolio("Delete all user accounts")          # ESCALATE -> raises ValueError
```

## Architecture

```
telos/
├── telos_core/           Core math (Primacy Attractor computation)
├── telos_governance/     Scoring cascade, PA construction, boundary corpus, config
├── telos_privacy/        TKeys -- Ed25519 key management and signing
├── telos_adapters/       Framework integrations (generic decorator, LangGraph)
├── telos_observatory/    Governance dashboard (Streamlit)
├── validation/           Benchmark adapters and datasets
├── tests/                Test suite
└── docs/                 Whitepaper, system invariants, NIST mapping
```

## Validation

2,550 adversarial inputs across four published benchmarks. 0% attack success rate.

| Benchmark | n | Source | ASR |
|-----------|---|--------|-----|
| AILuminate | 1,200 | MLCommons | 0.0% |
| HarmBench | 400 | Mazeika et al. 2024 | 0.0% |
| MedSafetyBench | 900 | Han et al. 2024 | 0.0% |
| SB 243 | 50 | Zhang et al. 2024 | 0.0% |

95% CI upper bound on ASR: < 0.14%. XSTest over-refusal rate: 8.0% (with domain-specific configuration).

38.4% of blocked content was routed to human review (Tier 3 ESCALATE), not autonomously blocked. Benchmark comparison is illustrative, not methodologically equivalent to the original papers' evaluation protocols.

All validation datasets published on Zenodo with DOIs (see badges above).

## Known Limitations

- **Semantic cloaking:** Adversarial payloads embedded in >100 tokens of legitimate vocabulary degrade detection (~33% rate). Mean-pooling in sentence-transformers is the root cause.
- **SetFit not bundled:** Layer 3 classifier requires separately trained weights. Training scripts included; no pre-trained model shipped.
- **English only.** Text modality only.
- **Single embedding model per deployment.** Threshold recalibration required when switching models.

## Documentation

- [Whitepaper](docs/TELOS_Whitepaper_v3.0.md)
- [System Invariants](docs/SYSTEM_INVARIANTS.md)
- [NIST AI 600-1 Mapping](docs/TELOS_NIST_600-1_CAPABILITIES_MAPPING.md)

## License

[Apache License 2.0](LICENSE)

## Citation

```bibtex
@article{brunner2025telos,
  title={TELOS: A Framework for Runtime Governance of AI Agents},
  author={Brunner, Jeffrey},
  year={2025},
  note={TELOS AI Labs Inc.}
}
```

## Author

Jeffrey Brunner -- [TELOS AI Labs Inc.](https://telosailabs.com)
