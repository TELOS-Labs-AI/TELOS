"""Backward-compat shim. Use tools.run_backtest for new code."""
import sys as _sys, importlib as _importlib
_sys.modules[__name__] = _importlib.import_module("tools.run_backtest")
