"""Backward-compat shim. Use `telos_governance.pa.agent_templates` for new code."""
import sys as _sys, importlib as _importlib
_sys.modules[__name__] = _importlib.import_module("telos_governance.pa.agent_templates")
