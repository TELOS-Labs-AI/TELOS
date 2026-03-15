# T: SAAI Drift Detection Refinement -- Statistical Robustness

## Context

The SAAI drift detection works but its statistical foundation is weak. The current implementation uses a 3-turn baseline and a 5-turn sliding window -- both too small to produce meaningful signal. This task fixes the parameters without changing the core formula or thresholds.

**SAAI Framework (G1.7, G1.9) requires:**
1. Continuous drift measurement
2. Flexibility inversely proportional to drift magnitude
3. Automatic safeguards when thresholds are exceeded
4. Tiered response (notify → tighten → halt)

TELOS already satisfies all four. What's broken is the statistical robustness of the measurement.

**The thresholds (10/15/20%) are FROZEN. Do not change them.**

---

## What Changes

### 1. `telos_core/constants.py`

**Line 593:** Change `BASELINE_TURN_COUNT = 3` → `BASELINE_TURN_COUNT = 50`

**Line 621:** Change `SAAI_DRIFT_WINDOW_SIZE = 5` → remove or keep for backward compat but it will no longer be used by the drift tracker.

**Add new constants** (near the existing SAAI block, ~line 620-660):

```python
# EWMA smoothing span for drift detection (replaces sliding window).
# span=20 gives smoothing factor λ = 2/(20+1) ≈ 0.095.
# Recent events weighted more heavily; no cliff effects from window edge.
# Standard SPC (Statistical Process Control) method.
SAAI_EWMA_SPAN = 20

# Maximum coefficient of variation (σ/μ) allowed for baseline.
# If CV exceeds this after BASELINE_TURN_COUNT events, baseline is
# declared unstable and extended until CV drops below threshold.
# Prevents anchoring drift detection on erratic initial behavior.
SAAI_BASELINE_CV_MAX = 0.30
```

### 2. `telos_governance/adapters/response_manager.py` -- `AgenticDriftTracker`

This is the production drift tracker used by OpenClaw and LangGraph adapters.

**`reset()` method (~line 51):**
Replace:
```python
def reset(self):
    self._fidelity_scores: List[float] = []
    self._post_baseline_scores: List[float] = []
    self._baseline_fidelity: Optional[float] = None
    self._baseline_established: bool = False
    self._drift_level: str = "NORMAL"
    self._drift_magnitude: float = 0.0
    self._acknowledgment_count: int = 0
    self._permanently_blocked: bool = False
```

With:
```python
def reset(self):
    self._fidelity_scores: List[float] = []
    self._baseline_fidelity: Optional[float] = None
    self._baseline_std: float = 0.0
    self._baseline_established: bool = False
    self._ewma: Optional[float] = None  # EWMA current value
    self._drift_level: str = "NORMAL"
    self._drift_magnitude: float = 0.0
    self._acknowledgment_count: int = 0
    self._permanently_blocked: bool = False
```

**`record_fidelity()` method (~line 62):**
Replace the entire method body with:

