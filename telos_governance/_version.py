"""Single source of truth for telos package version.

Reads from pyproject.toml via importlib.metadata at runtime.
Avoids dual version strings that drift over time.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("telos")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"  # editable install or uninstalled
