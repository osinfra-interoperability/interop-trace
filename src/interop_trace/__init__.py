"""Interop Trace package metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("interop-trace")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
