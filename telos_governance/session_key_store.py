"""Backward-compat shim. Use `telos_governance.crypto.session_key_store` for new code."""
import sys as _sys, importlib as _importlib
_sys.modules[__name__] = _importlib.import_module("telos_governance.crypto.session_key_store")
