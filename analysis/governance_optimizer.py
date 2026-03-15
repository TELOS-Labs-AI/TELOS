"""Backward-compat shim. Use tools.governance_optimizer for new code."""
import sys as _sys, importlib as _importlib
_sys.modules[__name__] = _importlib.import_module("tools.governance_optimizer")
