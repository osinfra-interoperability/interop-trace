"""Shared execution and assessment vocabularies for records and interfaces."""

from enum import StrEnum


class ExecutionStatus(StrEnum):
    """Execution lifecycle, independent of errors and assessment results."""

    NOT_STARTED = "not_started"
    RUNNING = "running"
    FINISHED = "finished"


class AssessmentOutcome(StrEnum):
    """Assessor conclusion, separate from whether execution completed."""

    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class AssessmentCategory(StrEnum):
    """Observed error category, without claiming an underlying cause."""

    PERMISSION = "permission"
    ENVIRONMENT = "environment"
    PROCESS_ERROR = "process_error"
    MISSING_FILE = "missing_file"
    FILESYSTEM = "filesystem"
    RESOURCE_LIMIT = "resource_limit"
    UNKNOWN = "unknown"
