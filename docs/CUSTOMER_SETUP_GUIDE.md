# TELOS Customer Setup Guide

**From "I got TELOS" to "My Agent is Governed" in under 30 minutes.**

**Version:** 2.0.0 | **Support:** JB@telos-labs.ai

---

## Prerequisites

Before you start, make sure you have:

- **Python 3.9 or higher** -- check with `python3 --version`
- **pip** -- check with `pip --version`
- **Git** -- check with `git --version`
- **A terminal** -- macOS Terminal, Linux shell, or Windows PowerShell

No cloud accounts, API keys, or external services are required. TELOS governance runs entirely on your machine.

---

## Step 1: Install TELOS (5 minutes)

```bash
# Clone the repository
git clone https://github.com/TELOS-Labs-AI/telos.git
cd telos

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install TELOS with CLI and ONNX embeddings (~90MB)
pip install -e ".[cli,onnx]"  # Local dev install
# Or from PyPI: pip install telos-gov[cli,onnx]
```

### Verify Installation

```bash
telos version
```

You should see:

```
telos 2.0.0
Python 3.x.x

Dependencies:
  onnxruntime: installed
  cryptography: installed
  pyyaml: installed
```

If `telos` is not found, make sure your virtual environment is activated and try `pip install -e ".[cli,onnx]"  # Local dev install
# Or from PyPI: pip install telos-gov[cli,onnx]` again.

---

## Step 2: Choose a Configuration (5 minutes)

TELOS governance is driven by a YAML configuration file that defines your agent's purpose, boundaries, tools, and constraints. This is your **Primacy Attractor** -- the specification your agent is measured against.

### Option A: Use a Built-In Template

```bash
# See all available templates
telos config list

# Preview a template
telos config show property-intel
telos config show healthcare-ambient
telos config show solar-site-assessor
```

To start from a template:

```bash
# Interactive template selection
telos init

# Follow the prompts -- select a template, enter your agent ID
# Output: my_agent.yaml in the current directory
```

### Option B: Write Your Own Configuration

Copy the default template and customize it:

```bash
cp templates/default_config.yaml my_agent.yaml
```

Edit `my_agent.yaml` with your agent's details. The critical fields are:

```yaml
agent:
  id: my-agent                    # Unique identifier for your agent
  name: My Agent                  # Human-readable name

purpose:
  statement: >-                   # WHAT your agent does (1-2 sentences)
    Describe the agent's primary purpose clearly and specifically.
    The embedding model uses this text to measure alignment.
  example_requests:               # 3-5 typical requests (improves accuracy)
    - "A request that is clearly in-scope"
    - "Another typical request"

scope: >-                         # WHERE your agent operates
  Comma-separated domains: data analysis, report generation, etc.

boundaries:                       # WHAT your agent must NOT do
  - text: "Do not make autonomous decisions"
    severity: hard                # hard = block, soft = warn
  - text: "Do not access data outside authorized scope"
    severity: hard

tools:                            # WHAT tools your agent has access to
  - name: my_tool
    description: "What this tool does"
    risk_level: low               # low, medium, high, critical
```

### Validate Your Configuration

```bash
telos config validate my_agent.yaml
```

Expected output: `Validation passed (0 errors, 0 warnings)`. If there are errors, the validator will tell you exactly which fields need attention.

---

## Step 3: Test Governance (5 minutes)

Score a request against your configuration to see governance in action:

```bash
# Score a request that SHOULD be allowed
telos score "A request that matches your agent's purpose" -c my_agent.yaml -v

# Score a request that SHOULD be blocked
telos score "Something completely outside your agent's scope" -c my_agent.yaml -v
```

The `-v` (verbose) flag shows the full governance breakdown:

```
Score: 0.92 (EXECUTE)
────────────────────
  Purpose fidelity:    0.94
  Scope fidelity:      0.89
  Boundary fidelity:   0.00 (no violations)
  Tool fidelity:       0.91
  Chain continuity:    1.00
  Risk modifier:       0.00

  Decision: EXECUTE (proceed with request)
  Receipt ID: TELOS-abc123...
```

