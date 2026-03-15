"""
Integration tests for config-based SetFit model selection (Phase 4).

Tests that the YAML `setfit:` section is correctly parsed, validated,
and used to construct SetFit classifiers via the config loader.

Run: PYTHONPATH=. pytest tests/integration/test_setfit_config.py -v
"""

import os
import json
import tempfile
from pathlib import Path

import pytest

from telos_governance.config import (
    AgentConfig,
    SetFitConfig,
    ConfigValidationError,
    load_config,
    validate_config,
    _validate_raw_config,
    _parse_config,
)


# --- Minimal valid YAML for testing ---

MINIMAL_CONFIG = {
    "agent": {"id": "test-agent", "name": "Test Agent"},
    "purpose": {"statement": "Test agent purpose"},
    "scope": "Test scope",
    "boundaries": [{"text": "Do not do bad things", "severity": "hard"}],
}


def _write_yaml(data: dict, path: Path) -> Path:
    """Write a dict as YAML to a file."""
    import yaml
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    return path


class TestSetFitConfigDataclass:
    """Tests for the SetFitConfig dataclass."""

    def test_default_values(self):
        cfg = SetFitConfig()
        assert cfg.enabled is False
        assert cfg.model_dir == ""
        assert cfg.calibration == ""
        assert cfg.threshold == 0.50
        assert cfg.asymmetric_override is True

    def test_custom_values(self):
        cfg = SetFitConfig(
            enabled=True,
            model_dir="models/setfit_openclaw_v1",
            calibration="models/setfit_openclaw_v1/calibration.json",
            threshold=0.45,
            asymmetric_override=False,
        )
        assert cfg.enabled is True
        assert cfg.model_dir == "models/setfit_openclaw_v1"
        assert cfg.threshold == 0.45
        assert cfg.asymmetric_override is False


