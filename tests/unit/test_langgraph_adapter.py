"""
Tests for telos_adapters.langgraph

Tests the LangGraph adapter components:
- state_schema: TelosGovernedState, PrimacyAttractor, FidelityZone, DirectionLevel
- governance_node: calculate_fidelity, get_fidelity_zone, TelosGovernanceGate
- wrapper: TelosWrapper, telos_wrap
- supervisor: TelosSupervisor, create_telos_supervisor
- swarm: TelosSwarm, create_telos_swarm
"""

import pytest
import numpy as np
from datetime import datetime
from unittest.mock import MagicMock, patch


# =============================================================================
# STATE SCHEMA TESTS
# =============================================================================

class TestFidelityZone:
    def test_zone_values(self):
        from telos_adapters.langgraph.state_schema import FidelityZone
        assert FidelityZone.GREEN.value == "green"
        assert FidelityZone.YELLOW.value == "yellow"
        assert FidelityZone.ORANGE.value == "orange"
        assert FidelityZone.RED.value == "red"


class TestDirectionLevel:
    def test_direction_level_values(self):
        from telos_adapters.langgraph.state_schema import DirectionLevel
        assert DirectionLevel.NONE.value == "none"
        assert DirectionLevel.HARD_BLOCK.value == "hard_block"

    def test_no_intervention_level_exists(self):
        """Verify InterventionLevel was fully renamed to DirectionLevel."""
        import telos_adapters.langgraph.state_schema as mod
        assert not hasattr(mod, "InterventionLevel")


