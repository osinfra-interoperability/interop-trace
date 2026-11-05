"""Errors describing requirements a component consumer could not satisfy."""


class UnsupportedFormatError(ValueError):
    """The consumer cannot read the supplied format."""


class MissingOutputError(ValueError):
    """A required workflow output is absent."""


class ResultSchemaError(ValueError):
    """An output lacks the structure required by its consumer."""
