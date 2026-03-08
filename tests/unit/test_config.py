"""Tests for TELOS YAML configuration system."""

import os
import tempfile

import pytest
import yaml

from telos_governance.config import (
    AgentConfig,
    ConfigValidationError,
    load_config,
    validate_config,
)


def _write_yaml(data, suffix=".yaml"):
    """Write data to a temporary YAML file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
    yaml.dump(data, f, default_flow_style=False)
    f.close()
    return f.name


def _minimal_config():
    """Return a minimal valid configuration dict."""
    return {
        "agent": {"id": "test_agent", "name": "Test Agent"},
        "purpose": {"statement": "Help users test things"},
        "scope": "Unit testing and validation",
    }


class TestConfigValidation:
    """Tests for schema validation."""

    def test_minimal_valid_config(self):
        path = _write_yaml(_minimal_config())
        try:
            is_valid, errors = validate_config(path)
            assert is_valid, f"Expected valid, got errors: {errors}"
            assert errors == []
        finally:
            os.unlink(path)

    def test_missing_agent_section(self):
        data = _minimal_config()
        del data["agent"]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("agent" in e for e in errors)
        finally:
            os.unlink(path)

    def test_missing_agent_id(self):
        data = _minimal_config()
        del data["agent"]["id"]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("agent.id" in e for e in errors)
        finally:
            os.unlink(path)

    def test_missing_purpose(self):
        data = _minimal_config()
        del data["purpose"]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("purpose" in e for e in errors)
        finally:
            os.unlink(path)

    def test_missing_scope(self):
        data = _minimal_config()
        del data["scope"]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("scope" in e for e in errors)
        finally:
            os.unlink(path)

    def test_purpose_string_form(self):
        data = _minimal_config()
        data["purpose"] = "Help users test things"
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert is_valid, f"Expected valid, got errors: {errors}"
        finally:
            os.unlink(path)

    def test_scope_dict_format(self):
        """Scope as dict with statement and example_requests validates and loads."""
        data = _minimal_config()
        data["scope"] = {
            "statement": "Unit testing and validation",
            "example_requests": ["Run tests", "Check coverage"],
        }
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert is_valid, f"Expected valid, got errors: {errors}"
            cfg = load_config(path)
            assert cfg.scope == "Unit testing and validation"
            assert cfg.scope_example_requests == ["Run tests", "Check coverage"]
        finally:
            os.unlink(path)

    def test_scope_string_format_backward_compat(self):
        """Scope as plain string produces empty scope_example_requests."""
        data = _minimal_config()
        data["scope"] = "Unit testing and validation"
        path = _write_yaml(data)
        try:
            cfg = load_config(path)
            assert cfg.scope == "Unit testing and validation"
            assert cfg.scope_example_requests == []
        finally:
            os.unlink(path)

    def test_scope_dict_missing_statement(self):
        """Scope dict without statement fails validation."""
        data = _minimal_config()
        data["scope"] = {"example_requests": ["Run tests"]}
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("scope.statement" in e for e in errors)
        finally:
            os.unlink(path)

    def test_invalid_boundary_severity(self):
        data = _minimal_config()
        data["boundaries"] = [{"text": "No bad things", "severity": "extreme"}]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("severity" in e for e in errors)
        finally:
            os.unlink(path)

    def test_invalid_tool_risk_level(self):
        data = _minimal_config()
        data["tools"] = [{"name": "t", "description": "d", "risk_level": "extreme"}]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("risk_level" in e for e in errors)
        finally:
            os.unlink(path)

    def test_tool_missing_description(self):
        data = _minimal_config()
        data["tools"] = [{"name": "t"}]
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert any("description" in e for e in errors)
        finally:
            os.unlink(path)

    def test_invalid_constraints(self):
        data = _minimal_config()
        data["constraints"] = {
            "max_chain_length": -1,
            "escalation_threshold": 2.0,
        }
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert len(errors) >= 2
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        is_valid, errors = validate_config("/nonexistent/path.yaml")
        assert not is_valid
        assert any("not found" in e.lower() or "not found" in e for e in errors)

    def test_multiple_errors_reported(self):
        """Validation should collect all errors, not stop at first."""
        data = {}  # Missing everything
        path = _write_yaml(data)
        try:
            is_valid, errors = validate_config(path)
            assert not is_valid
            assert len(errors) >= 3  # agent, purpose, scope
        finally:
            os.unlink(path)


class TestConfigLoading:
    """Tests for loading and parsing configuration."""

    def test_load_minimal(self):
        path = _write_yaml(_minimal_config())
        try:
            cfg = load_config(path)
            assert isinstance(cfg, AgentConfig)
            assert cfg.agent_id == "test_agent"
            assert cfg.agent_name == "Test Agent"
            assert cfg.purpose == "Help users test things"
            assert cfg.scope == "Unit testing and validation"
        finally:
            os.unlink(path)

    def test_load_with_boundaries(self):
        data = _minimal_config()
        data["boundaries"] = [
            "No destructive operations",
            {"text": "No PII access", "severity": "hard"},
            {"text": "No external API calls", "severity": "soft"},
        ]
        path = _write_yaml(data)
        try:
            cfg = load_config(path)
            assert len(cfg.boundaries) == 3
            assert cfg.boundaries[0].text == "No destructive operations"
            assert cfg.boundaries[0].severity == "hard"  # default
            assert cfg.boundaries[1].severity == "hard"
            assert cfg.boundaries[2].severity == "soft"
        finally:
            os.unlink(path)

    def test_load_with_tools(self):
        data = _minimal_config()
        data["tools"] = [
            {"name": "query", "description": "Run queries"},
            {"name": "admin", "description": "Admin ops", "risk_level": "critical"},
        ]
        path = _write_yaml(data)
        try:
            cfg = load_config(path)
            assert len(cfg.tools) == 2
            assert cfg.tools[0].name == "query"
            assert cfg.tools[0].risk_level == "low"  # default
            assert cfg.tools[1].risk_level == "critical"
        finally:
            os.unlink(path)

    def test_load_with_constraints(self):
        data = _minimal_config()
        data["constraints"] = {
            "max_chain_length": 10,
            "max_tool_calls_per_step": 3,
            "escalation_threshold": 0.60,
            "require_human_above_risk": "medium",
        }
        path = _write_yaml(data)
        try:
            cfg = load_config(path)
            assert cfg.constraints.max_chain_length == 10
            assert cfg.constraints.max_tool_calls_per_step == 3
            assert cfg.constraints.escalation_threshold == 0.60
            assert cfg.constraints.require_human_above_risk == "medium"
        finally:
            os.unlink(path)

    def test_load_with_example_requests(self):
        data = _minimal_config()
        data["purpose"]["example_requests"] = ["Query A", "Query B"]
        path = _write_yaml(data)
        try:
            cfg = load_config(path)
            assert cfg.example_requests == ["Query A", "Query B"]
        finally:
            os.unlink(path)

    def test_load_with_safe_exemplars(self):
        data = _minimal_config()
        data["safe_exemplars"] = ["Safe query 1", "Safe query 2"]
        path = _write_yaml(data)
        try:
            cfg = load_config(path)
            assert cfg.safe_exemplars == ["Safe query 1", "Safe query 2"]
        finally:
            os.unlink(path)

    def test_load_invalid_raises(self):
        data = {"boundaries": []}  # Missing required fields
        path = _write_yaml(data)
        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                load_config(path)
            assert len(exc_info.value.errors) >= 3
        finally:
            os.unlink(path)

    def test_config_path_tracked(self):
        path = _write_yaml(_minimal_config())
        try:
            cfg = load_config(path)
            # resolve() expands symlinks (macOS /var -> /private/var)
            assert os.path.realpath(cfg.config_path) == os.path.realpath(path)
        finally:
            os.unlink(path)

    def test_default_constraints(self):
        """Loading without constraints section uses defaults."""
        path = _write_yaml(_minimal_config())
        try:
            cfg = load_config(path)
            assert cfg.constraints.max_chain_length == 20
            assert cfg.constraints.max_tool_calls_per_step == 5
            assert cfg.constraints.escalation_threshold == 0.50
            assert cfg.constraints.require_human_above_risk == "high"
        finally:
            os.unlink(path)


class TestPropertyIntelTemplate:
    """Test the reference property_intel.yaml template."""

    TEMPLATE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "templates",
        "property_intel.yaml",
    )

    def test_template_validates(self):
        if not os.path.exists(self.TEMPLATE_PATH):
            pytest.skip("Template file not found")
        is_valid, errors = validate_config(self.TEMPLATE_PATH)
        assert is_valid, f"Template validation failed: {errors}"

    def test_template_loads(self):
        if not os.path.exists(self.TEMPLATE_PATH):
            pytest.skip("Template file not found")
        cfg = load_config(self.TEMPLATE_PATH)
        assert cfg.agent_id == "property_intel"
        assert len(cfg.boundaries) == 5
        assert len(cfg.tools) == 6
        assert len(cfg.example_requests) == 5
        assert len(cfg.safe_exemplars) == 10