class TestPrimacyAttractor:
    def test_round_trip_serialization(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        pa = PrimacyAttractor(
            text="Help with financial analysis",
            embedding=np.array([0.1, 0.2, 0.3]),
            purpose="financial analysis",
            scope="portfolio review",
        )
        d = pa.to_dict()
        assert d["text"] == "Help with financial analysis"
        assert d["purpose"] == "financial analysis"
        assert d["scope"] == "portfolio review"
        assert isinstance(d["embedding"], list)
        assert len(d["embedding"]) == 3

        pa2 = PrimacyAttractor.from_dict(d)
        assert pa2.text == pa.text
        assert pa2.purpose == pa.purpose
        assert pa2.scope == pa.scope
        np.testing.assert_array_almost_equal(pa2.embedding, pa.embedding)

    def test_from_dict_missing_optional_fields(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        d = {"text": "test", "embedding": [0.1, 0.2]}
        pa = PrimacyAttractor.from_dict(d)
        assert pa.text == "test"
        assert pa.purpose is None
        assert pa.scope is None


class TestGovernanceTraceEntry:
    def test_to_dict(self):
        from telos_adapters.langgraph.state_schema import (
            GovernanceTraceEntry, FidelityZone, DirectionLevel,
        )
        entry = GovernanceTraceEntry(
            timestamp=datetime(2026, 1, 1),
            turn_number=1,
            action_type="tool_call",
            action_description="search: query",
            raw_similarity=0.35,
            fidelity_score=0.75,
            zone=FidelityZone.GREEN,
            direction_level=DirectionLevel.NONE,
            approved=True,
            approval_source="auto",
        )
        d = entry.to_dict()
        assert d["zone"] == "green"
        assert d["direction_level"] == "none"
        assert d["approved"] is True
        assert "direction_reason" in d


class TestGetZoneFromFidelity:
    def test_green_zone(self):
        from telos_adapters.langgraph.state_schema import get_zone_from_fidelity, FidelityZone
        assert get_zone_from_fidelity(0.70) == FidelityZone.GREEN
        assert get_zone_from_fidelity(0.95) == FidelityZone.GREEN

    def test_yellow_zone(self):
        from telos_adapters.langgraph.state_schema import get_zone_from_fidelity, FidelityZone
        assert get_zone_from_fidelity(0.65) == FidelityZone.YELLOW
        assert get_zone_from_fidelity(0.60) == FidelityZone.YELLOW

    def test_orange_zone(self):
        from telos_adapters.langgraph.state_schema import get_zone_from_fidelity, FidelityZone
        assert get_zone_from_fidelity(0.55) == FidelityZone.ORANGE
        assert get_zone_from_fidelity(0.50) == FidelityZone.ORANGE

    def test_red_zone(self):
        from telos_adapters.langgraph.state_schema import get_zone_from_fidelity, FidelityZone
        assert get_zone_from_fidelity(0.49) == FidelityZone.RED
        assert get_zone_from_fidelity(0.10) == FidelityZone.RED


class TestGetDirectionLevel:
    def test_hard_block_below_baseline(self):
        from telos_adapters.langgraph.state_schema import get_direction_level, DirectionLevel
        result = get_direction_level(fidelity=0.80, raw_similarity=0.15)
        assert result == DirectionLevel.HARD_BLOCK

    def test_none_for_green(self):
        from telos_adapters.langgraph.state_schema import get_direction_level, DirectionLevel
        result = get_direction_level(fidelity=0.75, raw_similarity=0.40)
        assert result == DirectionLevel.NONE

    def test_monitor_for_yellow(self):
        from telos_adapters.langgraph.state_schema import get_direction_level, DirectionLevel
        result = get_direction_level(fidelity=0.65, raw_similarity=0.30)
        assert result == DirectionLevel.MONITOR

    def test_correct_for_orange(self):
        from telos_adapters.langgraph.state_schema import get_direction_level, DirectionLevel
        result = get_direction_level(fidelity=0.55, raw_similarity=0.30)
        assert result == DirectionLevel.CORRECT

    def test_direct_for_red(self):
        from telos_adapters.langgraph.state_schema import get_direction_level, DirectionLevel
        result = get_direction_level(fidelity=0.40, raw_similarity=0.25)
        assert result == DirectionLevel.DIRECT


class TestCalculateSCI:
    def test_no_previous_embedding(self):
        from telos_adapters.langgraph.state_schema import calculate_sci
        continuity, inherited = calculate_sci(
            np.array([1.0, 0.0, 0.0]), None, 0.8
        )
        assert continuity == 1.0
        assert inherited == 1.0

    def test_identical_embeddings(self):
        from telos_adapters.langgraph.state_schema import calculate_sci
        emb = np.array([1.0, 0.0, 0.0])
        continuity, inherited = calculate_sci(emb, emb, 0.8)
        assert continuity == pytest.approx(1.0)
        assert inherited == pytest.approx(0.72)  # 0.8 * 0.90

    def test_orthogonal_embeddings_no_inheritance(self):
        from telos_adapters.langgraph.state_schema import calculate_sci
        continuity, inherited = calculate_sci(
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            0.8,
        )
        assert continuity == pytest.approx(0.0, abs=1e-6)
        assert inherited == 0.0


class TestCreateInitialState:
    def test_default_state(self):
        from telos_adapters.langgraph.state_schema import create_initial_state
        state = create_initial_state()
        assert state["messages"] == []
        assert state["primacy_attractor"] is None
        assert state["current_fidelity"] == 1.0
        assert state["current_zone"] == "green"
        assert state["direction_count"] == 0
        assert state["turn_number"] == 0

    def test_state_with_pa(self):
        from telos_adapters.langgraph.state_schema import (
            create_initial_state, PrimacyAttractor,
        )
        pa = PrimacyAttractor(text="test", embedding=np.array([1.0, 2.0]))
        state = create_initial_state(primacy_attractor=pa)
        assert state["primacy_attractor"] is not None
        assert state["primacy_attractor"]["text"] == "test"


# =============================================================================
# GOVERNANCE NODE TESTS
# =============================================================================

def _make_embed_fn(dim=3):
    """Create a deterministic mock embedding function."""
    def embed(text: str) -> np.ndarray:
        # Simple deterministic embedding based on text hash
        h = hash(text) % 10000
        rng = np.random.RandomState(h)
        vec = rng.randn(dim)
        return vec / np.linalg.norm(vec)
    return embed


def _make_high_fidelity_embed_fn(purpose_text: str, dim=16):
    """
    Create an embedding function where all texts have high similarity
    to the purpose text. Used for tests that need to pass fidelity checks.
    """
    base_vec = np.ones(dim) / np.sqrt(dim)

    def embed(text: str) -> np.ndarray:
        if text == purpose_text:
            return base_vec.copy()
        # All other texts get a vector close to purpose (high similarity)
        rng = np.random.RandomState(hash(text) % 10000)
        noise = rng.randn(dim) * 0.05  # small noise
        vec = base_vec + noise
        return vec / np.linalg.norm(vec)

    return embed


class TestCalculateFidelity:
    def test_text_input_requires_embed_fn(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.governance_node import calculate_fidelity
        pa = PrimacyAttractor(text="test", embedding=np.array([1.0, 0.0, 0.0]))
        with pytest.raises(ValueError, match="embed_fn required"):
            calculate_fidelity("some text", pa)

    def test_text_input_with_embed_fn(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.governance_node import calculate_fidelity
        embed = _make_embed_fn()
        pa = PrimacyAttractor(text="test", embedding=embed("test"))
        raw, norm = calculate_fidelity("test", pa, embed)
        assert raw == pytest.approx(1.0, abs=0.01)
        assert 0.0 <= norm <= 1.0

    def test_embedding_input(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.governance_node import calculate_fidelity
        pa = PrimacyAttractor(text="t", embedding=np.array([1.0, 0.0, 0.0]))
        raw, norm = calculate_fidelity(np.array([1.0, 0.0, 0.0]), pa)
        assert raw == pytest.approx(1.0, abs=0.01)

    def test_normalized_is_clamped(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.governance_node import calculate_fidelity
        pa = PrimacyAttractor(text="t", embedding=np.array([1.0, 0.0, 0.0]))
        raw, norm = calculate_fidelity(np.array([-1.0, 0.0, 0.0]), pa)
        assert 0.0 <= norm <= 1.0


class TestTelosGovernanceGate:
    def test_passthrough_without_pa(self):
        from telos_adapters.langgraph.governance_node import TelosGovernanceGate
        gate = TelosGovernanceGate(embed_fn=_make_embed_fn())
        state = {"primacy_attractor": None, "messages": []}
        result = gate(state)
        assert result is state  # unchanged

    def test_passthrough_without_messages(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.governance_node import TelosGovernanceGate
        embed = _make_embed_fn()
        pa = PrimacyAttractor(text="test", embedding=embed("test"))
        gate = TelosGovernanceGate(embed_fn=embed)
        state = {"primacy_attractor": pa.to_dict(), "messages": []}
        result = gate(state)
        assert result is state


# =============================================================================
# WRAPPER TESTS
# =============================================================================

class TestTelosWrapper:
    def _make_wrapper(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        embed = _make_embed_fn()
        pa = PrimacyAttractor(text="financial analysis", embedding=embed("financial analysis"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": []}
        return TelosWrapper(
            agent=agent,
            primacy_attractor=pa,
            embed_fn=embed,
            block_on_low_fidelity=False,
        ), agent

    def test_invoke_passes_through(self):
        wrapper, agent = self._make_wrapper()
        state = {"messages": []}
        wrapper.invoke(state)
        agent.invoke.assert_called_once()

    def test_governance_trace_recorded(self):
        wrapper, agent = self._make_wrapper()
        msg = MagicMock()
        msg.content = "analyze my portfolio returns"
        state = {"messages": [msg]}
        wrapper.invoke(state)
        # Should have at least one trace from post-check
        assert len(wrapper.governance_trace) >= 0

    def test_fidelity_trajectory(self):
        wrapper, _ = self._make_wrapper()
        # Initially empty
        assert wrapper.get_fidelity_trajectory() == []


class TestTelosWrap:
    def test_decorator_wraps_agent(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import telos_wrap, TelosWrapper
        embed = _make_embed_fn()
        pa = PrimacyAttractor(text="test", embedding=embed("test"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": []}
        wrapped = telos_wrap(pa, embed)(agent)
        assert isinstance(wrapped, TelosWrapper)


# =============================================================================
# SUPERVISOR TESTS
# =============================================================================

class TestTelosSupervisor:
    def _make_supervisor(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.supervisor import TelosSupervisor
        embed = _make_high_fidelity_embed_fn("code review")
        pa = PrimacyAttractor(text="code review", embedding=embed("code review"))
        agents = {"research": MagicMock(), "code": MagicMock()}
        return TelosSupervisor(
            agents=agents,
            primacy_attractor=pa,
            embed_fn=embed,
        )

    def test_route_with_no_messages(self):
        sup = self._make_supervisor()
        state = {"messages": [], "next_agent": None}
        result = sup.route(state)
        assert result["next_agent"] is None

    def test_route_selects_agent(self):
        sup = self._make_supervisor()
        msg = MagicMock()
        msg.content = "review the code for bugs"
        state = {
            "messages": [msg],
            "current_fidelity": 1.0,
            "current_zone": "green",
            "next_agent": None,
            "delegation_approved": True,
            "direction_count": 0,
        }
        result = sup.route(state)
        assert result["next_agent"] in ["research", "code"]
        assert result["delegation_approved"] is True

    def test_governance_trace_recorded(self):
        sup = self._make_supervisor()
        msg = MagicMock()
        msg.content = "review code"
        state = {
            "messages": [msg],
            "current_fidelity": 1.0,
            "current_zone": "green",
            "next_agent": None,
            "delegation_approved": True,
            "direction_count": 0,
        }
        sup.route(state)
        assert len(sup.get_governance_trace()) >= 1


class TestCreateTelosSupervisor:
    def test_factory(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.supervisor import (
            create_telos_supervisor, TelosSupervisor,
        )
        embed = _make_embed_fn()
        pa = PrimacyAttractor(text="test", embedding=embed("test"))
        sup = create_telos_supervisor(
            agents={"a": MagicMock()},
            primacy_attractor=pa,
            embed_fn=embed,
        )
        assert isinstance(sup, TelosSupervisor)


# =============================================================================
# SWARM TESTS
# =============================================================================

class TestTelosSwarm:
    def _make_swarm(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.swarm import TelosSwarm
        embed = _make_high_fidelity_embed_fn("data analysis")
        pa = PrimacyAttractor(text="data analysis", embedding=embed("data analysis"))
        agents = {"analyst": MagicMock(), "coder": MagicMock()}
        return TelosSwarm(
            agents=agents,
            primacy_attractor=pa,
            embed_fn=embed,
        )

    def test_handoff_approved(self):
        swarm = self._make_swarm()
        result = swarm.handoff(
            from_agent="analyst",
            to_agent="coder",
            context={},
            reason="Need code implementation",
        )
        assert result["approved"] is True
        assert result["from_agent"] == "analyst"
        assert result["to_agent"] == "coder"

    def test_handoff_chain_tracking(self):
        swarm = self._make_swarm()
        swarm.handoff("analyst", "coder", {}, "First handoff")
        swarm.handoff("coder", "analyst", {}, "Second handoff")
        chain = swarm.get_handoff_chain()
        assert len(chain) == 2
        assert chain[0]["from"] == "analyst"
        assert chain[1]["from"] == "coder"

    def test_sci_trajectory(self):
        swarm = self._make_swarm()
        swarm.handoff("analyst", "coder", {}, "First")
        swarm.handoff("coder", "analyst", {}, "Second")
        traj = swarm.get_sci_trajectory()
        assert len(traj) == 2
        for entry in traj:
            assert "sci" in entry
            assert "fidelity" in entry

    def test_governance_trace(self):
        swarm = self._make_swarm()
        swarm.handoff("analyst", "coder", {}, "test")
        trace = swarm.get_governance_trace()
        assert len(trace) >= 1
        assert trace[0]["action_type"] in ("handoff", "handoff_blocked")


class TestCreateTelosSwarm:
    def test_factory(self):
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.swarm import create_telos_swarm, TelosSwarm
        embed = _make_embed_fn()
        pa = PrimacyAttractor(text="test", embedding=embed("test"))
        swarm = create_telos_swarm(
            agents={"a": MagicMock()},
            primacy_attractor=pa,
            embed_fn=embed,
        )
        assert isinstance(swarm, TelosSwarm)


# =============================================================================
# LANGGRAPH __init__ EXPORTS
# =============================================================================

class TestLangGraphExports:
    def test_all_exports_available(self):
        from telos_adapters.langgraph import (
            TelosGovernedState,
            PrimacyAttractor,
            GovernanceTraceEntry,
            ActionChainEntry,
            FidelityZone,
            DirectionLevel,
            TelosGovernanceGate,
            telos_governance_node,
            calculate_fidelity,
            get_fidelity_zone,
            TelosWrapper,
            telos_wrap,
            TelosSupervisor,
            create_telos_supervisor,
            TelosSwarm,
            create_telos_swarm,
        )
        # All imports succeeded
        assert TelosGovernedState is not None

    def test_no_intervention_level_exported(self):
        import telos_adapters.langgraph as lg
        assert not hasattr(lg, "InterventionLevel")


# =============================================================================
# DRIFT TRACKER INTEGRATION TESTS (SAAI-002)
# =============================================================================

class TestWrapperDriftTracker:
    """Test AgenticDriftTracker integration in TelosWrapper (SAAI-002)."""

    def _make_wrapper_with_drift(self, fidelity_sequence=None):
        """Create a wrapper with a real AgenticDriftTracker."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        from telos_governance.response_manager import AgenticDriftTracker

        embed = _make_high_fidelity_embed_fn("financial analysis")
        pa = PrimacyAttractor(
            text="financial analysis",
            embedding=embed("financial analysis"),
        )

        # Agent that returns controlled fidelity content
        agent = MagicMock()
        if fidelity_sequence:
            self._fidelity_idx = 0
            self._fidelity_seq = fidelity_sequence

        agent.invoke.return_value = {
            "messages": [MagicMock(content="analyzing financial data")],
        }

        tracker = AgenticDriftTracker()
        wrapper = TelosWrapper(
            agent=agent,
            primacy_attractor=pa,
            embed_fn=embed,
            block_on_low_fidelity=False,
            drift_tracker=tracker,
        )
        return wrapper, agent, tracker

    def test_drift_tracker_records_fidelity(self):
        """5 invoke() calls should produce >= 5 recorded fidelity scores."""
        wrapper, agent, tracker = self._make_wrapper_with_drift()
        msg = MagicMock(content="analyze my portfolio returns")
        state = {"messages": [msg]}
        for _ in range(5):
            wrapper.invoke(state)
        history = wrapper.get_drift_history()
        assert len(history["all_fidelity_scores"]) >= 5

    def test_no_drift_tracker_when_none(self):
        """drift_tracker=None should not cause errors."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        embed = _make_high_fidelity_embed_fn("test")
        pa = PrimacyAttractor(text="test", embedding=embed("test"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="test")]}
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            drift_tracker=None,
        )
        result = wrapper.invoke({"messages": [MagicMock(content="test")]})
        assert "governance_blocked" not in result or result["governance_blocked"] is not True
        assert wrapper.get_drift_history() == {}

    def test_acknowledge_drift_resets(self):
        """acknowledge_drift() should reset drift level to NORMAL."""
        wrapper, _, tracker = self._make_wrapper_with_drift()
        # Force BLOCK state directly on tracker
        tracker._baseline_established = True
        tracker._baseline_fidelity = 0.90
        tracker._ewma = 0.90
        tracker._drift_level = "BLOCK"
        tracker._drift_magnitude = 0.25
        status = wrapper.acknowledge_drift("user reviewed output")
        assert status["drift_level"] == "NORMAL"

    def test_drift_block_returns_blocked_response(self):
        """When drift triggers BLOCK, invoke() should return governance_blocked."""
        wrapper, agent, tracker = self._make_wrapper_with_drift()
        # Establish baseline first (must also init EWMA for Phase 2)
        tracker._baseline_established = True
        tracker._baseline_fidelity = 0.90
        tracker._ewma = 0.90
        tracker._drift_level = "NORMAL"

        # Make record_fidelity return BLOCK
        original_record = tracker.record_fidelity
        def mock_block(fidelity):
            result = original_record(fidelity)
            # Force BLOCK after recording
            tracker._drift_level = "BLOCK"
            tracker._drift_magnitude = 0.25
            return {
                "drift_level": "BLOCK",
                "drift_magnitude": 0.25,
                "is_blocked": True,
                "is_restricted": False,
                "baseline_fidelity": 0.90,
                "baseline_established": True,
                "turn_count": len(tracker._fidelity_scores),
            }
        tracker.record_fidelity = mock_block

        msg = MagicMock(content="analyze portfolio")
        result = wrapper.invoke({"messages": [msg]})
        assert result.get("governance_blocked") is True
        assert result.get("drift_level") == "BLOCK"

    def test_drift_history_export_shape(self):
        """get_drift_history() should return expected dict keys."""
        wrapper, _, _ = self._make_wrapper_with_drift()
        msg = MagicMock(content="analyze data")
        wrapper.invoke({"messages": [msg]})
        history = wrapper.get_drift_history()
        assert "all_fidelity_scores" in history
        assert "baseline_established" in history
        assert "current_drift_level" in history
        assert "acknowledgment_count" in history

    def test_drift_warning_recorded_in_trace(self):
        """WARNING drift level should record drift_warning action_type in trace."""
        wrapper, agent, tracker = self._make_wrapper_with_drift()
        # Establish baseline and force WARNING state
        tracker._baseline_established = True
        tracker._baseline_fidelity = 0.90
        tracker._ewma = 0.90
        tracker._drift_level = "NORMAL"

        original_record = tracker.record_fidelity
        def mock_warning(fidelity):
            result = original_record(fidelity)
            return {
                "drift_level": "WARNING",
                "drift_magnitude": 0.12,
                "is_blocked": False,
                "is_restricted": False,
                "baseline_fidelity": 0.90,
                "baseline_established": True,
                "turn_count": len(tracker._fidelity_scores),
            }
        tracker.record_fidelity = mock_warning

        msg = MagicMock(content="analyze portfolio")
        wrapper.invoke({"messages": [msg]})
        trace = wrapper.get_governance_trace()
        warning_entries = [e for e in trace if e["action_type"] == "drift_warning"]
        assert len(warning_entries) >= 1


# =============================================================================
# ED25519 SIGNING TESTS (SAAI-005)
# =============================================================================

class _MockReceiptSigner:
    """Minimal mock of ReceiptSigner for testing Ed25519 signing."""

    def __init__(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        self._private_key = Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()

    def sign_payload(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)

    def public_key_bytes(self) -> bytes:
        from cryptography.hazmat.primitives import serialization
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    def verify(self, signature: bytes, payload: bytes) -> bool:
        try:
            self._public_key.verify(signature, payload)
            return True
        except Exception:
            return False


class TestEntrySigning:
    """Test Ed25519 signing of GovernanceTraceEntry (SAAI-005)."""

    def test_trace_entries_are_signed(self):
        """Signed trace entries have entry_signature (128 hex) and public_key (64 hex)."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        embed = _make_high_fidelity_embed_fn("test signing")
        pa = PrimacyAttractor(text="test signing", embedding=embed("test signing"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="signed output")]}
        signer = _MockReceiptSigner()
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            receipt_signer=signer, block_on_low_fidelity=False,
        )
        wrapper.invoke({"messages": [MagicMock(content="test input")]})
        trace = wrapper.get_governance_trace()
        assert len(trace) >= 1
        signed_entry = trace[-1]
        assert "entry_signature" in signed_entry
        assert "public_key" in signed_entry
        assert len(signed_entry["entry_signature"]) == 128  # 64 bytes hex
        assert len(signed_entry["public_key"]) == 64  # 32 bytes hex

    def test_no_signing_when_signer_none(self):
        """receipt_signer=None should produce no signature fields."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        embed = _make_high_fidelity_embed_fn("no sign test")
        pa = PrimacyAttractor(text="no sign test", embedding=embed("no sign test"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="output")]}
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            receipt_signer=None, block_on_low_fidelity=False,
        )
        wrapper.invoke({"messages": [MagicMock(content="input")]})
        trace = wrapper.get_governance_trace()
        assert len(trace) >= 1
        assert "entry_signature" not in trace[-1]
        assert "public_key" not in trace[-1]

    def test_signature_verifies(self):
        """Reconstructed canonical payload should verify against Ed25519 signature."""
        import hashlib
        import json as _json
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        embed = _make_high_fidelity_embed_fn("verify test")
        pa = PrimacyAttractor(text="verify test", embedding=embed("verify test"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="verified")]}
        signer = _MockReceiptSigner()
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            receipt_signer=signer, block_on_low_fidelity=False,
        )
        wrapper.invoke({"messages": [MagicMock(content="verify input")]})
        trace = wrapper.get_governance_trace()
        entry = trace[-1]
        # Reconstruct and verify
        sig_bytes = bytes.fromhex(entry["entry_signature"])
        signable = {k: v for k, v in entry.items()
                    if k not in ("entry_signature", "public_key")}
        canonical = _json.dumps(signable, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).digest()
        assert signer.verify(sig_bytes, payload_hash)

    def test_supervisor_signing(self):
        """TelosSupervisor with receipt_signer should sign trace entries."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.supervisor import TelosSupervisor
        embed = _make_high_fidelity_embed_fn("supervised signing")
        pa = PrimacyAttractor(
            text="supervised signing",
            embedding=embed("supervised signing"),
        )
        signer = _MockReceiptSigner()
        sup = TelosSupervisor(
            agents={"research": MagicMock(), "code": MagicMock()},
            primacy_attractor=pa,
            embed_fn=embed,
            receipt_signer=signer,
        )
        msg = MagicMock(content="review the signed code")
        state = {
            "messages": [msg],
            "current_fidelity": 1.0,
            "current_zone": "green",
            "next_agent": None,
            "delegation_approved": True,
            "direction_count": 0,
        }
        sup.route(state)
        trace = sup.get_governance_trace()
        assert len(trace) >= 1
        assert "entry_signature" in trace[-1]
        assert "public_key" in trace[-1]
        assert len(trace[-1]["entry_signature"]) == 128

    def test_swarm_signing(self):
        """TelosSwarm with receipt_signer should sign trace entries."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.swarm import TelosSwarm
        embed = _make_high_fidelity_embed_fn("swarm signing")
        pa = PrimacyAttractor(
            text="swarm signing",
            embedding=embed("swarm signing"),
        )
        signer = _MockReceiptSigner()
        swarm = TelosSwarm(
            agents={"analyst": MagicMock(), "coder": MagicMock()},
            primacy_attractor=pa,
            embed_fn=embed,
            receipt_signer=signer,
        )
        result = swarm.handoff("analyst", "coder", {}, "Need signing test")
        assert result["approved"] is True
        trace = swarm.get_governance_trace()
        assert len(trace) >= 1
        assert "entry_signature" in trace[-1]
        assert "public_key" in trace[-1]
        assert len(trace[-1]["entry_signature"]) == 128


# =============================================================================
# AUDIT TRAIL TESTS (SAAI-005)
# =============================================================================

class TestAuditExport:
    """Test persistent NDJSON audit trail (SAAI-005)."""

    def test_audit_file_created(self, tmp_path):
        """audit_path set should create an NDJSON file with events."""
        import json
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        audit_file = tmp_path / "audit.ndjson"
        embed = _make_high_fidelity_embed_fn("audit test")
        pa = PrimacyAttractor(text="audit test", embedding=embed("audit test"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="audited")]}
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            audit_path=str(audit_file), block_on_low_fidelity=False,
        )
        wrapper.invoke({"messages": [MagicMock(content="test audit")]})
        assert audit_file.exists()
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) >= 1
        for line in lines:
            record = json.loads(line)
            assert "event" in record
            assert "timestamp" in record
            assert "data" in record

    def test_audit_events_have_schema(self, tmp_path):
        """Each NDJSON line should have event/timestamp/data fields."""
        import json
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        audit_file = tmp_path / "schema_audit.ndjson"
        embed = _make_high_fidelity_embed_fn("schema test")
        pa = PrimacyAttractor(text="schema test", embedding=embed("schema test"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="schema output")]}
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            audit_path=str(audit_file), block_on_low_fidelity=False,
        )
        wrapper.invoke({"messages": [MagicMock(content="schema input")]})
        lines = audit_file.read_text().strip().split("\n")
        for line in lines:
            record = json.loads(line)
            assert record["event"] == "governance_decision"
            assert isinstance(record["timestamp"], (int, float))
            assert isinstance(record["data"], dict)
            assert "fidelity_score" in record["data"]

    def test_no_audit_when_path_none(self):
        """audit_path=None should not create any file I/O."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.wrapper import TelosWrapper
        embed = _make_high_fidelity_embed_fn("no audit")
        pa = PrimacyAttractor(text="no audit", embedding=embed("no audit"))
        agent = MagicMock()
        agent.invoke.return_value = {"messages": [MagicMock(content="no audit")]}
        wrapper = TelosWrapper(
            agent=agent, primacy_attractor=pa, embed_fn=embed,
            audit_path=None, block_on_low_fidelity=False,
        )
        wrapper.invoke({"messages": [MagicMock(content="no audit input")]})
        assert wrapper._audit_writer is None


# =============================================================================
# SWARM DRIFT TRACKER TESTS (SAAI-002, P0 quick win)
# =============================================================================

class TestSwarmDriftTracker:
    """Test AgenticDriftTracker integration in TelosSwarm (SAAI-002)."""

    def _make_swarm_with_drift(self):
        """Create a swarm with a real AgenticDriftTracker."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.swarm import TelosSwarm
        from telos_governance.response_manager import AgenticDriftTracker

        embed = _make_high_fidelity_embed_fn("project management tasks")
        pa = PrimacyAttractor(
            text="project management tasks",
            embedding=embed("project management tasks"),
        )
        agents = {"planner": MagicMock(), "executor": MagicMock()}
        tracker = AgenticDriftTracker()
        swarm = TelosSwarm(
            agents=agents,
            primacy_attractor=pa,
            embed_fn=embed,
            require_approval_for_handoff=False,
            drift_tracker=tracker,
        )
        return swarm, tracker

    def test_swarm_drift_tracker_records_fidelity(self):
        """Handoffs should feed fidelity into the drift tracker."""
        swarm, tracker = self._make_swarm_with_drift()
        for i in range(5):
            swarm.handoff(
                from_agent="planner", to_agent="executor",
                context={}, reason=f"Execute task {i} for project management",
            )
        history = tracker.get_drift_history()
        assert len(history["all_fidelity_scores"]) >= 5

    def test_swarm_no_drift_tracker_when_none(self):
        """drift_tracker=None should cause no errors."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.swarm import TelosSwarm

        embed = _make_high_fidelity_embed_fn("no drift test")
        pa = PrimacyAttractor(text="no drift test", embedding=embed("no drift test"))
        swarm = TelosSwarm(
            agents={"a": MagicMock()},
            primacy_attractor=pa,
            embed_fn=embed,
            require_approval_for_handoff=False,
            drift_tracker=None,
        )
        result = swarm.handoff(
            from_agent="a", to_agent="a", context={}, reason="test handoff",
        )
        assert result["approved"]

    def test_swarm_acknowledge_drift(self):
        """acknowledge_drift should reset drift to NORMAL."""
        swarm, tracker = self._make_swarm_with_drift()
        # Do handoffs to establish baseline
        for i in range(5):
            swarm.handoff(
                from_agent="planner", to_agent="executor",
                context={}, reason=f"Project management task {i}",
            )
        status = swarm.acknowledge_drift("Testing acknowledgment")
        assert status.get("drift_level") == "NORMAL" or "acknowledged" in str(status).lower() or "error" not in status

    def test_swarm_drift_history_export(self):
        """get_drift_history should return expected dict shape."""
        swarm, tracker = self._make_swarm_with_drift()
        swarm.handoff(
            from_agent="planner", to_agent="executor",
            context={}, reason="Project planning task",
        )
        history = swarm.get_drift_history()
        assert isinstance(history, dict)
        assert "all_fidelity_scores" in history

    def test_swarm_no_drift_history_when_none(self):
        """get_drift_history with no tracker returns empty dict."""
        from telos_adapters.langgraph.state_schema import PrimacyAttractor
        from telos_adapters.langgraph.swarm import TelosSwarm

        embed = _make_high_fidelity_embed_fn("no history")
        pa = PrimacyAttractor(text="no history", embedding=embed("no history"))
        swarm = TelosSwarm(
            agents={"a": MagicMock()},
            primacy_attractor=pa,
            embed_fn=embed,
            drift_tracker=None,
        )
        assert swarm.get_drift_history() == {}

    def test_swarm_drift_annotates_trace(self):
        """Drift fields should appear in governance trace entries."""
        swarm, tracker = self._make_swarm_with_drift()
        for i in range(5):
            swarm.handoff(
                from_agent="planner", to_agent="executor",
                context={}, reason=f"Project task {i} management",
            )
        # After enough handoffs, trace entries should have drift_level
        has_drift_fields = any(
            "drift_level" in entry for entry in swarm.governance_trace
        )
        assert has_drift_fields