```python
def record_fidelity(self, effective_fidelity: float) -> Dict[str, Any]:
    """Record a fidelity score and compute SAAI drift."""
    from telos_core.constants import (
        BASELINE_TURN_COUNT, SAAI_EWMA_SPAN, SAAI_BASELINE_CV_MAX,
        SAAI_DRIFT_WARNING, SAAI_DRIFT_RESTRICT, SAAI_DRIFT_BLOCK,
        EPSILON_NUMERICAL,
    )
    import statistics

    if self._permanently_blocked:
        return self._status()

    self._fidelity_scores.append(effective_fidelity)

    # --- Phase 1: Baseline collection ---
    if not self._baseline_established:
        if len(self._fidelity_scores) >= BASELINE_TURN_COUNT:
            baseline_scores = self._fidelity_scores[:BASELINE_TURN_COUNT]
            mu = sum(baseline_scores) / len(baseline_scores)
            sigma = statistics.stdev(baseline_scores) if len(baseline_scores) > 1 else 0.0
            cv = sigma / mu if mu > EPSILON_NUMERICAL else 1.0

            if cv <= SAAI_BASELINE_CV_MAX:
                # Baseline is stable -- establish it
                self._baseline_fidelity = mu
                self._baseline_std = sigma
                self._baseline_established = True
                self._ewma = mu  # Initialize EWMA at baseline mean
            else:
                # Baseline too erratic -- extend by using all scores so far
                # Re-check on every subsequent turn until stable
                all_scores = self._fidelity_scores
                mu = sum(all_scores) / len(all_scores)
                sigma = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
                cv = sigma / mu if mu > EPSILON_NUMERICAL else 1.0
                if cv <= SAAI_BASELINE_CV_MAX:
                    self._baseline_fidelity = mu
                    self._baseline_std = sigma
                    self._baseline_established = True
                    self._ewma = mu

        return self._status()

    # --- Phase 2: EWMA drift detection ---
    lam = 2.0 / (SAAI_EWMA_SPAN + 1)  # smoothing factor
    self._ewma = lam * effective_fidelity + (1 - lam) * self._ewma

    # Drift = relative decline from baseline (clamped to >= 0)
    self._drift_magnitude = max(
        0.0,
        (self._baseline_fidelity - self._ewma) / (self._baseline_fidelity + EPSILON_NUMERICAL),
    )

    # Graduated sanctions (Ostrom DP5)
    if self._drift_magnitude >= SAAI_DRIFT_BLOCK:
        self._drift_level = "BLOCK"
    elif self._drift_magnitude >= SAAI_DRIFT_RESTRICT:
        self._drift_level = "RESTRICT"
    elif self._drift_magnitude >= SAAI_DRIFT_WARNING:
        self._drift_level = "WARNING"
    else:
        self._drift_level = "NORMAL"

    return self._status()
```

**`acknowledge_drift()` method (~line 119):**
Update the reset to clear EWMA instead of post_baseline_scores:
```python
def acknowledge_drift(self, reason: str = "") -> Dict[str, Any]:
    """Acknowledge drift -- resets level but preserves baseline."""
    from telos_core.constants import SAAI_MAX_ACKNOWLEDGMENTS

    self._acknowledgment_count += 1
    if self._acknowledgment_count >= SAAI_MAX_ACKNOWLEDGMENTS:
        self._permanently_blocked = True
        self._drift_level = "BLOCK"
        return self._status()

    # Reset drift state but keep baseline
    self._drift_level = "NORMAL"
    self._drift_magnitude = 0.0
    self._ewma = self._baseline_fidelity  # Reset EWMA to baseline
    return self._status()
```

**`_status()` method:**
Add `baseline_progress` for the mobile app to show during baseline phase:
```python
def _status(self) -> Dict[str, Any]:
    from telos_core.constants import BASELINE_TURN_COUNT
    return {
        "drift_level": self._drift_level,
        "drift_magnitude": round(self._drift_magnitude, 4),
        "baseline_fidelity": self._baseline_fidelity,
        "baseline_established": self._baseline_established,
        "baseline_progress": min(len(self._fidelity_scores), BASELINE_TURN_COUNT) if not self._baseline_established else BASELINE_TURN_COUNT,
        "baseline_required": BASELINE_TURN_COUNT,
        "is_blocked": self._drift_level == "BLOCK",
        "is_restricted": self._drift_level == "RESTRICT",
        "permanently_blocked": self._permanently_blocked,
        "turn_count": len(self._fidelity_scores),
    }
```

**`to_dict()` and `restore()` methods (~line 200-230):**
Update serialization -- replace `post_baseline_scores` with `ewma`:
```python
def to_dict(self) -> Dict[str, Any]:
    return {
        "fidelity_scores": list(self._fidelity_scores),
        "baseline_fidelity": self._baseline_fidelity,
        "baseline_std": self._baseline_std,
        "baseline_established": self._baseline_established,
        "ewma": self._ewma,
        "drift_level": self._drift_level,
        "drift_magnitude": self._drift_magnitude,
        "acknowledgment_count": self._acknowledgment_count,
        "permanently_blocked": self._permanently_blocked,
    }

@classmethod
def restore(cls, state: Dict[str, Any]) -> "AgenticDriftTracker":
    tracker = cls()
    tracker._fidelity_scores = list(state.get("fidelity_scores", []))
    tracker._baseline_fidelity = state.get("baseline_fidelity")
    tracker._baseline_std = state.get("baseline_std", 0.0)
    tracker._baseline_established = state.get("baseline_established", False)
    tracker._ewma = state.get("ewma")
    tracker._drift_level = state.get("drift_level", "NORMAL")
    tracker._drift_magnitude = state.get("drift_magnitude", 0.0)
    tracker._acknowledgment_count = state.get("acknowledgment_count", 0)
    tracker._permanently_blocked = state.get("permanently_blocked", False)
    return tracker
```

