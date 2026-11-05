"""Describe the runner's host without inspecting external tools."""

import platform


def capture_environment() -> dict[str, str]:
    """Return host OS, release, architecture and Python version."""
    return {
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }
