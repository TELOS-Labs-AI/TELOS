"""Backward-compat shim. Use `telos_governance.corpus.boundary_corpus_safe` for new code."""
import sys as _sys, importlib as _importlib
_sys.modules[__name__] = _importlib.import_module("telos_governance.corpus.boundary_corpus_safe")