### 3. `telos_core/governance_trace.py` -- `GovernanceTraceCollector`

This is the conversational TELOS drift tracker. Same changes, different structure.

**`__init__` (~line 124):** Add EWMA state:
```python
self._baseline_fidelities: List[float] = []
self._baseline_fidelity: Optional[float] = None
self._baseline_std: float = 0.0          # NEW
self._baseline_established: bool = False
self._ewma: Optional[float] = None       # NEW
self._drift_level: DriftLevel = DriftLevel.NORMAL
```

**`_establish_baseline()` (~line 317):** Add stability gate:
```python
def _establish_baseline(self) -> None:
    from telos_core.constants import SAAI_BASELINE_CV_MAX, EPSILON_NUMERICAL

    if not self._baseline_fidelities:
        logger.warning("Cannot establish baseline: no fidelity data")
        return

    self._baseline_fidelity = statistics.mean(self._baseline_fidelities)
    baseline_min = min(self._baseline_fidelities)
    baseline_max = max(self._baseline_fidelities)
    self._baseline_std = statistics.stdev(self._baseline_fidelities) if len(self._baseline_fidelities) > 1 else 0.0

    # Stability gate: reject baseline if CV too high
    cv = self._baseline_std / self._baseline_fidelity if self._baseline_fidelity > EPSILON_NUMERICAL else 1.0
    if cv > SAAI_BASELINE_CV_MAX:
        logger.info(
            f"SAAI Baseline CV too high ({cv:.3f} > {SAAI_BASELINE_CV_MAX}), "
            f"extending baseline collection"
        )
        return  # Don't establish -- keep collecting

    is_stable = all(f >= INTERVENTION_THRESHOLD for f in self._baseline_fidelities)
    self._baseline_established = True
    self._ewma = self._baseline_fidelity  # Initialize EWMA

    baseline_event = BaselineEstablishedEvent(
        session_id=self.session_id,
        baseline_turn_count=len(self._baseline_fidelities),
        baseline_fidelity=self._baseline_fidelity,
        baseline_min=baseline_min,
        baseline_max=baseline_max,
        baseline_std=self._baseline_std,
        is_stable=is_stable,
    )
    self._write_event(baseline_event)

    logger.info(
        f"SAAI Baseline established: fidelity={self._baseline_fidelity:.3f}, "
        f"range=[{baseline_min:.3f}, {baseline_max:.3f}], CV={cv:.3f}, stable={is_stable}"
    )
```

**`_saai_process_fidelity()` (~line 298):** Allow baseline extension past BASELINE_TURN_COUNT:
```python
def _saai_process_fidelity(self, turn_number: int, fidelity: float) -> None:
    from telos_core.constants import BASELINE_TURN_COUNT

    if not self._baseline_established:
        self._baseline_fidelities.append(fidelity)
        if len(self._baseline_fidelities) >= BASELINE_TURN_COUNT:
            self._establish_baseline()
        return

    # Phase 2: EWMA drift detection
    self._update_ewma_and_check_drift(turn_number, fidelity)
```

**Add new method `_update_ewma_and_check_drift()`:**
```python
def _update_ewma_and_check_drift(self, turn_number: int, fidelity: float) -> None:
    """EWMA-based drift detection (replaces session-average method)."""
    from telos_core.constants import (
        SAAI_EWMA_SPAN, SAAI_DRIFT_WARNING, SAAI_DRIFT_RESTRICT,
        SAAI_DRIFT_BLOCK, EPSILON_NUMERICAL,
    )

    if not self._baseline_established or self._baseline_fidelity is None:
        return
    if self._baseline_fidelity <= 0:
        return

    # Update EWMA
    lam = 2.0 / (SAAI_EWMA_SPAN + 1)
    self._ewma = lam * fidelity + (1 - lam) * self._ewma

    # Compute drift
    drift_magnitude = max(
        0.0,
        (self._baseline_fidelity - self._ewma) / (self._baseline_fidelity + EPSILON_NUMERICAL),
    )

    new_drift_level = self._compute_drift_level(drift_magnitude)

    if self._should_trigger_review(new_drift_level):
        self._trigger_mandatory_review(
            turn_number=turn_number,
            new_level=new_drift_level,
            drift_magnitude=drift_magnitude,
            current_avg=self._ewma,
        )
```

