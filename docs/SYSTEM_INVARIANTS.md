# TELOS System Invariants

Safety-critical invariants that must hold across all deployments, configurations, and future development. Violations of these invariants compromise the integrity of the governance framework.

---

## INV-1: Governance is INERT until TKey-signed

The TELOS governance engine refuses to start without a valid Ed25519 TKey signature on the PA configuration. Without signature, the engine is **INERT** — not degraded, not warning-only, INERT.

**Rationale:** Liability separation. The customer must cryptographically attest to what they defined before the engine enforces it. TELOS has zero fingerprints in the customer's governance specification.

**Implementation:** `pa_signing.verify_config()` called at daemon boot. `governance_active` property returns `True` only if `status == VERIFIED`. Daemon still starts (agent can run ungoverned), but all score requests return INERT with `pa_unsigned: true`.

**Introduced:** 2026-02-22. Enforced in daemon: commit `5a3c8ae`.

---

## INV-2: Never fine-tune on PA-injected outputs

If PA-injected outputs become training data — via fine-tuning, RLHF, DPO, or any other weight-update mechanism — surface features of compliance get baked into model weights. The agent would **appear** aligned without governance infrastructure. The semantic injection layer would produce false confidence while the actual governance constraints (boundary detection, fidelity scoring, escalation) become irrelevant.

This is the "parroting" failure mode: the model learns to produce outputs that **look** governed without being governed. The mathematical scoring layer can no longer distinguish genuine compliance from learned mimicry.

**Rationale:** The dual-layer alignment architecture (pre-generation semantic injection + post-generation mathematical scoring) requires that the semantic layer supplements, never replaces, the mathematical layer. If the semantic layer contaminates training data, the mathematical layer's measurements become unreliable.

**Implementation:** Governance events include `pa_injected: bool` to track which outputs were generated under PA injection. Any data pipeline consuming governance telemetry must filter on this field. No automated export path may include PA-injected outputs without explicit human authorization.

**Introduced:** 2026-02-26. Source: internal safety review.

---

## INV-3: PA changes require Ed25519 ceremony

The PA configuration can only be updated through a cryptographic signing ceremony. No runtime mechanism may modify the PA without producing a new Ed25519 signature. Hot-reloading of PA content without re-signing is a security violation.

**Rationale:** The PA is the governance specification — the contract between human principal and AI agent. Changes must be deliberate, auditable, and non-repudiable.

**Implementation:** `PAContext` precomputes injection blocks at session start and caches them. Invalidation only on PA change detected via hash comparison. New PA requires `telos pa sign` with customer's TKey.

**Introduced:** 2026-02-22.
