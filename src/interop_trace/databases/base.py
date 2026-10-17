"""Contracts for preparing protein sequence databases."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Database:
    """A prepared protein database at an absolute path, with an explicit format.

    ``format`` identifies the representation, such as ``fasta`` or ``uniprot_xml``.
    Consuming workflows and benchmarks must check that they support this format.
    The sequences are search candidates, not benchmark ground truth.
    This record does not parse, convert or validate the contents.
    """

    path: Path
    format: str


class DatabaseProvider(Protocol):
    """A sequence source configured with its implementation-specific parameters."""

    def prepare(self, *, output_dir: Path) -> Database:
        """Return a local database, using ``output_dir`` for any generated files.

        Implementations select or retrieve sequences according to their own
        settings and declare the resulting format. They must return an existing,
        absolute path or raise an exception.
        """
        ...