class TestSetFitConfigValidation:
    """Tests for setfit section validation in _validate_raw_config."""

    def test_no_setfit_section_is_valid(self):
        errors = _validate_raw_config(MINIMAL_CONFIG)
        assert len(errors) == 0

    def test_setfit_enabled_with_model_dir(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": True, "model_dir": "models/test"}}
        errors = _validate_raw_config(data)
        assert len(errors) == 0

    def test_setfit_enabled_without_model_dir(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": True}}
        errors = _validate_raw_config(data)
        assert any("model_dir is required" in e for e in errors)

    def test_setfit_disabled_without_model_dir(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": False}}
        errors = _validate_raw_config(data)
        assert len(errors) == 0

    def test_setfit_invalid_threshold(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": True, "model_dir": "m/", "threshold": 1.5}}
        errors = _validate_raw_config(data)
        assert any("threshold must be a float" in e for e in errors)

    def test_setfit_negative_threshold(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": True, "model_dir": "m/", "threshold": -0.1}}
        errors = _validate_raw_config(data)
        assert any("threshold must be a float" in e for e in errors)

    def test_setfit_invalid_enabled_type(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": "yes", "model_dir": "m/"}}
        errors = _validate_raw_config(data)
        assert any("enabled must be a boolean" in e for e in errors)

    def test_setfit_invalid_asymmetric_type(self):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": True, "model_dir": "m/", "asymmetric_override": "true"}}
        errors = _validate_raw_config(data)
        assert any("asymmetric_override must be a boolean" in e for e in errors)

    def test_setfit_not_a_dict(self):
        data = {**MINIMAL_CONFIG, "setfit": "invalid"}
        errors = _validate_raw_config(data)
        assert any("must be a mapping" in e for e in errors)


class TestSetFitConfigParsing:
    """Tests for setfit section parsing in _parse_config."""

    def test_parse_with_setfit_section(self):
        data = {
            **MINIMAL_CONFIG,
            "setfit": {
                "enabled": True,
                "model_dir": "models/setfit_openclaw_v1",
                "threshold": 0.45,
                "asymmetric_override": False,
            },
        }
        config = _parse_config(data)
        assert config.setfit is not None
        assert config.setfit.enabled is True
        assert config.setfit.model_dir == "models/setfit_openclaw_v1"
        assert config.setfit.threshold == 0.45
        assert config.setfit.asymmetric_override is False

    def test_parse_without_setfit_section(self):
        config = _parse_config(MINIMAL_CONFIG)
        assert config.setfit is None

    def test_parse_setfit_defaults(self):
        data = {
            **MINIMAL_CONFIG,
            "setfit": {"enabled": True, "model_dir": "models/test"},
        }
        config = _parse_config(data)
        assert config.setfit.threshold == 0.50
        assert config.setfit.asymmetric_override is True
        assert config.setfit.calibration == ""


class TestSetFitConfigLoadFromYaml:
    """Tests for loading setfit config from YAML files."""

    def test_load_config_with_setfit(self, tmp_path):
        data = {
            **MINIMAL_CONFIG,
            "setfit": {
                "enabled": True,
                "model_dir": "models/setfit_openclaw_v1",
                "calibration": "models/setfit_openclaw_v1/calibration.json",
                "threshold": 0.50,
                "asymmetric_override": True,
            },
        }
        yaml_path = _write_yaml(data, tmp_path / "test.yaml")
        config = load_config(str(yaml_path))
        assert config.setfit is not None
        assert config.setfit.enabled is True
        assert config.setfit.model_dir == "models/setfit_openclaw_v1"
    def test_load_config_without_setfit(self, tmp_path):
        yaml_path = _write_yaml(MINIMAL_CONFIG, tmp_path / "test.yaml")
        config = load_config(str(yaml_path))
        assert config.setfit is None

    def test_validate_config_with_invalid_setfit(self, tmp_path):
        data = {**MINIMAL_CONFIG, "setfit": {"enabled": True}}
        yaml_path = _write_yaml(data, tmp_path / "test.yaml")
        is_valid, errors = validate_config(str(yaml_path))
        assert not is_valid
        assert any("model_dir" in e for e in errors)


class TestSetFitConfigInAgentConfig:
    """Tests that SetFitConfig integrates properly in AgentConfig."""

    def test_agent_config_setfit_field_exists(self):
        config = AgentConfig(agent_id="test", agent_name="Test")
        assert config.setfit is None

    def test_agent_config_with_setfit(self):
        sf = SetFitConfig(enabled=True, model_dir="models/test")
        config = AgentConfig(agent_id="test", agent_name="Test", setfit=sf)
        assert config.setfit is not None
        assert config.setfit.enabled is True


class TestOpenClawYamlSetFitSection:
    """Tests that the openclaw.yaml template includes the setfit section."""

    @pytest.fixture
    def openclaw_yaml_path(self):
        """Path to the openclaw.yaml template."""
        return Path(__file__).resolve().parent.parent.parent / "templates" / "openclaw.yaml"

    def test_openclaw_yaml_has_setfit(self, openclaw_yaml_path):
        if not openclaw_yaml_path.exists():
            pytest.skip("openclaw.yaml not found")

        import yaml
        with open(openclaw_yaml_path) as f:
            data = yaml.safe_load(f)

        assert "setfit" in data
        assert data["setfit"]["enabled"] is True  # Enabled with v2 model (trained on O's audit trail)
        assert "model_dir" in data["setfit"]
        assert data["setfit"]["model_dir"] == "models/setfit_openclaw_v2"

    def test_openclaw_yaml_validates(self, openclaw_yaml_path):
        if not openclaw_yaml_path.exists():
            pytest.skip("openclaw.yaml not found")

        is_valid, errors = validate_config(str(openclaw_yaml_path))
        assert is_valid, f"openclaw.yaml validation failed: {errors}"

    def test_openclaw_yaml_loads_setfit_config(self, openclaw_yaml_path):
        if not openclaw_yaml_path.exists():
            pytest.skip("openclaw.yaml not found")

        config = load_config(str(openclaw_yaml_path))
        assert config.setfit is not None
        assert config.setfit.enabled is True  # Enabled with v2 model
        assert config.setfit.threshold == 0.50
        assert config.setfit.asymmetric_override is True


class TestConfigLoaderSetFitIntegration:
    """Tests for OpenClawConfigLoader SetFit loading from config."""

    def test_config_loader_no_setfit_graceful(self, tmp_path):
        """Config without setfit section should create engine without SetFit."""
        data = {
            **MINIMAL_CONFIG,
            "tools": [{"name": "test_tool", "description": "A test tool"}],
        }
        yaml_path = _write_yaml(data, tmp_path / "test.yaml")

        from telos_adapters.openclaw.config_loader import OpenClawConfigLoader
        import numpy as np

        def mock_embed(text):
            np.random.seed(hash(text) % 2**31)
            v = np.random.randn(384).astype(np.float32)
            return v / np.linalg.norm(v)

        loader = OpenClawConfigLoader()
        loader.load(path=str(yaml_path), embed_fn=mock_embed)

        assert loader.is_loaded
        assert loader.engine is not None
        # Engine should work without SetFit
        assert loader.engine._setfit_classifier is None

    def test_config_loader_setfit_missing_model_graceful(self, tmp_path):
        """Config with setfit enabled but missing model should fall back gracefully."""
        data = {
            **MINIMAL_CONFIG,
            "tools": [{"name": "test_tool", "description": "A test tool"}],
            "setfit": {
                "enabled": True,
                "model_dir": str(tmp_path / "nonexistent_model"),
                "threshold": 0.50,
            },
        }
        yaml_path = _write_yaml(data, tmp_path / "test.yaml")

        from telos_adapters.openclaw.config_loader import OpenClawConfigLoader
        import numpy as np

        def mock_embed(text):
            np.random.seed(hash(text) % 2**31)
            v = np.random.randn(384).astype(np.float32)
            return v / np.linalg.norm(v)

        loader = OpenClawConfigLoader()
        loader.load(path=str(yaml_path), embed_fn=mock_embed)

        assert loader.is_loaded
        assert loader.engine is not None
        # SetFit should have failed gracefully
        assert loader.engine._setfit_classifier is None

    def test_config_loader_setfit_disabled(self, tmp_path):
        """Config with setfit disabled should not attempt to load model."""
        data = {
            **MINIMAL_CONFIG,
            "tools": [{"name": "test_tool", "description": "A test tool"}],
            "setfit": {
                "enabled": False,
                "model_dir": "models/setfit_openclaw_v1",
            },
        }
        yaml_path = _write_yaml(data, tmp_path / "test.yaml")

        from telos_adapters.openclaw.config_loader import OpenClawConfigLoader
        import numpy as np

        def mock_embed(text):
            np.random.seed(hash(text) % 2**31)
            v = np.random.randn(384).astype(np.float32)
            return v / np.linalg.norm(v)

        loader = OpenClawConfigLoader()
        loader.load(path=str(yaml_path), embed_fn=mock_embed)

        assert loader.is_loaded
        assert loader.engine._setfit_classifier is None
