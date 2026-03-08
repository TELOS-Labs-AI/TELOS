# TELOS Governance Demos

Two live governance demo suites covering property intelligence and healthcare. Each demonstrates the full 4-layer cascade (L0:keywords -> L1:cosine -> L1.5:SetFit -> L2:LLM) with real-time scoring, cryptographic signing, and forensic audit trails.

---

## Quick Start

```bash
# Set PYTHONPATH from project root
export PYTHONPATH=$(pwd)

# Via CLI (requires pip install -e .)
telos demo nearmap                           # Property intelligence (9 scenarios)
telos demo healthcare                        # Healthcare menu (7 configs, 70 scenarios)

# Via Python directly (no install needed)
python3 demos/nearmap_live_demo.py           # Nearmap direct
python3 demos/healthcare_launcher.py         # Healthcare interactive menu

# Speed up (skip pauses)
DEMO_FAST=1 python3 demos/healthcare_launcher.py
telos demo healthcare --fast

# Observation mode (score without blocking)
DEMO_OBSERVE=1 python3 demos/nearmap_live_demo.py
telos demo nearmap --observe
```

---

## 1. Nearmap Property Intelligence Demo

**File:** `nearmap_live_demo.py`

Self-narrating terminal walkthrough demonstrating the full TELOS governance stack with a **real agentic AI loop** against a Nearmap-style Property Intelligence Agent.

### What it does

1. Loads the Property Intelligence Agent configuration (PA, tools, boundaries)
2. Initialises the FidelityEngine with local SentenceTransformer embeddings (384-dim)
3. Runs 9 scenarios through the full governance stack (FidelityEngine + ToolSelectionGate + ActionChain)
4. Shows 6-dimension scoring breakdowns for every request (purpose, scope, tool, chain, boundary, composite)
5. **Agentic mode:** Mistral autonomously decides which tool to call via native function calling, simulated tools execute and return realistic property data, Mistral summarises the results
6. **Blocked requests** never reach the LLM -- governance stops them before the API call
7. Tracks a multi-step chain with SCI continuity detection (drift + recovery)
8. Prints a signed session proof and summary

### Running

```bash
# Governance-only mode (no API key needed)
python3 demos/nearmap_live_demo.py

# Full agentic mode -- Mistral decides tool calls
MISTRAL_API_KEY=your_key python3 demos/nearmap_live_demo.py

# Via CLI
telos demo nearmap
telos demo nearmap --fast --observe

# Plain ASCII (no colour)
NO_COLOR=1 python3 demos/nearmap_live_demo.py
```

---

## 2. Healthcare AI Governance Demos

**Files:** `healthcare_launcher.py`, `healthcare_live_demo.py`, `healthcare_scenarios.py`

7 healthcare agent configurations spanning clinical documentation, diagnostics, patient-facing portals, and therapeutic decision support. Each config has its own PA, tool palette, boundaries, and governance calibration.

### Configs

| # | Config | Agent Type | Scenarios |
|---|--------|-----------|-----------|
| 1 | `healthcare_ambient_doc` | Clinical AI scribe | 10 |
| 2 | `healthcare_call_center` | Scheduling/Rx/billing | 10 |
| 3 | `healthcare_coding` | ICD-10/CPT coding assist | 10 |
| 4 | `healthcare_diagnostic_ai` | Imaging/lab triage | 10 |
| 5 | `healthcare_patient_facing` | Portal Q&A/intake | 10 |
| 6 | `healthcare_predictive` | Sepsis/deterioration | 10 |
| 7 | `healthcare_therapeutic` | Treatment CDS/dosing | 10 |

### Running

```bash
# Interactive menu (choose 1-7, or 8 for all)
python3 demos/healthcare_launcher.py

# Run a specific config
python3 demos/healthcare_live_demo.py --config healthcare_ambient_doc

# Via CLI
telos demo healthcare                          # Interactive menu
telos demo healthcare -c healthcare_ambient    # Specific config
telos demo healthcare --all --fast             # All 7 sequentially
```

---

## 3. Permission Controller (ESCALATE Notifications)

When the governance engine returns an **ESCALATE** verdict, the Permission Controller notifies the operator and waits for a decision before allowing or blocking the tool call.

### Notification Channels

| Channel | Interaction | Setup |
|---------|------------|-------|
| **Telegram** | Approve/Deny inline buttons | Create bot via @BotFather, get token + chat ID |
| **WhatsApp** | Approve/Deny buttons (Cloud API) | Meta Business app + phone number + access token |
| **Discord** | Notification only (v1) | Channel webhook URL |

### Configuration

```bash
# Interactive setup
telos agent configure-notifications

# Or add to agent config directly:
# notifications:
#   telegram_bot_token: "..."
#   telegram_chat_id: "..."
#   whatsapp_phone_number_id: "..."
#   whatsapp_access_token: "..."
#   whatsapp_recipient_number: "+..."
#   discord_webhook_url: "..."
#   escalation_timeout_seconds: 300
#   timeout_action: "deny"
```

### CLI Fallback

```bash
# Approve a pending escalation
telos agent approve <escalation-id>

# Deny a pending escalation
telos agent deny <escalation-id>

# List recent escalations
telos agent escalations
telos agent escalations --pending
```

### Override Receipts

Approved overrides produce an **Ed25519-signed receipt** for EU AI Act Article 14 compliance. Keys are stored at `~/.telos/keys/`. Audit log at `~/.telos/audit/escalations.jsonl`.

---

## Requirements

- Python 3.9+
- `sentence-transformers` (install with `pip install telos[embeddings]`)
- `mistralai` (optional -- install with `pip install telos[mistral]`)
- `MISTRAL_API_KEY` environment variable (optional -- enables agentic LLM mode)
- `onnxruntime` (for SetFit L1.5 cascade -- install with `pip install onnxruntime`)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEMO_FAST` | off | Skip pauses between scenarios |
| `DEMO_OBSERVE` | off | Observation mode -- score without blocking |
| `NO_COLOR` | off | Disable terminal colours |
| `MISTRAL_API_KEY` | none | Enable Mistral LLM for agentic tool selection |
