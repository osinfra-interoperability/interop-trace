"""Shared execution and assessment vocabularies for records and interfaces."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Execution progress, including unknown or not-yet-started UI states."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AssessmentOutcome(StrEnum):
    """Assessor conclusion, separate from whether execution completed."""

    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class AssessmentCategory(StrEnum):
    """Cause category; only unknown is defined until classification is developed."""

    UNKNOWN = "unknown"
