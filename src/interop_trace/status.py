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
    TIMEOUT = "timeout"
    NETWORK = "network"
    UNSUPPORTED_FORMAT = "unsupported_format"
    MISSING_OUTPUT = "missing_output"
    SCHEMA_MISMATCH = "schema_mismatch"
    UNSUPPORTED_EVALUATION = "unsupported_evaluation"
    BENCHMARK_INPUT_MISMATCH = "benchmark_input_mismatch"
    ACCEPTANCE_CRITERION_NOT_MET = "acceptance_criterion_not_met"
    UNKNOWN = "unknown"
