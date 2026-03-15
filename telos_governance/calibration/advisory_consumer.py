"""
Advisory Consumer -- Structured pipeline from advisory findings to calibration queue.

Consumes advisory_finding.json output from the 6 commissioned advisory agents,
validates against schema, filters by severity, routes by category, and queues
actionable items at ~/.telos/calibration_queue/pending.json.

Pipeline:
    Advisory agents (90-min cycles) -> advisory_finding.json
        -> validate -> filter -> route -> calibration queue

Routing rules:
    centroid_calibration -> flag PA tool definitions needing exemplar updates
    threshold_tuning    -> record proposed changes (NEVER auto-apply)
    audit_integrity     -> flag audit trail issues
    boundary_coverage   -> flag missing/weak boundaries
    drift_detection     -> record drift signals for SPC trending
    chain_continuity    -> flag chain break patterns
    compliance_gap      -> flag regulatory coverage gaps

Severity filter:
    CRITICAL/HIGH -> auto-queued with priority
    MEDIUM        -> queued with review_required=True
    LOW/INFO      -> logged only (not queued)
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CALIBRATION_QUEUE_DIR = Path.home() / ".telos" / "calibration_queue"
PENDING_FILE = CALIBRATION_QUEUE_DIR / "pending.json"

REQUIRED_FINDING_FIELDS = {
    "finding_id", "severity", "category", "metric_name",
    "metric_value", "recommendation",
}

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}

VALID_CATEGORIES = {
    "centroid_calibration",
    "threshold_tuning",
    "audit_integrity",
    "boundary_coverage",
    "drift_detection",
    "chain_continuity",
    "compliance_gap",
}

VALID_ACTIONS = {
    "recalibrate_centroids",
    "adjust_threshold",
    "add_boundary",
    "remove_boundary",
    "fix_audit_chain",
    "fix_correlation",
    "retrain_setfit",
    "no_action",
}

# Severities that auto-queue
AUTO_QUEUE_SEVERITIES = {"CRITICAL", "HIGH"}
# Severities that queue with review required
REVIEW_QUEUE_SEVERITIES = {"MEDIUM"}
# Severities that are logged only
LOG_ONLY_SEVERITIES = {"LOW", "INFO"}


class AdvisoryConsumerError(Exception):
    """Error in advisory finding consumption."""
    pass


@dataclass
class CalibrationItem:
    """A single item in the calibration queue."""
    item_id: str
    finding_id: str
    severity: str
    category: str
    dimension: str
    metric_name: str
    metric_value: float
    metric_target: Optional[float]
    metric_delta: Optional[float]
    action: str
    target_module: str
    target_field: str
    description: str
    priority: int
    review_required: bool
    advisor_id: str
    cycle_id: str
    convergence_count: int
    agreeing_advisors: List[str]
    queued_at: float = 0.0

    def __post_init__(self):
        if self.queued_at == 0.0:
            self.queued_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CalibrationItem":
        return cls(**d)


@dataclass
class ConsumptionResult:
    """Result of consuming advisory findings."""
    consumed: int = 0
    queued: int = 0
    rejected: int = 0
    logged_only: int = 0
    errors: List[str] = field(default_factory=list)
    items: List[CalibrationItem] = field(default_factory=list)


def validate_finding(finding: Dict[str, Any]) -> Optional[str]:
    """Validate a single advisory finding.

    Returns:
        None if valid, error message string if invalid.
    """
    missing = REQUIRED_FINDING_FIELDS - set(finding.keys())
    if missing:
        return f"Missing required fields: {', '.join(sorted(missing))}"

    severity = finding.get("severity", "")
    if severity not in VALID_SEVERITIES:
        return f"Invalid severity: {severity}"

    category = finding.get("category", "")
    if category not in VALID_CATEGORIES:
        return f"Invalid category: {category}"

    rec = finding.get("recommendation", {})
    if not isinstance(rec, dict):
        return "recommendation must be a dict"

    action = rec.get("action", "")
    if action and action not in VALID_ACTIONS:
        return f"Invalid action: {action}"

    return None


def consume_findings(
    findings_data: Dict[str, Any],
    audit_fn=None,
) -> ConsumptionResult:
    """Consume advisory findings and route to calibration queue.

    Args:
        findings_data: Parsed advisory_finding.json content.
        audit_fn: Optional callback(event_type, data) for audit logging.

    Returns:
        ConsumptionResult with counts and queued items.
    """
    result = ConsumptionResult()

    advisor_id = findings_data.get("advisor_id", "unknown")
    cycle_id = findings_data.get("cycle_id", "")
    findings = findings_data.get("findings", [])

    if not isinstance(findings, list):
        result.errors.append("findings must be an array")
        return result

    for finding in findings:
        result.consumed += 1

        # Validate
        error = validate_finding(finding)
        if error:
            result.rejected += 1
            result.errors.append(
                f"Finding {finding.get('finding_id', '?')}: {error}"
            )
            continue

        severity = finding["severity"]
        category = finding["category"]
        rec = finding.get("recommendation", {})

        # Route by severity
        if severity in LOG_ONLY_SEVERITIES:
            result.logged_only += 1
            if audit_fn:
                audit_fn("advisory_finding_logged", {
                    "finding_id": finding["finding_id"],
                    "severity": severity,
                    "category": category,
                    "advisor_id": advisor_id,
                })
            continue

        # Queue the finding
        review_required = severity in REVIEW_QUEUE_SEVERITIES
        priority = rec.get("priority", 3)
        if severity == "CRITICAL":
            priority = min(priority, 1)
        elif severity == "HIGH":
            priority = min(priority, 2)

        item = CalibrationItem(
            item_id=str(uuid.uuid4()),
            finding_id=finding["finding_id"],
            severity=severity,
            category=category,
            dimension=finding.get("dimension", ""),
            metric_name=finding["metric_name"],
            metric_value=finding["metric_value"],
            metric_target=finding.get("metric_target"),
            metric_delta=finding.get("metric_delta"),
            action=rec.get("action", "no_action"),
            target_module=rec.get("target_module", ""),
            target_field=rec.get("target_field", ""),
            description=rec.get("description", ""),
            priority=priority,
            review_required=review_required,
            advisor_id=advisor_id,
            cycle_id=cycle_id,
            convergence_count=finding.get("convergence_count", 0),
            agreeing_advisors=finding.get("agreeing_advisors", []),
        )

        result.items.append(item)
        result.queued += 1

        if audit_fn:
            audit_fn("advisory_finding_consumed", {
                "finding_id": finding["finding_id"],
                "item_id": item.item_id,
                "severity": severity,
                "category": category,
                "action": item.action,
                "priority": priority,
                "review_required": review_required,
                "advisor_id": advisor_id,
            })

    return result


def load_pending_queue() -> List[CalibrationItem]:
    """Load the pending calibration queue from disk."""
    if not PENDING_FILE.exists():
        return []
    try:
        data = json.loads(PENDING_FILE.read_text("utf-8"))
        return [CalibrationItem.from_dict(d) for d in data]
    except (json.JSONDecodeError, OSError, TypeError) as e:
        logger.warning(f"Could not load calibration queue: {e}")
        return []


def save_pending_queue(items: List[CalibrationItem]) -> None:
    """Save the calibration queue to disk."""
    CALIBRATION_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = [item.to_dict() for item in items]
        PENDING_FILE.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )
    except OSError as e:
        logger.warning(f"Could not save calibration queue: {e}")


def consume_and_queue(
    findings_data: Dict[str, Any],
    audit_fn=None,
) -> ConsumptionResult:
    """Consume findings and append to persistent calibration queue.

    This is the main entry point. It:
    1. Validates and routes findings
    2. Loads existing queue
    3. Appends new items
    4. Saves back to disk
    """
    result = consume_findings(findings_data, audit_fn=audit_fn)

    if result.items:
        existing = load_pending_queue()
        existing.extend(result.items)
        # Sort by priority (lower = higher priority)
        existing.sort(key=lambda x: x.priority)
        save_pending_queue(existing)
        logger.info(
            f"Calibration queue: +{len(result.items)} items "
            f"({len(existing)} total pending)"
        )

    return result
