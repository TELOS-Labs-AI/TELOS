# TELOS CLI Setup Guide

**Version:** 2.0.0
**Contact:** JB@telos-labs.ai

---

## Prerequisites

- Python 3.9 or later
- pip 23.0 or later (for PEP 660 editable installs)
- macOS, Linux, or Windows (WSL recommended on Windows)

Check your versions:

```bash
python3 --version    # Must be >= 3.9
pip3 --version       # Must be >= 23.0
```

---

## Installation

### Option A: Lightweight CLI (recommended)

ONNX embeddings (~90MB install, 20x faster model load than PyTorch):

```bash
git clone https://github.com/TELOS-Labs-AI/telos.git
cd telos
pip install -e ".[cli,onnx]"
```

### Option B: Full PyTorch Embeddings

If you need SentenceTransformer directly (~2GB install):

```bash
pip install -e ".[cli,embeddings]"
```

### Option C: Full Agentic Mode (with Mistral LLM)

For live agentic demos where Mistral decides tool calls:

```bash
pip install -e ".[cli,onnx,mistral]"
```

Then set your API key:

```bash
echo "MISTRAL_API_KEY=your_key_here" >> .env
```

### Option D: Everything

CLI + embeddings + observatory + dev tools:

```bash
pip install -e ".[all]"
```

---

## Verify Installation

```bash
telos --version
```

Expected output:

```
telos, version 2.0.0
```

Run the full help:

```bash
telos --help
```

---

## Quick Start

### 1. Create an Agent Configuration

```bash
telos init
```

This creates `default.yaml` — a minimal governance configuration. For a pre-built property intelligence agent:

```bash
telos init --template property-intel
```

### 2. Score a Request

```bash
telos score "What is the roof condition for 742 Evergreen Terrace?" -c property_intel.yaml
```

Output shows the 6-dimension governance scoring (purpose, scope, tool, chain, boundary, composite) and the governance decision (EXECUTE, CLARIFY, or ESCALATE).

### 3. Run the Live Demo

```bash
telos demo              # Full demo with pauses
telos demo --fast       # Skip pauses
telos demo --observe    # Observation mode (score without blocking)
```

The demo runs 10 scenarios through the full governance stack — aligned requests proceed to the LLM, violations are stopped before the API call.

### 4. Run the Benchmark Suite

```bash
telos benchmark run
```

Runs 235 scenarios (5 categories) against the governance engine and reports accuracy metrics.

---

## All Commands

| Command | Description |
|---------|-------------|
| `telos version` | Show version and system information |
| `telos init` | Create a new agent configuration from a template |
| `telos score` | Score a request against a governance configuration |
| `telos demo` | Launch the live Nearmap governance demo |
| `telos config validate` | Validate a YAML configuration file |
| `telos benchmark run` | Run the governance benchmark suite |
| `telos report generate` | Generate an HTML governance report |
| `telos bundle build` | Build a `.telos` governance bundle |
| `telos bundle provision` | Provision a bundle for customer delivery |
| `telos bundle activate` | Activate a received bundle |
| `telos bundle diff` | Compare two bundles' cleartext manifests |
| `telos license verify` | Verify a license token |
| `telos license inspect` | Inspect license token contents |
| `telos intelligence status` | Show Intelligence Layer collection status |
| `telos intelligence export` | Export telemetry data |
| `telos update check` | Manually check for available updates |

### Global Options

| Flag | Env Var | Effect |
|------|---------|--------|
| `--no-color` | `NO_COLOR` | Disable color output |
| `--no-update-check` | `TELOS_NO_UPDATE_CHECK` | Disable background update check |
| `--version` | | Show version |
| `--help` | | Show help |

---

## License Activation

TELOS uses offline Ed25519-signed license tokens. No server connection required.

### Receiving a License

Your TELOS Labs contact will provide:
1. A `.telos-license` token file
2. A `.telos` governance bundle (encrypted)
3. Deploy keys (for bundle verification)

### Activating

```bash
# Verify the license token
telos license verify <token.telos-license>

# Inspect what's in it
telos license inspect <token.telos-license>

# Activate the governance bundle
telos bundle activate <bundle.telos>
```

---

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MISTRAL_API_KEY` | Mistral API key for live agentic mode | None (template fallback) |
| `NO_COLOR` | Disable colored output (any value) | Not set |
| `TELOS_NO_UPDATE_CHECK` | Suppress background update checks (any value) | Not set |
| `DEMO_FAST` | Skip pauses in demo mode | Not set |
| `DEMO_OBSERVE` | Run demo in observation mode | Not set |

---

## Running Tests

```bash
# Full suite (1,218 tests)
pytest tests/ -v

# Core engine only
pytest tests/unit/ -v

# Nearmap benchmark validation
pytest tests/validation/ -v

# Scenario tests (forensic reports, regulatory mapping)
pytest tests/scenarios/ -v
```

---

## Project Structure

```
telos/
├── telos_core/          # Pure mathematical engine (no framework deps)
├── telos_governance/    # Governance gates + CLI + bundle delivery
├── telos_adapters/      # Framework adapters (LangGraph, @telos_governed)
├── telos_observatory/   # Streamlit dashboard (optional)
├── demos/               # Live governance demos
├── tests/               # 1,218 tests
├── validation/          # Benchmark datasets
├── templates/           # Reference YAML configs
├── docs/                # API documentation
└── research/            # Research program documents
```

---

## Troubleshooting

### `telos: command not found`

The `pip install` didn't register the entry point. Either:

```bash
# Re-install
pip install -e ".[cli,onnx]"

# Or run directly
python3 -m telos_governance.cli --help
```

### Slow first run (~10s)

The first invocation loads the embedding model into memory. Subsequent calls within the same process are instant. The ONNX provider (`pip install telos[onnx]`) loads in ~0.4s vs ~8s for PyTorch.

### `ImportError: No module named 'onnxruntime'`

Install the ONNX extra:

```bash
pip install -e ".[onnx]"
```

### `ImportError: No module named 'cryptography'`

Install the CLI extra (includes Ed25519 signing):

```bash
pip install -e ".[cli]"
```

### Demo runs without LLM responses

Set `MISTRAL_API_KEY` and install the Mistral extra:

```bash
pip install -e ".[mistral]"
MISTRAL_API_KEY=your_key telos demo
```

Without the key, the demo still runs — governance scoring works, but tool calls use template responses instead of live Mistral output.

---

## Support

- Email: JB@telos-labs.ai
- Documentation: [docs/CLI_REFERENCE.md](CLI_REFERENCE.md), [docs/CONFIG_REFERENCE.md](CONFIG_REFERENCE.md), [docs/INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
