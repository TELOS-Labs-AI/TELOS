# TELOS CLI Reference

**Version:** 2.0.0
**Entry point:** `telos` (installed via `pip install telos-gov[cli,onnx]`)

---

## Installation

```bash
# Lightweight (recommended, ~90MB)
pip install telos-gov[cli,onnx]

# Full PyTorch embeddings (~2GB)
pip install telos-gov[cli,embeddings]

# Everything (dev, gateway, observatory)
pip install telos-gov[all]
```

---

## Commands

### `telos version`

Show version and system information.

```
$ telos version
telos 2.0.0
Python 3.11.7

Dependencies:
  sentence-transformers: not installed
  onnxruntime: installed
  cryptography: installed
  pyyaml: installed
```

### `telos config list`

List all available configuration templates grouped by domain.

```
$ telos config list

Available configurations:

  General
    [1] default             Blank starter template — customize for any agent

  Insurance
    [2] property-intel      Aerial imagery + risk scoring for insurance underwriting

  Healthcare (7 configs)
    [3] healthcare-ambient      Ambient clinical documentation (DAX, Abridge)
    [4] healthcare-call-center  Patient call center agent
    ...
```

---

### `telos config show <name>`

Preview a configuration template's purpose, boundaries, tools, and constraints.

| Argument | Description |
|----------|-------------|
| `name` | Template name (from `telos config list`) |

```
$ telos config show healthcare-ambient

Ambient Clinical Documentation
────────────────────────────────
  Domain:     Healthcare
  Agent ID:   healthcare_ambient_doc
  Purpose:    Accurately document the clinical encounter...
  Boundaries: 8 (all hard)
  Tools:      8 (3 high-risk, 1 medium-risk, 4 low-risk)

  Key boundaries:
    • No fabrication of clinical findings not discussed during the encounter
    • No attribution of family or social history to the patient
    • No autonomous clinical decision-making
```

---

### `telos config validate <path>`

Validate a TELOS YAML configuration file against the schema.

| Argument | Description |
|----------|-------------|
| `path` | Path to `.yaml` configuration file |

```
$ telos config validate agents/property_intel.yaml
OK: agents/property_intel.yaml is valid
  Agent: Property Intelligence Agent (property-intel)
  Purpose: Provide AI-powered property intelligence...
  Boundaries: 5
  Tools: 8
  Example requests: 5
  Safe exemplars: 10
```

Exit code 1 on validation failure.

---

### `telos init`

Create a new agent configuration from a template. Run without flags for interactive selection.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--template`, `-t` | STRING | interactive | Template name (from `telos config list`) |
| `--output`, `-o` | PATH | auto | Output filename |
| `--list` | FLAG | false | List templates and exit |

Available templates: `default`, `property-intel`, `healthcare-ambient`, `healthcare-call-center`, `healthcare-coding`, `healthcare-diagnostic`, `healthcare-patient`, `healthcare-predictive`, `healthcare-therapeutic`.

```
$ telos init
Available templates:
  General
    [1] default             Blank starter template
  Insurance
    [2] property-intel      Aerial imagery + risk scoring
  Healthcare (7 configs)
    [3] healthcare-ambient  ...
Select template [1-9]: 3
Created: healthcare_ambient.yaml

$ telos init -t healthcare-diagnostic -o my_agent.yaml
Created: my_agent.yaml
```

---

### `telos score <request>`

Score a request against an agent's governance configuration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--config`, `-c` | PATH | required | Path to YAML config file |
| `--json` | flag | | Output as JSON |
| `--verbose`, `-v` | flag | | Show per-dimension scores |
| `--sign` | flag | | Sign governance receipt with Ed25519 |
| `--telemetry` | choice | `off` | Intelligence Layer level: `off`, `metrics`, `full` |