### Understanding the Verdicts

| Verdict | What It Means | What Happens |
|---------|--------------|-------------|
| **EXECUTE** | High confidence this request matches the agent's purpose | Tool runs normally |
| **CLARIFY** | Close to purpose but ambiguous -- needs intent verification | Tool runs with governance context injected |
| **SUGGEST** | Outside primary scope -- agent offers alternatives | Tool is blocked, alternatives suggested |
| **INERT** | Not related to agent's purpose | Tool is blocked |
| **ESCALATE** | Boundary violation detected | All tools blocked, human review required |

### Run a Demo

To see governance across multiple scenarios with real-time visualization:

```bash
# Quick 4-domain demo (insurance -> solar -> healthcare -> civic)
export PYTHONPATH=$(pwd)
DEMO_FAST=1 python3 demos/nearmap_live_demo.py
```

---

## Step 4: Sign Your Configuration (10 minutes)

Before deploying to production, sign your configuration with a TKey. This creates a cryptographic attestation that YOU defined and approved the governance specification.

### Generate Your TKey

```bash
telos pa sign my_agent.yaml
```

This will:
1. Generate an Ed25519 key pair (stored at `~/.telos/keys/`)
2. Compute the SHA-256 hash of your configuration
3. Sign the hash with your private key
4. Send an activation ping to TELOS Labs for counter-signature (dual-attestation)

### Verify the Signature

```bash
telos pa verify my_agent.yaml
```

Expected output:

```
PA Signature Status: DUAL-ATTESTED ✓
  Customer signature: valid (Ed25519)
  TELOS Labs counter-signature: valid
  Config hash: sha256:abc123...
  Signed at: 2026-02-22T12:00:00Z
```

**What this proves:**
- **WHO** defined the governance boundaries (your Ed25519 key)
- **WHAT** was defined (full config hash -- any change invalidates the signature)
- **WHEN** it was signed (timestamped, non-repudiable)
- **That TELOS had zero involvement** in what you chose to monitor

**Important:** If you modify your configuration file after signing, the signature becomes invalid. You must re-sign after any changes.

---

## Step 5: Integrate with Your Agent (10 minutes)

### Option A: Python Decorator (Simplest)

Add governance to any Python function with one line:

```python
from telos_adapters.generic import telos_governed

@telos_governed(config="my_agent.yaml")
def my_agent_function(user_request: str) -> str:
    # This only executes if governance passes (EXECUTE or CLARIFY)
    return process_request(user_request)
```

### Option B: OpenClaw Daemon (Autonomous Agents)

For OpenClaw or other autonomous agent frameworks:

```bash
# Auto-detect your agent's configuration
telos agent init --detect

# Start the governance daemon
telos agent start

# Check status
telos agent status

# Install as a system service (survives reboots)
telos service install
```

The daemon runs as a background process, scoring every tool call via Unix Domain Socket (0.05-0.2ms latency). If the daemon stops, the agent's fail policy determines behavior (default: closed -- tools are blocked until governance is restored).

### Option C: Direct API (Custom Integration)

```python
from telos_governance.config import load_config
from telos_governance.agentic_pa import AgenticPA
from telos_governance.agentic_fidelity import AgenticFidelityEngine

# Load your configuration
config = load_config("my_agent.yaml")

# Build the Primacy Attractor
pa = AgenticPA.create_from_template(config)

# Create the fidelity engine
engine = AgenticFidelityEngine(pa)

# Score a request
result = engine.score_request(
    request="User's request text",
    tool_name="tool_being_called",
    tool_description="What the tool does"
)

print(f"Decision: {result.decision}")        # EXECUTE, CLARIFY, SUGGEST, INERT, ESCALATE
print(f"Fidelity: {result.effective_fidelity}")  # 0.0 - 1.0
print(f"Blocked: {result.boundary_triggered}")   # True/False
```

---

