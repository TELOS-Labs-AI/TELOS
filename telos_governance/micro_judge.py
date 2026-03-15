"""
Micro-Judge -- Last-resort CLARIFY resolution via small/fast LLM.

CLARIFY Cascade Step 4: When Steps 1-3 (action enrichment, dimensional
escalation, precedent lookup) fail to resolve a CLARIFY verdict, the
micro-judge makes the final call using a small, fast model that is NOT
the governed agent's model (avoids self-evaluation loop).

Design constraints:
- Off by default (enabled: false in config)
- Never judges boundary_proximity (always needs human review)
- Fail-open on errors (keep CLARIFY, don't block the agent)
- Rate limited (default 10/hour)
- No new pip dependencies (uses httpx, already in tree)
- Config: ~/.telos/micro_judge.json

Provenance: P2 CLARIFY Cascade work order, Step 4.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".telos" / "micro_judge.json"

DEFAULT_CONFIG = {
    "enabled": False,
    "model": "claude-haiku-4-5-20251001",
    "provider": "anthropic",
    "api_key_env": "ANTHROPIC_API_KEY",
    "max_calls_per_hour": 10,
    "timeout_seconds": 5,
    "skip_dimensions": ["boundary_proximity"],
}

MICRO_JUDGE_PROMPT = """You are a governance micro-judge. Given an AI agent's purpose, scope, and boundaries, determine if the following action should be ALLOWED or BLOCKED.

Agent purpose: {purpose}
Agent scope: {scope}
Agent boundaries (abbreviated): {boundaries}

Action: Tool={tool_name}, Description={action_text}

Ambiguous dimension: {ambiguous_dimension} -- {clarify_description}

Respond with exactly one of: ALLOW or BLOCK
Then on a new line, give one sentence of reasoning."""


class MicroJudgeConfig:
    """Parsed micro-judge configuration."""

    def __init__(self, data: Optional[dict] = None):
        d = {**DEFAULT_CONFIG, **(data or {})}
        self.enabled: bool = bool(d.get("enabled", False))
        self.model: str = str(d.get("model", DEFAULT_CONFIG["model"]))
        self.provider: str = str(d.get("provider", "anthropic"))
        self.api_key_env: str = str(d.get("api_key_env", "ANTHROPIC_API_KEY"))
        self.max_calls_per_hour: int = int(d.get("max_calls_per_hour", 10))
        self.timeout_seconds: float = float(d.get("timeout_seconds", 5))
        self.skip_dimensions: list = list(d.get("skip_dimensions", ["boundary_proximity"]))


class MicroJudge:
    """CLARIFY resolution via small/fast LLM call.

    Off by default. Reads config from ``~/.telos/micro_judge.json``.
    Fail-open on all errors -- never blocks the agent due to judge failure.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        config: Optional[MicroJudgeConfig] = None,
    ):
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._config = config or self._load_config()
        self._call_timestamps: list = []  # monotonic timestamps of recent calls
        self._total_calls: int = 0
        self._total_allows: int = 0
        self._total_blocks: int = 0
        self._total_errors: int = 0

    def _load_config(self) -> MicroJudgeConfig:
        """Load config from disk. Returns defaults if file missing/corrupt."""
        try:
            if self._config_path.exists():
                raw = self._config_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                return MicroJudgeConfig(data)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load micro-judge config: %s", exc)
        return MicroJudgeConfig()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def _is_rate_limited(self) -> bool:
        """Check if we've exceeded max_calls_per_hour."""
        now = time.monotonic()
        cutoff = now - 3600.0
        # Prune old timestamps
        self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
        return len(self._call_timestamps) >= self._config.max_calls_per_hour

    def should_skip(self, ambiguous_dimension: str) -> bool:
        """Check if this dimension should skip the micro-judge."""
        return ambiguous_dimension in self._config.skip_dimensions

    def judge(
        self,
        tool_name: str,
        action_text: str,
        ambiguous_dimension: str,
        clarify_description: str,
        purpose: str = "",
        scope: str = "",
        boundaries: str = "",
    ) -> Tuple[Optional[str], str]:
        """Call the micro-judge LLM synchronously.

        Args:
            tool_name: Tool being scored.
            action_text: Action description.
            ambiguous_dimension: Which dimension was ambiguous (from Step 2).
            clarify_description: Human-readable description of ambiguity.
            purpose: Agent's purpose statement.
            scope: Agent's scope statement.
            boundaries: Abbreviated boundary list.

        Returns:
            Tuple of (decision, reasoning) where decision is "execute",
            "escalate", or None (on error/timeout/rate-limit).
            Reasoning is the model's one-sentence explanation.
        """
        if not self._config.enabled:
            return None, "micro-judge disabled"

        if self.should_skip(ambiguous_dimension):
            return None, f"skipped: {ambiguous_dimension} in skip_dimensions"

        if self._is_rate_limited():
            logger.info("Micro-judge rate limited (%d calls/hour)", self._config.max_calls_per_hour)
            return None, "rate limited"

        import os
        api_key = os.environ.get(self._config.api_key_env, "")
        if not api_key:
            logger.warning("Micro-judge: %s not set", self._config.api_key_env)
            return None, f"missing API key: {self._config.api_key_env}"

        prompt = MICRO_JUDGE_PROMPT.format(
            purpose=purpose[:500],
            scope=scope[:500],
            boundaries=boundaries[:500],
            tool_name=tool_name,
            action_text=action_text[:300],
            ambiguous_dimension=ambiguous_dimension,
            clarify_description=clarify_description,
        )

        try:
            decision, reasoning = self._call_anthropic(api_key, prompt)
            self._call_timestamps.append(time.monotonic())
            self._total_calls += 1

            if decision == "execute":
                self._total_allows += 1
            elif decision == "escalate":
                self._total_blocks += 1
            else:
                self._total_errors += 1

            return decision, reasoning

        except Exception as exc:
            logger.warning("Micro-judge call failed (fail-open): %s", exc)
            self._total_errors += 1
            return None, f"error: {exc}"

    def _call_anthropic(self, api_key: str, prompt: str) -> Tuple[Optional[str], str]:
        """Make synchronous Anthropic API call via httpx."""
        import httpx

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self._config.model,
                "max_tokens": 100,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=self._config.timeout_seconds,
        )
        response.raise_for_status()

        data = response.json()
        text = data.get("content", [{}])[0].get("text", "").strip()
        return self._parse_response(text)

    @staticmethod
    def _parse_response(text: str) -> Tuple[Optional[str], str]:
        """Parse the model's ALLOW/BLOCK response.

        Returns (decision, reasoning). Decision is "execute" for ALLOW,
        "escalate" for BLOCK, None for parse failure.
        """
        if not text:
            return None, "empty response"

        lines = text.strip().split("\n", 1)
        first_line = lines[0].strip().upper()
        reasoning = lines[1].strip() if len(lines) > 1 else ""

        if "ALLOW" in first_line:
            return "execute", reasoning
        elif "BLOCK" in first_line:
            return "escalate", reasoning
        else:
            return None, f"unparseable: {first_line}"

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "micro_judge_enabled": self._config.enabled,
            "micro_judge_calls": self._total_calls,
            "micro_judge_allows": self._total_allows,
            "micro_judge_blocks": self._total_blocks,
            "micro_judge_errors": self._total_errors,
        }
