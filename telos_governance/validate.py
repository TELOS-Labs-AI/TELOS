"""Backward-compat shim. Use `telos_governance.teloscope.validate` for new code."""
import sys as _sys, importlib as _importlib
_sys.modules[__name__] = _importlib.import_module("telos_governance.teloscope.validate")
