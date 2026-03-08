"""
PA Context — System prompt injection with cryptographic integrity.

Generates PA injection blocks for inclusion in model system prompts.
The PA is a known, fixed document — NOT RAG retrieval. Precompute at
session start, invalidate only on PA change (Ed25519 ceremony).

The hash chain: signed PA → injection block → hash verification every turn.
This creates the PA Injection Integrity Record — a novel compliance artifact
that proves the model had the governance specification in context when it
generated its response.

Two modes:
  - Full mode (~4-8k tokens): Complete PA for large context windows (200k+)
  - Compressed mode (~2k tokens): Essential constraints for small windows (32k)

Usage:
    from telos_governance.pa_context import PAContext

    ctx = PAContext.from_config("templates/agent.yaml")
    block = ctx.get_injection_block()           # full mode
    block = ctx.get_injection_block(compressed=True)  # compressed

    # Verify integrity every turn
    assert ctx.verify_injection_integrity(block, ctx.injection_hash)

Compliance:
  - NIST AI 600-1 (GV 1.4): PA specification present in model context
  - EU AI Act Art. 72: Verifiable governance context per response
  - Pre-generation semantic alignment layer (safety-by-design principle)
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class PAContext:
    """
    PA injection context — generates and verifies PA blocks for system prompts.

    Precomputed at session start. Cached until PA changes.
    """

    # Source data (from YAML)
    agent_name: str = ""
    purpose: str = ""
    scope: str = ""
    boundaries: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    constraints: dict = field(default_factory=dict)
    safe_exemplars: list = field(default_factory=list)

    # Integrity
    config_path: str = ""
    config_hash: str = ""  # SHA-256 of the raw YAML file

    # Cached injection blocks (precomputed)
    _full_block: str = ""
    _compressed_block: str = ""
    _injection_hash: str = ""  # SHA-256 of the full injection block

    # Alternating-treatment experiment
    # When enabled, PA injection can be toggled per-turn for experimental design.
    # The pa_injected field on GovernanceEvent records which condition each turn used.
    injection_enabled: bool = True
    alternating_mode: bool = False  # If True, alternate injection per turn
    _turn_counter: int = 0

    @classmethod
    def from_config(cls, config_path: str) -> "PAContext":
        """Load PAContext from a YAML configuration file."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"PA config not found: {config_path}")

        raw_yaml = path.read_text(encoding="utf-8")
        config_hash = hashlib.sha256(raw_yaml.encode("utf-8")).hexdigest()

        data = yaml.safe_load(raw_yaml)
        agent = data.get("agent", {})
        purpose_block = data.get("purpose", {})
        boundaries_raw = data.get("boundaries", [])
        tools_raw = data.get("tools", [])
        constraints_raw = data.get("constraints", {})

        scope_raw = data.get("scope", "")
        scope_str = scope_raw.get("statement", "") if isinstance(scope_raw, dict) else str(scope_raw)

        ctx = cls(
            agent_name=agent.get("name", agent.get("id", "")),
            purpose=purpose_block.get("statement", "") if isinstance(purpose_block, dict) else str(purpose_block),
            scope=scope_str,
            boundaries=[
                {"text": b.get("text", b) if isinstance(b, dict) else str(b),
                 "severity": b.get("severity", "hard") if isinstance(b, dict) else "hard"}
                for b in boundaries_raw
            ],
            tools=[
                {"name": t.get("name", ""), "description": t.get("description", ""),
                 "risk_level": t.get("risk_level", "low")}
                for t in tools_raw
            ],
            constraints=constraints_raw,
            safe_exemplars=data.get("safe_exemplars", []),
            config_path=str(path.resolve()),
            config_hash=config_hash,
        )

        # Precompute injection blocks
        ctx._full_block = ctx._build_full_block()
        ctx._compressed_block = ctx._build_compressed_block()
        ctx._injection_hash = hashlib.sha256(
            ctx._full_block.encode("utf-8")
        ).hexdigest()

        logger.info(
            "PAContext loaded: %s (%d boundaries, %d tools, hash=%s…)",
            ctx.agent_name, len(ctx.boundaries), len(ctx.tools),
            ctx.config_hash[:12],
        )
        return ctx

    @property
    def injection_hash(self) -> str:
        """SHA-256 hash of the full injection block."""
        return self._injection_hash

    def get_injection_block(self, compressed: bool = False) -> str:
        """
        Return formatted PA text for system prompt injection.

        Args:
            compressed: If True, return ~2k token version for small context
                        windows (32k). Otherwise full version for 200k+ windows.
        """
        return self._compressed_block if compressed else self._full_block

    def get_injection_hash(self) -> str:
        """Return SHA-256 hash of the full injection block."""
        return self._injection_hash

    def verify_injection_integrity(
        self, injection_block: str, expected_hash: str
    ) -> bool:
        """
        Verify that an injection block matches the expected hash.

        This is called every turn to ensure the PA in the model's context
        has not been tampered with since session start.
        """
        actual_hash = hashlib.sha256(
            injection_block.encode("utf-8")
        ).hexdigest()
        return actual_hash == expected_hash

    def should_inject(self) -> bool:
        """
        Determine whether PA should be injected for the current turn.

        In normal mode: returns injection_enabled.
        In alternating mode: alternates between injected/not-injected per turn.
        The model has no memory between turns, so toggling is clean (zero hysteresis).
        """
        if not self.injection_enabled:
            return False
        if not self.alternating_mode:
            return True
        # Alternating: even turns injected, odd turns not
        return self._turn_counter % 2 == 0

    def advance_turn(self) -> bool:
        """
        Advance the turn counter and return whether PA should be injected.

        Returns the injection decision for the NEW turn.
        """
        self._turn_counter += 1
        inject = self.should_inject()
        logger.debug(
            "PA injection turn %d: %s (alternating=%s)",
            self._turn_counter, inject, self.alternating_mode,
        )
        return inject

    def get_injection_block_for_turn(self, compressed: bool = False) -> Optional[str]:
        """
        Return the injection block if PA should be injected this turn, else None.

        Combines should_inject() check with block retrieval in one call.
        """
        if not self.should_inject():
            return None
        return self.get_injection_block(compressed=compressed)

    def _build_full_block(self) -> str:
        """Build the full PA injection block (~4-8k tokens)."""
        lines = [
            "=== GOVERNANCE SPECIFICATION (PA) ===",
            f"Agent: {self.agent_name}",
            f"Config Hash: {self.config_hash[:16]}",
            "",
            f"PURPOSE: {self.purpose}",
            "",
            f"SCOPE: {self.scope}",
            "",
        ]

        if self.boundaries:
            lines.append("BOUNDARIES (hard constraints — violations trigger escalation):")
            for i, b in enumerate(self.boundaries, 1):
                severity = b.get("severity", "hard").upper()
                lines.append(f"  {i}. [{severity}] {b['text']}")
            lines.append("")

        if self.tools:
            lines.append("AUTHORIZED TOOLS:")
            for t in self.tools:
                risk = t.get("risk_level", "low").upper()
                lines.append(f"  - {t['name']} [{risk}]: {t['description']}")
            lines.append("")

        if self.constraints:
            lines.append("CONSTRAINTS:")
            for key, val in self.constraints.items():
                lines.append(f"  {key}: {val}")
            lines.append("")

        lines.append(
            "Every action you take is measured against this specification. "
            "Stay within scope. Respect boundaries. Use authorized tools "
            "for their intended purpose."
        )
        lines.append("=== END GOVERNANCE SPECIFICATION ===")

        return "\n".join(lines)

    def _build_compressed_block(self) -> str:
        """Build compressed PA injection block (~2k tokens)."""
        lines = [
            "=== PA ===",
            f"Purpose: {self.purpose[:200]}",
            f"Scope: {self.scope[:200]}",
        ]

        if self.boundaries:
            # Only hard boundaries in compressed mode
            hard = [b for b in self.boundaries if b.get("severity") == "hard"]
            if hard:
                lines.append("Boundaries:")
                for b in hard[:10]:  # Cap at 10 for token budget
                    lines.append(f"  - {b['text'][:120]}")

        if self.tools:
            tool_names = [t["name"] for t in self.tools]
            lines.append(f"Tools: {', '.join(tool_names)}")

        lines.append("Stay within scope. Respect boundaries.")
        lines.append("=== END PA ===")

        return "\n".join(lines)
