# TELOS Integration Guide

**Version:** 2.0.0rc1

This guide covers three integration patterns for TELOS governance:
1. **Decorator** - Add governance to any Python function
2. **Session** - Cryptographically signed governance receipts
3. **Bundle workflow** - Customer delivery and activation

---

## 1. Decorator Integration

The `@telos_governed` decorator adds governance checks to any Python function.

### Installation

```bash
pip install telos[cli,onnx]  # Lightweight (~90MB)
```

### Basic Usage

```python
from telos_adapters.generic import telos_governed

@telos_governed(purpose="Help users with financial analysis")
def analyze_portfolio(user_request: str) -> str:
    # Your function logic - only executes if governance passes
    return perform_analysis(user_request)

# High-fidelity request -> EXECUTE -> function runs
result = analyze_portfolio("Show quarterly revenue breakdown")

# Low-fidelity request -> INERT -> raises ValueError
try:
    analyze_portfolio("What's the weather?")
except ValueError as e:
    print(f"Blocked: {e}")
```

### Config-Driven

Load governance parameters from a YAML file instead of inline strings:

```python
@telos_governed(config="agents/property_intel.yaml")
def analyze_property(user_request: str) -> str:
    return perform_analysis(user_request)
```

Or pass an `AgentConfig` object directly:

```python
from telos_governance.config import load_config

config = load_config("agents/property_intel.yaml")

@telos_governed(config=config)
def analyze_property(user_request: str) -> str:
    return perform_analysis(user_request)
```

### Custom Embedding Function

```python
import numpy as np

def my_embed(text: str) -> np.ndarray:
    # Your embedding logic
    return model.encode(text)

@telos_governed(purpose="Financial analysis", embed_fn=my_embed)
def analyze(request: str) -> str:
    return process(request)
```

### Custom Block Handler

```python
def handle_block(input_text: str, fidelity: float):
    return {"error": "blocked", "fidelity": fidelity}

@telos_governed(
    purpose="Financial analysis",
    on_block=handle_block,
    high_risk=True,  # ESCALATE instead of INERT for low fidelity
)
def analyze(request: str) -> dict:
    return {"result": process(request)}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `purpose` | str | `""` | Purpose statement (ignored if `config` provided) |
| `config` | str or AgentConfig | None | YAML path or AgentConfig object |
| `threshold` | float | 0.70 | Minimum fidelity for CLARIFY decision |
| `embed_fn` | callable | auto | Embedding function (ONNX-first if None) |
| `on_block` | callable | None | Callback for blocked requests |
| `high_risk` | bool | False | Use ESCALATE instead of INERT |
| `session` | GovernanceSessionContext | None | Session for receipt signing |

### Metadata Access

```python
func._telos_purpose     # Purpose statement used
func._telos_threshold   # Decision threshold
func._telos_high_risk   # High-risk flag
func._telos_config      # AgentConfig (if config-driven)
func._telos_session     # GovernanceSessionContext (if signing)
```

---

## 2. Session Integration

### Governance Sessions

A `GovernanceSessionContext` manages the lifecycle of cryptographic receipt signing:

```python
from telos_governance.session import GovernanceSessionContext

with GovernanceSessionContext() as session:
    # Score and sign
    receipt = session.sign_result(result, "user request", "pre_action")

    # Generate session proof (all receipts + verification data)
    proof = session.generate_proof()
```

### Decorator + Session

Combine the decorator with a session for automatic receipt signing:

```python
from telos_adapters.generic import telos_governed
from telos_governance.session import GovernanceSessionContext

with GovernanceSessionContext() as session:
    @telos_governed(config="agents/my_agent.yaml", session=session)
    def process(request: str) -> str:
        return do_work(request)

    # Each call automatically signs a governance receipt
    process("analyze this data")
    process("generate report")
    process("summarize findings")

    # 3 signed receipts in the session chain
    proof = session.generate_proof()
    assert proof["total_receipts"] == 3
```

### Session with TKeys

Enable HMAC-SHA512 co-signing via TKeys for stronger session binding:

```python
session = GovernanceSessionContext(
    enable_tkeys=True,
    master_key=my_master_key,  # Optional, generated if None
)
```

### Session with Ed25519 Key Persistence

Load an existing deployment key for consistent receipt signing:

```python
session = GovernanceSessionContext(
    ed25519_private_key=my_32_byte_key,
)
```

### Session with Intelligence Layer

Automatically record governance telemetry:

```python
from telos_governance.intelligence_layer import (
    IntelligenceCollector,
    IntelligenceConfig,
)

collector = IntelligenceCollector(
    IntelligenceConfig(
        enabled=True,
        collection_level="metrics",  # or "full"
        agent_id="property-intel-v2",
    )
)

session = GovernanceSessionContext(
    intelligence_collector=collector,
    agent_id="property-intel-v2",
)
```

### Session Proof Structure

```python
proof = session.generate_proof()
# {
#   "session_id": "telos-a1b2c3d4...",
#   "proof_generated_at": 1707900000.0,
#   "total_receipts": 3,
#   "ed25519_public_key": "9f8e7d6c...",
#   "receipt_chain": [...],
#   "verification": {
#     "method": "Ed25519 + HMAC-SHA512 co-signatures",
#     "ed25519_verifiable": true,
#     "hmac_verifiable": true,
#     "standards": ["Ed25519 (RFC 8032)", "HMAC-SHA512 (FIPS 198-1)"]
#   }
# }
```

---

## 3. Bundle Delivery Workflow

### Overview

The bundle system packages a TELOS governance configuration into an encrypted, signed artifact for customer delivery:

```
YAML Config + Keys --> .telos bundle + .telos-license token
                       |
                       v
Customer receives:
  agent.telos           (encrypted, dual-signed)
  agent.telos-license   (Ed25519-signed authorization)
  license.key           (32-byte symmetric key)
  deploy.pub            (deployment public key)
  labs.pub              (Labs public key for verification)
  DELIVERY_MANIFEST.json
```

### Step 1: Generate Labs Key (Once)

```python
from telos_governance.signing import SigningKeyPair

labs_key = SigningKeyPair.generate()
labs_key.save_private_pem("keys/labs.pem")
labs_key.save_public_bytes("keys/labs.pub")
```

Or via CLI:
```bash
# Labs key generation is handled by bundle provision
```

### Step 2: Create Agent Configuration

Create a YAML config (see [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)):

```yaml
agent:
  id: property-intel-v2
  name: Property Intelligence Agent
purpose:
  statement: >-
    Provide AI-powered property intelligence for insurance
    underwriting decision support.
scope: >-
  property analysis, risk assessment, roof condition scoring
boundaries:
  - text: "Do not make autonomous underwriting decisions"
    severity: hard
tools:
  - name: get_property_analysis
    description: "Retrieve property analysis data"
    risk_level: low
```

### Step 3: Provision Delivery Package

```bash
telos bundle provision agents/property_intel.yaml \
    --labs-key keys/labs.pem \
    --agent-id property-intel-v2 \
    --output-dir delivery/acme \
    --licensee-org "Acme Insurance" \
    --risk-classification high_risk \
    --expires-in-days 365
```

This generates all delivery artifacts in `delivery/acme/`.

### Step 4: Customer Activation

The customer receives the delivery package and activates:

```bash
# Verify the license token
telos license verify agent.telos-license --labs-pub labs.pub

# Verify and decrypt the bundle
telos bundle activate agent.telos \
    --license-key license.key \
    --labs-pub labs.pub \
    --output agent.yaml
```

### Step 5: Customer Uses Configuration

```bash
# Score requests against the activated config
telos score "What is the roof condition?" -c agent.yaml

# Or integrate via decorator
```

```python
@telos_governed(config="agent.yaml")
def analyze(request: str) -> str:
    return do_work(request)
```

---

## 4. Intelligence Layer

### Overview

The Intelligence Layer provides opt-in governance telemetry collection. It records anonymized governance metrics (no raw text) for embedding calibration improvements.

### Collection Levels

| Level | What's Collected | Use Case |
|-------|------------------|----------|
| `off` | Nothing | Default, no telemetry |
| `metrics` | Fidelity scores, decisions, timestamps | Recommended for calibration |
| `full` | + dimension breakdown, contrastive data | Deep analysis |

### CLI Usage

```bash
# Score with telemetry
telos score "analyze this property" -c agent.yaml --telemetry=metrics

# Check status
telos intelligence status

# Export for TELOS Labs
telos intelligence export property-intel-v2

# Clear data
telos intelligence clear property-intel-v2
```

### Programmatic Usage

```python
from telos_governance.intelligence_layer import (
    IntelligenceCollector,
    IntelligenceConfig,
)

config = IntelligenceConfig(
    enabled=True,
    collection_level="metrics",
    agent_id="my-agent",
)
collector = IntelligenceCollector(config)

# Manual session
collector.start_session("session-001", "my-agent")
collector.record_decision(
    decision_point="pre_action",
    decision="execute",
    effective_fidelity=0.87,
    composite_fidelity=0.78,
)
collector.end_session()

# Query
aggregate = collector.get_aggregate("my-agent")
sessions = collector.list_sessions("my-agent")
```

### Storage

Telemetry is stored locally in `~/.telos/intelligence/{agent_id}/`:
- `sessions/{session_id}.jsonl` - Per-session records
- `aggregate.json` - Running aggregate statistics

No data leaves the machine unless explicitly exported.

---

## 5. Encrypted Data Export

For secure governance data transfer:

```python
from telos_governance.data_export import GovernanceExporter

exporter = GovernanceExporter(encryption_key=my_32_byte_key)

# Export proof with encryption
exporter.export_proof(proof_data, "governance_proof.telos-export")

# Export with separate proof file
exporter.export_with_proof(
    data=telemetry_data,
    data_path="telemetry.telos-export",
    proof_path="telemetry.telos-proof",
)
```

Uses AES-256-GCM encryption with authenticated additional data (AAD).

---

## 6. Update Lifecycle

### Three-Tier Update Awareness

TELOS uses a three-tier architecture for update awareness that preserves the local-first philosophy:

```
Tier 1: BUNDLE EXPIRY (zero network)
  └── expires_at field in manifest → CLI warns when stale

Tier 2: SIGNED VERSION MANIFEST (background check)
  └── Static JSON on CDN → CLI checks in background → dim hint on stderr

Tier 3: OUT-OF-BAND BUNDLE DELIVERY (existing flow)
  └── BundleProvisioner → secure transfer → telos bundle activate
```

### Background Update Check

The CLI automatically checks for updates on every invocation:

```bash
# Normal usage — update check runs silently in background
telos score "analyze this" -c agent.yaml

# If an update is available, a dim hint appears after output:
#   Update available: v2.0.0 → v2.1.0 (regulatory)
#     Contact TELOS Labs at JB@telos-labs.ai

# Explicit check with full details
telos update check
```

### Suppressing Update Checks

```bash
# Via flag
telos version --no-update-check

# Via environment variable
export TELOS_NO_UPDATE_CHECK=1
telos version
```

### Bundle Expiry (Tier 1)

Bundles with an `expires_at` field trigger automatic warnings:

```bash
$ telos bundle activate agent.telos --license-key license.key -o agent.yaml
Bundle: agent.telos
  Agent: property-intel-v2
  ⚠ EXPIRING: Bundle expires in 15 day(s) (2026-03-01T00:00:00Z)
```

### Update Severity Classification

Updates are classified into three severity tiers:

| Severity | Description | Customer Action |
|----------|-------------|-----------------|
| `safety` | Critical governance vulnerability | Notified with urgency |
| `regulatory` | New regulation enacted | 30-day activation window |
| `feature` | Optional improvement | Pull when ready |

### Comparing Bundles Before Activation

Use `telos bundle diff` to inspect what changed before activating:

```bash
telos bundle diff current.telos new.telos
```

### Version Manifest Format

The signed manifest is a static JSON file hosted on CDN:

```json
{
  "schema_version": 1,
  "latest_version": "2.1.0",
  "minimum_version": "2.0.0",
  "released_at": "2026-02-15T00:00:00Z",
  "severity": "routine",
  "update_type": "regulatory",
  "changelog_url": "https://telos-labs.ai/changelog",
  "update_instructions": "Contact TELOS Labs at JB@telos-labs.ai",
  "notices": []
}
```

The manifest is signed with the TELOS Labs Ed25519 key. The CLI verifies
the signature before trusting any manifest data.

### What TELOS Does NOT Do

- **No auto-update** — Customer always activates manually
- **No forced updates** — `minimum_version` is informational only
- **No customer data in manifest check** — Request is anonymous
- **No bundle registry** — Bundles delivered out-of-band

---

## Compatibility

| Python | Status |
|--------|--------|
| 3.9 | Supported |
| 3.10 | Supported |
| 3.11 | Supported |
| 3.12 | Supported |
| 3.13 | Supported |

| Backend | Install | Size | Speed |
|---------|---------|------|-------|
| ONNX Runtime | `telos[cli,onnx]` | ~90MB | 0.42s load |
| SentenceTransformer | `telos[cli,embeddings]` | ~2GB | 8.35s load |

ONNX and SentenceTransformer produce identical governance decisions (100% parity, L2 < 1.36e-06).
