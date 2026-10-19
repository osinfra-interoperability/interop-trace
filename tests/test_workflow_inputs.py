"""Check reusable decompression and cleanup of interrupted input preparation."""

import gzip
from pathlib import Path

import pytest

from interop_trace.datasets import Dataset
from interop_trace.workflows._execution import measurement_files


def test_compressed_inputs_are_decompressed_once(tmp_path: Path) -> None:
    source = tmp_path / "sample.mgf.gz"
    source.write_bytes(gzip.compress(b"BEGIN IONS\nEND IONS\n"))
    plain = tmp_path / "other.mzML"
    plain.write_text("spectra")
    dataset = Dataset((source, plain))
    first = measurement_files(dataset)
    assert first == (source.with_suffix(""), plain)
    assert first[0].read_bytes() == b"BEGIN IONS\nEND IONS\n"
    modified = first[0].stat().st_mtime_ns
    assert measurement_files(dataset) == first
    assert first[0].stat().st_mtime_ns == modified


def test_invalid_gzip_does_not_leave_a_reusable_partial_file(tmp_path: Path) -> None:
    source = tmp_path / "sample.mgf.gz"
    source.write_bytes(b"not gzip")
    with pytest.raises(OSError):
        measurement_files(Dataset((source,)))
    assert not source.with_suffix("").exists()