```
$ telos score "What is the roof condition for this property?" -c agent.yaml
Decision: execute
Fidelity: 87.23%

$ telos score "What is the roof condition?" -c agent.yaml --verbose --sign
Decision: execute
Fidelity: 87.23%

Per-dimension scores:
  Purpose:  0.8723
  Scope:    0.8145
  Tool:     0.7891
  Chain:    0.0000
  Boundary: 0.0312

  Composite: 0.7834
  Effective: 0.8723

  Selected tool: get_property_analysis
  Contrastive: suppressed (gap=-0.1234)

  Explanations:
    purpose: Strong alignment with property intelligence purpose
    scope: Within data analysis scope
    ...

Signed receipt:
  Session: telos-a1b2c3d4e5f6g7h8
  Ed25519: 3a4b5c6d7e8f9a0b1c2d3e4f5a6b...
  Public key: 9f8e7d6c5b4a3928...
```

**JSON output:**
```json
{
  "request": "What is the roof condition?",
  "agent": "property-intel",
  "decision": "execute",
  "composite_fidelity": 0.7834,
  "effective_fidelity": 0.8723,
  "purpose_fidelity": 0.8723,
  "scope_fidelity": 0.8145,
  "boundary_violation": 0.0312,
  "tool_fidelity": 0.7891,
  "chain_continuity": 0.0,
  "boundary_triggered": false,
  "selected_tool": "get_property_analysis",
  "human_required": false,
  "receipt": {
    "ed25519_signature": "...",
    "public_key": "...",
    "payload_hash": "...",
    "session_id": "telos-..."
  }
}
```

---

### `telos benchmark run`

Run the Nearmap counterfactual governance benchmark.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dataset`, `-d` | PATH | bundled | Path to JSONL scenario dataset |
| `--output`, `-o` | PATH | bundled | Path to write JSON results |
| `--verbose`, `-v` | flag | | Print per-scenario pass/fail |
| `--forensic` | flag | | Generate 9-section HTML report + JSONL + CSV |
| `--forensic-dir` | PATH | `validation/nearmap/reports/` | Directory for forensic output |

```
$ telos benchmark run --verbose --forensic
Loading scenarios from .../nearmap_counterfactual_v1.jsonl...
Loaded 235 scenarios
Running benchmark...
  ...
Results written to .../benchmark_results.json

Generating forensic reports...
  HTML:  .../reports/nearmap_benchmark_forensic_2026-02-14.html
  JSONL: .../reports/nearmap_benchmark_forensic_2026-02-14.jsonl
  CSV:   .../reports/nearmap_benchmark_forensic_2026-02-14.csv

Benchmark PASSED (81.7% accuracy)
```

Exit code 1 if accuracy < 85%.

---

### `telos report generate`

Generate forensic governance report from existing benchmark results.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--results`, `-r` | PATH | bundled | Path to benchmark results JSON |
| `--dataset`, `-d` | PATH | bundled | Path to JSONL scenario dataset |
| `--output-dir`, `-o` | PATH | `validation/nearmap/reports/` | Directory for report outputs |

```
$ telos report generate --results benchmark_results.json
Generating forensic reports...
  HTML:  .../reports/nearmap_benchmark_forensic_2026-02-14.html
  JSONL: .../reports/nearmap_benchmark_forensic_2026-02-14.jsonl
  CSV:   .../reports/nearmap_benchmark_forensic_2026-02-14.csv
Done.
```

---

### `telos bundle build <config_path>`

Build a `.telos` governance bundle from a YAML configuration.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--labs-key` | PATH | required | TELOS Labs private key PEM |
| `--deploy-key` | PATH | required | Deployment private key PEM |
| `--license-key` | PATH | required | 32-byte license key file |
| `--output`, `-o` | PATH | required | Output `.telos` file |
| `--agent-id` | string | | Agent identifier |
| `--description` | string | | Bundle description |
| `--telos-version` | string | | TELOS version string |
| `--risk-classification` | choice | | `high_risk`, `limited_risk`, `minimal_risk`, `unclassified` |
| `--regulatory-jurisdiction` | string | | Comma-separated jurisdictions |

```
$ telos bundle build agent.yaml \
    --labs-key labs.pem --deploy-key deploy.pem \
    --license-key license.key --output agent.telos \
    --agent-id property-intel-v2 --risk-classification high_risk
