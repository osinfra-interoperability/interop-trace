"""Contracts for obtaining experimental measurements and sample information."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Dataset:
    """Prepared measurements and optional sample metadata, at absolute paths.

    ``files`` can contain raw measurements or converted files such as mzML.
    ``sample_metadata`` describes the samples and their relationship to files;
    its format must be understood by the consuming workflow or benchmark.
    This record does not read or validate the files.
    """

    files: tuple[Path, ...]
    sample_metadata: Path | None = None


class DatasetProvider(Protocol):
    """A dataset source configured with its implementation-specific parameters."""

    def prepare(self, *, output_dir: Path) -> Dataset:
        """Return local inputs, using ``output_dir`` for any generated files.

        Implementations may retrieve remote data or reuse existing local data.
        They must return existing, absolute paths or raise an exception.
        """
        ...
