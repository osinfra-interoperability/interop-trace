"""System-level check for the package entry point."""

import builtins
import subprocess
import sys

from typer.testing import CliRunner

from interop_trace.cli import app


def test_module_entry_point_shows_help():
    """Ensure the package exposes the CLI without running an analysis."""
    result = subprocess.run(
        [sys.executable, "-m", "interop_trace", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Tracing interoperability" in result.stdout


def test_interface_explains_missing_optional_dependency(monkeypatch):
    original_import = builtins.__import__

    def without_ui(name, *args, **kwargs):
        if name == "interop_trace.interface":
            raise ModuleNotFoundError("No module named 'nicegui'", name="nicegui")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_ui)
    result = CliRunner().invoke(app, ["ui"])
    assert result.exit_code == 1
    assert "poetry install --extras ui" in result.output
