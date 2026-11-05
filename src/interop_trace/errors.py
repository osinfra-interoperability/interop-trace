"""Errors describing requirements a component consumer could not satisfy."""


class UnsupportedFormatError(ValueError):
    """The consumer cannot read the supplied format."""


class MissingOutputError(ValueError):
    """A required workflow output is absent."""


class ResultSchemaError(ValueError):
    """An output lacks the structure required by its consumer."""


class UnsupportedEvaluationError(ValueError):
    """The supplied information cannot support the requested evaluation."""


class BenchmarkInputMismatchError(ValueError):
    """Supplied inputs do not match the benchmark's required reference selection."""