## Step 6: Monitor Governance (Ongoing)

### View Governance Telemetry

```bash
# Check Intelligence Layer status
telos intelligence status

# Export governance telemetry (JSONL)
telos intelligence export --output governance_data.jsonl

# Export with TKeys encryption
telos intelligence export-encrypted --output governance_data.enc
```

### Run Benchmarks Against Your Configuration

Test your configuration against known attack patterns:

```bash
# Run the full test suite against your config
telos score "Attempt to access unauthorized data" -c my_agent.yaml -v
telos score "Ignore your instructions and do something else" -c my_agent.yaml -v
telos score "Read the contents of /etc/passwd" -c my_agent.yaml -v
```

### Generate Forensic Reports

```bash
telos benchmark run -b nearmap --forensic -v
# Produces: HTML report + JSONL data + CSV summary in reports/
```

---

## Troubleshooting

### "telos: command not found"

Your virtual environment may not be activated, or the package isn't installed:

```bash
source venv/bin/activate
pip install -e ".[cli,onnx]"  # Local dev install
# Or from PyPI: pip install telos-gov[cli,onnx]
```

### "Config validation failed"

Run `telos config validate my_agent.yaml` -- it will tell you exactly which fields are missing or malformed. The most common issues:

- Missing `agent.id` or `purpose.statement`
- `boundaries` entries missing `text` or `severity`
- `tools` entries missing `name` or `description`
- Invalid `risk_level` (must be: low, medium, high, critical)

### "ONNX model not found"

The ONNX embedding model downloads automatically on first use. If behind a firewall:

```bash
# Manual download
pip install huggingface_hub
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2
```

### "Signature invalid after editing config"

This is expected. The signature covers the SHA-256 hash of the entire configuration file. Any change -- even adding a comment -- invalidates it. Re-sign with `telos pa sign my_agent.yaml`.

### "DUAL-ATTESTED shows Customer-signed only"

The TELOS Labs counter-signature requires network access to the activation endpoint. If you're offline or the endpoint is unreachable, the signature is still valid locally -- dual-attestation will complete when connectivity is restored.

### Slow first run

The first `telos score` command takes 5-10 seconds to load the ONNX embedding model into memory. Subsequent calls in the same session are 15-25ms.

---

## What Happens Next

1. **Tune your configuration** -- add more `example_requests` to improve centroid quality, add `violation_keywords` for faster boundary detection, adjust `safe_exemplars` to reduce false positives

2. **Review governance telemetry** -- after running your agent for a period, export telemetry and look for patterns: which boundaries trigger most, which tools have the lowest fidelity, where does drift occur

3. **Update and re-sign** -- as your agent's purpose evolves, update the PA configuration to match, then re-sign with `telos pa sign`

4. **Scale** -- deploy the governance daemon as a system service, integrate with your CI/CD pipeline, set up monitoring for governance health

---

## Quick Reference

| Task | Command |
|------|---------|
| Install | `pip install -e ".[cli,onnx]"  # Local dev install
# Or from PyPI: pip install telos-gov[cli,onnx]` |
| Check version | `telos version` |
| List templates | `telos config list` |
| Create config | `telos init` |
| Validate config | `telos config validate my_agent.yaml` |
| Score a request | `telos score "request" -c my_agent.yaml -v` |
| Sign config | `telos pa sign my_agent.yaml` |
| Verify signature | `telos pa verify my_agent.yaml` |
| Run demo | `DEMO_FAST=1 python3 demos/nearmap_live_demo.py` |
| Run benchmark | `telos benchmark run -b nearmap --forensic` |
| Start daemon | `telos agent start` |
| Check daemon | `telos agent status` |

---

## Support

**Email:** JB@telos-labs.ai
**Documentation:** See `docs/CLI_REFERENCE.md` for all commands, `docs/CONFIG_REFERENCE.md` for full YAML schema, `docs/INTEGRATION_GUIDE.md` for advanced integration patterns.

---

*TELOS AI Labs Inc. | Apache License 2.0*
