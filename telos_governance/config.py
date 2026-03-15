"""
TELOS Configuration -- YAML-based PA configuration for CLI.

Loads agent governance configuration from .yaml files and validates
against the required schema. Configurations map directly to AgenticPA
construction parameters.

Schema:
  agent:
    id: str (required)
    name: str (required)
    description: str (optional)
  purpose:
    statement: str (required)
    example_requests: list[str] (optional, improves centroid quality)
  scope: str (required)
  boundaries:
    - text: str (required)
      severity: "hard" | "soft" (default: "hard")
  safe_exemplars: list[str] (optional, for contrastive FPR reduction)
  violation_keywords: list[str] (optional, domain-specific violation indicators)
  tools:
    - name: str (required)
      description: str (required)
      risk_level: "low" | "medium" | "high" | "critical" (default: "low")
  constraints:
    max_chain_length: int (default: 20)
    max_tool_calls_per_step: int (default: 5)
    escalation_threshold: float (default: 0.50)
    require_human_above_risk: "low" | "medium" | "high" | "critical" (default: "high")
  setfit:  (optional -- L1.5 boundary classifier)
    enabled: bool (default: false)
    model_dir: str (required if enabled)
    calibration: str (optional -- path to calibration JSON)
    threshold: float (default: 0.50)
    asymmetric_override: bool (default: true)

Compliance:
- NIST AI 600-1 (GV 1.4): Declarative YAML configuration implements "governance
  by design" -- the PA specification IS the governance policy document. NIST 600-1
  requires documented governance policies for GenAI systems; the YAML config is
  that document in machine-readable, version-controllable form.
- IEEE P7000 (Model Process for Addressing Ethical Concerns): Configuration schema
  encodes ethical requirements (boundaries, escalation rules, human-in-the-loop
  thresholds) as first-class fields, not comments or documentation addenda.
- NIST AI RMF (MAP 1.1): The config schema maps directly to MAP 1.1's requirement
  for documenting "intended purposes, potentially beneficial uses, and context of
  use" -- purpose.statement, scope, and constraints define the operational context.
- OWASP LLM Top 10 (LLM08 -- Excessive Agency): The constraints section (max chain
  length, escalation threshold, require_human_above_risk) directly constrains
  agent autonomy through declarative configuration rather than runtime logic.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Valid values for constrained fields
VALID_SEVERITIES = {"hard", "soft"}
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}

# Templates directory relative to this file
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Template registry -- single source of truth for available configs
TEMPLATE_REGISTRY = {
    # Generic
    "default": {
        "file": "default_config.yaml",
        "domain": "General",
        "name": "Default Template",
        "description": "Blank starter template -- customize for any agent",
    },
    # Property Intelligence
    "property-intel": {
        "file": "property_intel.yaml",
        "domain": "Insurance",
        "name": "Property Intelligence Agent",
        "description": "Aerial imagery + risk scoring for insurance underwriting",
    },
    # Healthcare
    "healthcare-ambient": {
        "file": "healthcare/healthcare_ambient.yaml",
        "domain": "Healthcare",
        "name": "Ambient Clinical Documentation",
        "description": "AI scribe for provider-patient encounters (DAX, Abridge)",
    },
    "healthcare-call-center": {
        "file": "healthcare/healthcare_call_center.yaml",
        "domain": "Healthcare",
        "name": "Patient Call Center Agent",
        "description": "Agentic call routing, triage, and scheduling",
    },
    "healthcare-coding": {
        "file": "healthcare/healthcare_coding.yaml",
        "domain": "Healthcare",
        "name": "Clinical Coding Assistant",
        "description": "ICD-10/CPT code suggestion with clinician review",
    },
    "healthcare-diagnostic": {
        "file": "healthcare/healthcare_diagnostic_ai.yaml",
        "domain": "Healthcare",
        "name": "Diagnostic AI Assistant",
        "description": "Imaging + lab interpretation for clinical decision support",
    },
    "healthcare-patient": {
        "file": "healthcare/healthcare_patient_facing.yaml",
        "domain": "Healthcare",
        "name": "Patient-Facing AI",
        "description": "Chatbot for patient intake, symptom checking, portal Q&A",
    },
    "healthcare-predictive": {
        "file": "healthcare/healthcare_predictive.yaml",
        "domain": "Healthcare",
        "name": "Predictive Analytics Agent",
        "description": "Readmission risk, sepsis early warning, population health",
    },
    "healthcare-therapeutic": {
        "file": "healthcare/healthcare_therapeutic.yaml",
        "domain": "Healthcare",
        "name": "Therapeutic Decision Support",
        "description": "Treatment protocol + drug interaction + dosing guidance",
    },
    # Civic Services
    "civic-services": {
        "file": "civic_services.yaml",
        "domain": "Government",
        "name": "Civic Services Agent",
        "description": "Municipal government services, eligibility screening, and citizen assistance",
    },
    # Solar / AECO
    "solar-site-assessor": {
        "file": "solar_site_assessor.yaml",
        "domain": "Solar / AECO",
        "name": "Solar Site Assessment Agent",
        "description": "Site feasibility, performance modeling, and permitting for solar installations",
    },
    # Cloud Platform
    "vultr-enterprise-analyst": {
        "file": "vultr_governed_cloud.yaml",
        "domain": "Cloud Platform",
        "name": "Enterprise Data Analyst (Vultr)",
        "description": "Generic enterprise analyst -- TELOS governance sidecar on Vultr cloud",
    },
}


def list_templates():
    """Return template registry grouped by domain.

    Returns:
        Dict mapping domain names to lists of (key, metadata) tuples.
    """
    grouped = {}
    for key, meta in TEMPLATE_REGISTRY.items():
        domain = meta["domain"]
        grouped.setdefault(domain, []).append((key, meta))
    return grouped


def get_template_path(name: str) -> Path:
    """Resolve a template short name to its absolute file path.

    Args:
        name: Template key from TEMPLATE_REGISTRY.

    Returns:
        Absolute Path to the template YAML file.

    Raises:
        KeyError: If name is not in the registry.
        FileNotFoundError: If the template file doesn't exist on disk.
    """
    if name not in TEMPLATE_REGISTRY:
        raise KeyError(f"Unknown template: '{name}'. Available: {', '.join(TEMPLATE_REGISTRY)}")
    src = _TEMPLATES_DIR / TEMPLATE_REGISTRY[name]["file"]
    if not src.exists():
        raise FileNotFoundError(f"Template file missing: {src}")
    return src


@dataclass
class BoundaryConfig:
    """A single boundary from configuration."""
    text: str
    severity: str = "hard"


@dataclass
class ToolConfig:
    """A single tool definition from configuration."""
    name: str
    description: str
    risk_level: str = "low"


@dataclass
class ConstraintsConfig:
    """Operational constraints from configuration."""
    max_chain_length: int = 20
    max_tool_calls_per_step: int = 5
    escalation_threshold: float = 0.50
    require_human_above_risk: str = "high"


@dataclass
class SetFitConfig:
    """SetFit L1.5 boundary classifier configuration.

    Enables domain-specific SetFit models to be loaded from YAML config
    rather than hardcoded paths. Each domain (healthcare, openclaw, etc.)
    can specify its own trained SetFit model.

    YAML format:
      setfit:
        enabled: true
        model_dir: models/setfit_openclaw_v1
        threshold: 0.50
        asymmetric_override: true
    """
    enabled: bool = False
    model_dir: str = ""
    calibration: str = ""  # Path to calibration JSON (optional, auto-detected from model_dir)
    threshold: float = 0.50
    asymmetric_override: bool = True  # SetFit can escalate but never downgrade
    composite_boost: bool = False  # Enable legitimacy modulation in composite scoring

    def __post_init__(self):
        if self.enabled and self.model_dir:
            # Validate model_dir does not contain path traversal components
            model_path = Path(self.model_dir)
            if ".." in model_path.parts:
                raise ValueError(f"setfit.model_dir must not contain '..': {self.model_dir}")
        if self.enabled and self.calibration:
            cal_path = Path(self.calibration)
            if ".." in cal_path.parts:
                raise ValueError(f"setfit.calibration must not contain '..': {self.calibration}")


@dataclass
class NotificationsConfig:
    """Permission controller notification configuration.

    Configures how ESCALATE verdicts are communicated to the human operator
    and how override responses are collected. Supports Telegram (interactive
    buttons), WhatsApp (interactive buttons via Cloud API), and Discord
    (notification-only in v1).

    YAML format:
      notifications:
        telegram_bot_token: "123456:ABC-DEF..."
        telegram_chat_id: "987654321"
        discord_webhook_url: "https://discord.com/api/webhooks/..."
        whatsapp_phone_number_id: "1234567890"
        whatsapp_access_token: "EAAx..."
        whatsapp_recipient_number: "+1234567890"
        escalation_timeout_seconds: 300
        timeout_action: "deny"

    Regulatory traceability:
        - EU AI Act Art. 14: Human oversight via real-time notification
        - EU AI Act Art. 72: Override receipts for post-market audit
        - SAAI claim TELOS-SAAI-009: Human-in-the-loop for ESCALATE decisions
    """
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_recipient_number: str = ""
    escalation_timeout_seconds: int = 300
    timeout_action: str = "deny"  # "deny" (fail-closed) only. "allow" (fail-open) is unsafe and deprecated.

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_discord(self) -> bool:
        return bool(self.discord_webhook_url)

    @property
    def has_whatsapp(self) -> bool:
        return bool(self.whatsapp_phone_number_id and self.whatsapp_access_token
                     and self.whatsapp_recipient_number)

    @property
    def has_any_channel(self) -> bool:
        return self.has_telegram or self.has_discord or self.has_whatsapp


@dataclass
class AgentConfig:
    """Complete agent configuration loaded from YAML."""
    # Identity
    agent_id: str
    agent_name: str
    description: str = ""

    # Governance dimensions
    purpose: str = ""
    scope: str = ""
    example_requests: List[str] = field(default_factory=list)
    scope_example_requests: List[str] = field(default_factory=list)
    boundaries: List[BoundaryConfig] = field(default_factory=list)
    safe_exemplars: List[str] = field(default_factory=list)
    violation_keywords: List[str] = field(default_factory=list)
    tools: List[ToolConfig] = field(default_factory=list)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    setfit: Optional[SetFitConfig] = None
    notifications: Optional[NotificationsConfig] = None

    # Construction mode: "legacy" (default) or "tool_grounded" (Gate 1 + Gate 2)
    construction_mode: str = "legacy"

    # Demo overrides: scoring adjustments for standalone demo feeds
    # chain_weight: 0.0 disables chain continuity (no conversational context)
    demo_overrides: Dict[str, Any] = field(default_factory=dict)

    # Source tracking
    config_path: Optional[str] = None


class ConfigValidationError(Exception):
    """Raised when a configuration file fails validation."""

    def __init__(self, errors: List[str], path: Optional[str] = None):
        self.errors = errors
        self.path = path
        msg = f"Configuration validation failed ({len(errors)} error(s))"
        if path:
            msg += f" in {path}"
        msg += ":\n  " + "\n  ".join(errors)
        super().__init__(msg)


def _validate_raw_config(data: Dict[str, Any]) -> List[str]:
    """Validate raw YAML data against the schema. Returns list of error strings."""
    errors = []

    # --- agent section (required) ---
    agent = data.get("agent")
    if not agent or not isinstance(agent, dict):
        errors.append("Missing required section: 'agent'")
    else:
        if not agent.get("id"):
            errors.append("Missing required field: agent.id")
        if not agent.get("name"):
            errors.append("Missing required field: agent.name")

    # --- purpose section (required) ---
    purpose = data.get("purpose")
    if not purpose:
        errors.append("Missing required section: 'purpose'")
    elif isinstance(purpose, dict):
        if not purpose.get("statement"):
            errors.append("Missing required field: purpose.statement")
        ex = purpose.get("example_requests")
        if ex is not None and not isinstance(ex, list):
            errors.append("purpose.example_requests must be a list")
    elif isinstance(purpose, str):
        pass  # Simple string form is allowed
    else:
        errors.append("'purpose' must be a string or a mapping with 'statement'")

    # --- scope (required) ---
    scope = data.get("scope")
    if not scope:
        errors.append("Missing required field: 'scope'")
    elif isinstance(scope, dict):
        if not scope.get("statement"):
            errors.append("Missing required field: scope.statement")
        ex = scope.get("example_requests")
        if ex is not None and not isinstance(ex, list):
            errors.append("scope.example_requests must be a list")
    elif isinstance(scope, str):
        pass  # Simple string form is allowed
    else:
        errors.append("'scope' must be a string or a mapping with 'statement'")

    # --- boundaries (optional but recommended) ---
    boundaries = data.get("boundaries")
    if boundaries is not None:
        if not isinstance(boundaries, list):
            errors.append("'boundaries' must be a list")
        else:
            for i, b in enumerate(boundaries):
                if isinstance(b, str):
                    continue  # Simple string form
                elif isinstance(b, dict):
                    if not b.get("text"):
                        errors.append(f"boundaries[{i}]: missing required field 'text'")
                    sev = b.get("severity", "hard")
                    if sev not in VALID_SEVERITIES:
                        errors.append(
                            f"boundaries[{i}]: severity must be one of {VALID_SEVERITIES}, got '{sev}'"
                        )
                else:
                    errors.append(f"boundaries[{i}]: must be a string or mapping")

    # --- safe_exemplars (optional) ---
    safe = data.get("safe_exemplars")
    if safe is not None:
        if not isinstance(safe, list):
            errors.append("'safe_exemplars' must be a list of strings")

    # --- violation_keywords (optional) ---
    vk = data.get("violation_keywords")
    if vk is not None:
        if not isinstance(vk, list):
            errors.append("'violation_keywords' must be a list of strings")
        else:
            for i, kw in enumerate(vk):
                if not isinstance(kw, str) or not kw.strip():
                    errors.append(f"violation_keywords[{i}]: must be a non-empty string")

    # --- tools (optional) ---
    tools = data.get("tools")
    if tools is not None:
        if not isinstance(tools, list):
            errors.append("'tools' must be a list")
        else:
            for i, t in enumerate(tools):
                if not isinstance(t, dict):
                    errors.append(f"tools[{i}]: must be a mapping")
                    continue
                if not t.get("name"):
                    errors.append(f"tools[{i}]: missing required field 'name'")
                if not t.get("description"):
                    errors.append(f"tools[{i}]: missing required field 'description'")
                rl = t.get("risk_level", "low")
                if rl not in VALID_RISK_LEVELS:
                    errors.append(
                        f"tools[{i}]: risk_level must be one of {VALID_RISK_LEVELS}, got '{rl}'"
                    )

    # --- constraints (optional) ---
    constraints = data.get("constraints")
    if constraints is not None:
        if not isinstance(constraints, dict):
            errors.append("'constraints' must be a mapping")
        else:
            mcl = constraints.get("max_chain_length")
            if mcl is not None and (not isinstance(mcl, int) or mcl < 1):
                errors.append("constraints.max_chain_length must be a positive integer")
            mtc = constraints.get("max_tool_calls_per_step")
            if mtc is not None and (not isinstance(mtc, int) or mtc < 1):
                errors.append("constraints.max_tool_calls_per_step must be a positive integer")
            et = constraints.get("escalation_threshold")
            if et is not None and (not isinstance(et, (int, float)) or et < 0 or et > 1):
                errors.append("constraints.escalation_threshold must be a float between 0 and 1")
            rhar = constraints.get("require_human_above_risk")
            if rhar is not None and rhar not in VALID_RISK_LEVELS:
                errors.append(
                    f"constraints.require_human_above_risk must be one of {VALID_RISK_LEVELS}"
                )

    # --- setfit section (optional) ---
    setfit = data.get("setfit")
    if setfit is not None:
        if not isinstance(setfit, dict):
            errors.append("'setfit' must be a mapping")
        else:
            enabled = setfit.get("enabled")
            if enabled is not None and not isinstance(enabled, bool):
                errors.append("setfit.enabled must be a boolean")
            model_dir = setfit.get("model_dir")
            if enabled and not model_dir:
                errors.append("setfit.model_dir is required when setfit.enabled is true")
            threshold = setfit.get("threshold")
            if threshold is not None and (
                not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1
            ):
                errors.append("setfit.threshold must be a float between 0 and 1")
            ao = setfit.get("asymmetric_override")
            if ao is not None and not isinstance(ao, bool):
                errors.append("setfit.asymmetric_override must be a boolean")
            cb = setfit.get("composite_boost")
            if cb is not None and not isinstance(cb, bool):
                errors.append("setfit.composite_boost must be a boolean")

    # --- notifications section (optional) ---
    notifications = data.get("notifications")
    if notifications is not None:
        if not isinstance(notifications, dict):
            errors.append("'notifications' must be a mapping")
        else:
            timeout = notifications.get("escalation_timeout_seconds")
            if timeout is not None and (not isinstance(timeout, int) or timeout < 1):
                errors.append("notifications.escalation_timeout_seconds must be a positive integer")
            ta = notifications.get("timeout_action")
            if ta is not None and ta not in ("deny", "allow"):
                errors.append("notifications.timeout_action must be 'deny' or 'allow'")

    return errors


def _parse_config(data: Dict[str, Any], path: Optional[str] = None) -> AgentConfig:
    """Parse validated raw YAML data into an AgentConfig."""
    agent = data.get("agent", {})

    # Purpose: accept both string and dict forms
    purpose_raw = data.get("purpose", "")
    if isinstance(purpose_raw, dict):
        purpose_text = purpose_raw.get("statement", "")
        example_requests = purpose_raw.get("example_requests", [])
    else:
        purpose_text = str(purpose_raw)
        example_requests = []

    # Scope: accept both string and dict forms (like purpose)
    scope_raw = data.get("scope", "")
    if isinstance(scope_raw, dict):
        scope_text = scope_raw.get("statement", "")
        scope_example_requests = scope_raw.get("example_requests", [])
    else:
        scope_text = str(scope_raw)
        scope_example_requests = []

    # Boundaries: accept both string and dict forms
    boundaries = []
    for b in data.get("boundaries", []):
        if isinstance(b, str):
            boundaries.append(BoundaryConfig(text=b))
        elif isinstance(b, dict):
            boundaries.append(BoundaryConfig(
                text=b["text"],
                severity=b.get("severity", "hard"),
            ))

    # Tools
    tools = []
    for t in data.get("tools", []):
        tools.append(ToolConfig(
            name=t["name"],
            description=t["description"],
            risk_level=t.get("risk_level", "low"),
        ))

    # Constraints
    constraints_raw = data.get("constraints", {})
    constraints = ConstraintsConfig(
        max_chain_length=constraints_raw.get("max_chain_length", 20),
        max_tool_calls_per_step=constraints_raw.get("max_tool_calls_per_step", 5),
        escalation_threshold=constraints_raw.get("escalation_threshold", 0.50),
        require_human_above_risk=constraints_raw.get("require_human_above_risk", "high"),
    )

    # SetFit config (optional)
    setfit_raw = data.get("setfit")
    setfit_config = None
    if setfit_raw and isinstance(setfit_raw, dict):
        setfit_config = SetFitConfig(
            enabled=setfit_raw.get("enabled", False),
            model_dir=setfit_raw.get("model_dir", ""),
            calibration=setfit_raw.get("calibration", ""),
            threshold=setfit_raw.get("threshold", 0.50),
            asymmetric_override=setfit_raw.get("asymmetric_override", True),
            composite_boost=setfit_raw.get("composite_boost", False),
        )

    # Notifications config (optional)
    notif_raw = data.get("notifications")
    notif_config = None
    if notif_raw and isinstance(notif_raw, dict):
        notif_config = NotificationsConfig(
            telegram_bot_token=notif_raw.get("telegram_bot_token", ""),
            telegram_chat_id=str(notif_raw.get("telegram_chat_id", "")),
            discord_webhook_url=notif_raw.get("discord_webhook_url", ""),
            whatsapp_phone_number_id=notif_raw.get("whatsapp_phone_number_id", ""),
            whatsapp_access_token=notif_raw.get("whatsapp_access_token", ""),
            whatsapp_recipient_number=notif_raw.get("whatsapp_recipient_number", ""),
            escalation_timeout_seconds=notif_raw.get("escalation_timeout_seconds", 300),
            timeout_action=notif_raw.get("timeout_action", "deny"),
        )

    # Demo overrides (optional)
    demo_overrides = data.get("demo_overrides", {})
    if not isinstance(demo_overrides, dict):
        demo_overrides = {}

    return AgentConfig(
        agent_id=agent.get("id", ""),
        agent_name=agent.get("name", ""),
        description=agent.get("description", ""),
        purpose=purpose_text,
        scope=scope_text,
        example_requests=example_requests,
        scope_example_requests=scope_example_requests,
        boundaries=boundaries,
        safe_exemplars=data.get("safe_exemplars", []),
        violation_keywords=data.get("violation_keywords", []),
        tools=tools,
        constraints=constraints,
        setfit=setfit_config,
        notifications=notif_config,
        construction_mode=agent.get("construction_mode", "legacy"),
        demo_overrides=demo_overrides,
        config_path=path,
    )


def load_config(path: str) -> AgentConfig:
    """Load and validate a TELOS agent configuration from a YAML file.

    Args:
        path: Path to .yaml configuration file.

    Returns:
        Validated AgentConfig.

    Raises:
        FileNotFoundError: If the file does not exist.
        ConfigValidationError: If validation fails.
        ImportError: If pyyaml is not installed.
    """
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "TELOS config requires the 'pyyaml' package. "
            "Install with: pip install telos[cli]"
        )

    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Configuration file not found: {resolved}")

    with open(resolved) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ConfigValidationError(
            ["File must contain a YAML mapping (not a list or scalar)"],
            path=str(resolved),
        )

    errors = _validate_raw_config(data)
    if errors:
        raise ConfigValidationError(errors, path=str(resolved))

    config = _parse_config(data, path=str(resolved))
    logger.info("Loaded configuration for agent '%s' from %s", config.agent_name, resolved)
    return config


def validate_config(path: str) -> Tuple[bool, List[str]]:
    """Validate a configuration file without loading it fully.

    Returns:
        Tuple of (is_valid, list of error messages).
    """
    try:
        import yaml
    except ImportError:
        return False, ["pyyaml is not installed. Install with: pip install telos[cli]"]

    resolved = Path(path).resolve()
    if not resolved.exists():
        return False, [f"File not found: {resolved}"]

    try:
        with open(resolved) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return False, [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return False, ["File must contain a YAML mapping (not a list or scalar)"]

    errors = _validate_raw_config(data)
    return len(errors) == 0, errors
