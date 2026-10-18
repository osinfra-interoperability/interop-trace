"""System-level check for the package entry point."""

import subprocess
import sys


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