**`_check_cumulative_drift()` (~line 354):** This method is now replaced by `_update_ewma_and_check_drift()`. Either delete it or leave it as dead code -- the call in `_saai_process_fidelity()` no longer invokes it.

### 4. Tests -- `tests/scenarios/test_saai_drift_scenarios.py`

The test file has 5 scenario classes that test drift detection. These tests will need adjustment because the baseline is now 50 turns instead of 3, and detection uses EWMA instead of sliding window.

**Key changes:**
- Each test's setup phase needs to generate 50+ baseline events instead of ~3
- The helper `_compute_saai_drift()` should be updated to use EWMA
- The drift trigger points will shift because EWMA is smoother than a raw window -- you may need slightly more degraded turns to cross thresholds
- `TestSAAISteadyStateCompliance` (22-turn control) needs to be expanded to 70+ turns

**For each test class:**
1. Add a baseline helper that generates 50 on-topic turns at stable fidelity
2. Then apply the drift pattern (gradual, rapid, catastrophic, recovery, steady-state)
3. Assert the same threshold crossings but at adjusted turn counts

**The assertions about WHICH level is reached should NOT change** -- WARNING at 10%, RESTRICT at 15%, BLOCK at 20%. Only the turn numbers at which they're reached will change.

### 5. Compliance endpoint traffic light -- `telos_api/main.py`

The traffic light in the compliance endpoint should derive from SAAI drift level, not from arbitrary escalation rate thresholds.

**Current (approximate):**
```python
if escalation_rate > 0.15 or boundary_trigger_rate > 0.5:
    traffic_light = "RED"
elif escalation_rate > 0.05 or boundary_trigger_rate > 0.2:
    traffic_light = "YELLOW"
else:
    traffic_light = "GREEN"
```

**Replace with:**
```python
# Traffic light derived from SAAI drift level
# NORMAL/WARNING = GREEN (system operating, drift within tolerance)
# RESTRICT = YELLOW (thresholds tightened, review recommended)
# BLOCK = RED (session frozen, intervention required)
if drift_level == "BLOCK":
    traffic_light = "RED"
elif drift_level == "RESTRICT":
    traffic_light = "YELLOW"
else:
    traffic_light = "GREEN"
```

Note: The compliance endpoint aggregates across all events in a time window, not a single session. The `drift_level` here should be the **worst drift level seen** across all sessions in the window (already computed in the SAAI section of the endpoint).

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `telos_core/constants.py` | `BASELINE_TURN_COUNT` 3→50, add `SAAI_EWMA_SPAN=20`, `SAAI_BASELINE_CV_MAX=0.30` |
| `telos_governance/adapters/response_manager.py` | Replace sliding window with EWMA in `AgenticDriftTracker` |
| `telos_core/governance_trace.py` | Replace session-average with EWMA in `GovernanceTraceCollector` |
| `tests/scenarios/test_saai_drift_scenarios.py` | Expand baselines to 50+, update turn counts for EWMA timing |
| `telos_api/main.py` (StewartBot) | Traffic light from SAAI drift level, not escalation rate |

## Verification

```bash
cd /Users/jb/Desktop/telos_hardened && source .venv/bin/activate
python -m pytest tests/scenarios/test_saai_drift_scenarios.py -v
python -m pytest tests/ -x -q
```

After tests pass, hit the compliance endpoint:
```bash
curl -H "Authorization: Bearer nrm-telos-2026-demo" http://localhost:8100/api/v1/compliance/report?hours=24
```

Confirm `traffic_light` now derives from drift data.

## Important Notes

- **Do NOT change the 10/15/20% thresholds.** They are frozen.
- **Do NOT change the graduated sanctions behavior.** RESTRICT still tightens EXECUTE threshold. BLOCK still forces ESCALATE.
- **The EWMA smoothing factor λ = 2/(span+1) ≈ 0.095.** This means ~20 recent events dominate the signal. Old events decay exponentially.
- **The stability gate (CV < 0.30) may extend baseline beyond 50 turns** if early behavior is erratic. This is intentional -- better to wait for stable baseline than anchor on noise.
- **Backward compat:** `SAAI_DRIFT_WINDOW_SIZE` can remain in constants.py for any code that still references it, but the drift tracker no longer uses it.
