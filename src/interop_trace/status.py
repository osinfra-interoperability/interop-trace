"""Shared execution status vocabulary for saved records and interfaces."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Execution progress, including unknown or not-yet-started UI states."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"