Bundle built: agent.telos (4,128 bytes)
  Agent: property-intel-v2
  Labs fingerprint: a1b2c3d4e5f6...
  Deploy fingerprint: 9f8e7d6c5b4a...
```

---

### `telos bundle provision <config_path>`

Provision a complete customer delivery package.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--labs-key` | PATH | required | TELOS Labs private key PEM |
| `--output-dir`, `-o` | PATH | required | Output directory |
| `--agent-id` | string | | Agent identifier |
| `--description` | string | | Bundle description |
| `--telos-version` | string | | TELOS version string |
| `--licensee-id` | string | | Licensee identifier |
| `--licensee-org` | string | | Licensee organization |
| `--risk-classification` | choice | | Risk classification |
| `--regulatory-jurisdiction` | string | | Jurisdiction identifiers |
| `--expires-in-days` | int | perpetual | License expiration days |

```
$ telos bundle provision agent.yaml \
    --labs-key labs.pem \
    --agent-id property-intel-v2 \
    --output-dir ./delivery/acme \
    --licensee-org "Acme Insurance" \
    --risk-classification high_risk \
    --expires-in-days 365
Delivery provisioned: ./delivery/acme/
  Bundle:      ./delivery/acme/property-intel-v2.telos
  Token:       ./delivery/acme/property-intel-v2.telos-license
  License key: ./delivery/acme/license.key
  Deploy pub:  ./delivery/acme/deploy.pub
  Labs pub:    ./delivery/acme/labs.pub
  Manifest:    ./delivery/acme/DELIVERY_MANIFEST.json

SECURITY: Deliver license.key out-of-band (USB, secure transfer).
```

Generates: `.telos` bundle, `.telos-license` token, `license.key` (32-byte, 0o600), deployment public key, Labs public key, `DELIVERY_MANIFEST.json`.

---

### `telos bundle activate <bundle_path>`

Decrypt and activate a `.telos` bundle.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--license-key` | PATH | required | 32-byte license key file |
| `--labs-pub` | PATH | | Labs public key for signature verification |
| `--output`, `-o` | PATH | required | Output path for decrypted config |

```
$ telos bundle activate agent.telos \
    --license-key license.key --labs-pub labs.pub --output agent.yaml
Bundle: agent.telos
  Agent: property-intel-v2
  Version: 2.0.0
  Labs signature: VERIFIED

Activated: agent.yaml (2,048 bytes)
```

---

### `telos license verify <token_path>`

Verify a TELOS license token.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--labs-pub` | PATH | | Labs public key for signature verification |
| `--license-key` | PATH | | License key to verify binding |
| `--agent-id` | string | | Expected agent ID |
| `--grace-period` | int | 0 | Grace period in days after expiry |

```
$ telos license verify agent.telos-license --labs-pub labs.pub
Token: agent.telos-license
  Agent: property-intel-v2
  Token ID: tok_a1b2c3d4
  Perpetual: no
  Expires: 2027-02-14T00:00:00
  Signature: VERIFIED

License VALID
```

---

### `telos license inspect <token_path>`

Inspect a license token payload (no keys required).

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--json` | flag | | Output as JSON |

```
$ telos license inspect agent.telos-license
License Token: agent.telos-license
--------------------------------------------------
  Token ID:      tok_a1b2c3d4
  Agent ID:      property-intel-v2
  Issuer:        TELOS AI Labs Inc.
  Issued At:     2026-02-14T00:00:00
  Expires At:    2027-02-14T00:00:00
  Capabilities:  score, benchmark
  Bundle ID:     bun_9f8e7d6c
  Licensee Org:  Acme Insurance
  Risk Class:    high_risk
```

---

### `telos intelligence status`

Show Intelligence Layer status and storage statistics.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--base-dir` | PATH | `~/.telos/intelligence/` | Override storage directory |

```
$ telos intelligence status
Intelligence Layer Status
----------------------------------------
  Base directory: /Users/me/.telos/intelligence
  Agents tracked: 1

  Agent: property-intel-v2
    Sessions: 47
    Records:  1,234
    Mean fidelity: 0.8312
    Decisions: {'execute': 891, 'clarify': 234, 'suggest': 89, 'inert': 20}
```

