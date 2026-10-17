"""Contracts for preparing protein sequence databases."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Database:
    """A prepared protein FASTA file at an absolute path.

    The sequences are search candidates, not benchmark ground truth.
    This record does not parse or validate the FASTA contents.
    """

    fasta: Path


class DatabaseProvider(Protocol):
    """A sequence source configured with its implementation-specific parameters."""

    def prepare(self, *, output_dir: Path) -> Database:
        """Return a local FASTA, using ``output_dir`` for any generated files.

        Implementations select or retrieve sequences according to their own
        settings and must return an existing, absolute path or raise an exception.
        """
        ...