---

### `telos intelligence export <agent_id>`

Export telemetry data for an agent.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--output`, `-o` | PATH | `{agent_id}-telemetry.json` | Output file path |
| `--base-dir` | PATH | `~/.telos/intelligence/` | Override storage directory |

```
$ telos intelligence export property-intel-v2
Exported telemetry for 'property-intel-v2' to property-intel-v2-telemetry.json
  Sessions: 47
  Records: 1,234
```

---

### `telos intelligence clear <agent_id>`

Clear telemetry data for an agent.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--base-dir` | PATH | `~/.telos/intelligence/` | Override storage directory |

```
$ telos intelligence clear property-intel-v2
Cleared 47 session file(s) for 'property-intel-v2'
```

### `telos intelligence export-encrypted <agent_id>`

Export encrypted telemetry for TELOS Labs analysis. Encrypts aggregate telemetry data with AES-256-GCM using the license key, producing a `.telos-export` file suitable for secure transfer.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--license-key` | PATH (required) | — | Path to license key file for encryption |
| `--output`, `-o` | PATH | `{agent_id}-telemetry.telos-export` | Output file path |
| `--base-dir` | PATH | `~/.telos/intelligence/` | Override storage directory |

```
$ telos intelligence export-encrypted property-intel-v2 \
    --license-key license.key
Encrypted telemetry exported: property-intel-v2-telemetry.telos-export
  Sessions: 3
  Total records: 142
  Mean fidelity: 0.8234
  Format: AES-256-GCM encrypted .telos-export
```

No raw request text is included — only mathematical governance metrics.

---

### `telos update check`

Explicitly check for available TELOS updates. Fetches the signed version manifest from the TELOS Labs CDN and displays version information.

```
$ telos update check
Checking for updates...
Current version: v2.0.0
Latest version:  v2.1.0
Released:        2026-02-15T00:00:00Z
Severity:        REGULATORY
Type:            regulatory
Minimum version: v2.0.0

↑ Update available
  Changelog: https://telos-labs.ai/changelog
  Contact TELOS Labs at JB@telos-labs.ai
```

---

### `telos bundle diff <bundle_a> <bundle_b>`

Compare two `.telos` bundles by their cleartext manifests. No decryption required.

| Argument | Description |
|----------|-------------|
| `bundle_a` | Path to first `.telos` bundle |
| `bundle_b` | Path to second `.telos` bundle |

```
$ telos bundle diff agent_v1.telos agent_v2.telos
Bundle A: agent_v1.telos
Bundle B: agent_v2.telos
──────────────────────────────────────────────────
  changelog:
    A:
    B: Updated regulatory boundaries for EU AI Act
  corpus_version:
    A: 61.106.48
    B: 61.112.52
  supersedes:
    A:
    B: a1b2c3d4-5678-...

  → Bundle B supersedes Bundle A
```

---

## Global Options

| Option | Env Var | Description |
|--------|---------|-------------|
| `--no-color` | `NO_COLOR` | Disable color output |
| `--no-update-check` | `TELOS_NO_UPDATE_CHECK` | Disable background update check |
| `--version` | | Show version and exit |

## Background Update Check

TELOS CLI automatically checks for updates in the background on every invocation. This check:
- Runs in a daemon thread with a 2-second timeout
- Caches results for 24 hours in `~/.telos/update_cache.json`
- Only shows a notification on TTY stderr (never pollutes stdout pipes)
- Verifies the manifest signature with the TELOS Labs public key
- Sends no customer data (anonymous request)

Disable with `--no-update-check` or `TELOS_NO_UPDATE_CHECK=1`.

## Bundle Expiry Warnings

When activating a bundle with an `expires_at` field, the CLI automatically warns:
- **Within 30 days of expiry:** Yellow warning with days remaining
- **After expiry:** Red warning with days since expiration

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (validation failure, missing deps, benchmark failure) |
