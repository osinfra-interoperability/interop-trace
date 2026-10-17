"""Check Sage installation using real, tiny archives and no network requests."""

import json
import os
import tarfile
import zipfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from requests import Response

from interop_trace.downloads import DownloadCache
from interop_trace.workflows import download_sage


def archive_bytes(url: str, *, include_binary: bool = True) -> bytes:
    buffer = BytesIO()
    asset = url.rsplit("/", 1)[1]
    windows = asset.endswith(".zip")
    name = asset.removesuffix(".zip").removesuffix(".tar.gz")
    files = {"LICENSE": b"license", "README.md": b"readme"}
    if include_binary:
        files["sage.exe" if windows else "sage"] = b"test executable"
    if windows:
        with zipfile.ZipFile(buffer, "w") as archive:
            for filename, content in files.items():
                archive.writestr(f"{name}/{filename}", content)
    else:
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            for filename, content in files.items():
                member = tarfile.TarInfo(f"{name}/{filename}")
                member.size = len(content)
                member.mode = 0o755 if filename == "sage" else 0o644
                archive.addfile(member, BytesIO(content))
    return buffer.getvalue()


@pytest.fixture
def downloader(
    monkeypatch: pytest.MonkeyPatch,
    http_transport: Mock,
    http_response: Callable[..., Response],
) -> Mock:
    monkeypatch.setattr(
        "interop_trace.workflows.sage.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr(
        "interop_trace.workflows.sage.platform.machine", lambda: "arm64"
    )
    http_transport.side_effect = lambda request: http_response(
        archive_bytes(request.url)
    )
    return http_transport


@pytest.mark.parametrize(
    "system, machine, target",
    [
        ("Darwin", "arm64", "aarch64-apple-darwin"),
        ("Darwin", "x86_64", "x86_64-apple-darwin"),
        ("Linux", "aarch64", "aarch64-unknown-linux-musl"),
        ("Linux", "x86_64", "x86_64-unknown-linux-musl"),
        ("Windows", "AMD64", "x86_64-pc-windows-msvc"),
    ],
)
def test_download_selects_build_and_records_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    downloader: Mock,
    system: str,
    machine: str,
    target: str,
) -> None:
    monkeypatch.setattr("interop_trace.workflows.sage.platform.system", lambda: system)
    monkeypatch.setattr(
        "interop_trace.workflows.sage.platform.machine", lambda: machine
    )
    cache = DownloadCache(tmp_path / "cache")

    executable = download_sage(cache_dir=cache.root)

    suffix = ".zip" if system == "Windows" else ".tar.gz"
    url = (
        "https://github.com/lazear/sage/releases/download/v0.14.7/"
        f"sage-v0.14.7-{target}{suffix}"
    )
    assert downloader.call_args.args[0].url == url
    assert executable.is_absolute()
    assert executable.read_bytes() == b"test executable"
    assert (executable.parent / "LICENSE").is_file()
    assert len(cache.entries()) == 1
    entry = cache.entries()[0]
    assert entry.name == "sage"
    assert entry.kind == "workflow"
    assert entry.url == url
    assert entry.metadata == {"version": "0.14.7"}
    assert entry.downloaded_at
    assert json.loads((entry.path.parent / "download.json").read_text())["path"] == str(
        entry.path
    )
    if system != "Windows":
        assert executable.stat().st_mode & 0o100


def test_repeat_call_reuses_download_and_extraction(
    tmp_path: Path, downloader: Mock
) -> None:
    executable = download_sage(cache_dir=tmp_path / "cache")
    os.utime(executable, (42, 42))

    repeated = download_sage(cache_dir=tmp_path / "cache")

    downloader.assert_called_once()
    assert repeated == executable
    assert repeated.stat().st_mtime == 42


def test_missing_executable_is_restored_without_downloading(
    tmp_path: Path, downloader: Mock
) -> None:
    executable = download_sage(cache_dir=tmp_path / "cache")
    executable.unlink()

    restored = download_sage(cache_dir=tmp_path / "cache")

    downloader.assert_called_once()
    assert restored.read_bytes() == b"test executable"


def test_versions_have_separate_downloads(tmp_path: Path, downloader: Mock) -> None:
    first = download_sage("0.14.7", cache_dir=tmp_path / "cache")
    second = download_sage("0.14.6", cache_dir=tmp_path / "cache")

    assert first != second
    assert downloader.call_count == 2
    assert len(DownloadCache(tmp_path / "cache").entries()) == 2


def test_clear_removes_archive_and_executable(tmp_path: Path, downloader: Mock) -> None:
    cache = DownloadCache(tmp_path / "cache")
    executable = download_sage(cache_dir=cache.root)
    archive = cache.entries()[0].path

    cache.clear()

    assert not executable.exists()
    assert not archive.exists()
    assert download_sage(cache_dir=cache.root).is_file()
    assert downloader.call_count == 2


def test_missing_binary_is_an_error(
    tmp_path: Path, downloader: Mock, http_response: Callable[..., Response]
) -> None:
    downloader.side_effect = lambda request: http_response(
        archive_bytes(request.url, include_binary=False)
    )

    with pytest.raises(FileNotFoundError, match="release does not contain"):
        download_sage(cache_dir=tmp_path / "cache")


def test_unsupported_platform_fails_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, downloader: Mock
) -> None:
    monkeypatch.setattr(
        "interop_trace.workflows.sage.platform.system", lambda: "Windows"
    )

    with pytest.raises(ValueError, match="No Sage download for Windows/aarch64"):
        download_sage(cache_dir=tmp_path / "cache")

    downloader.assert_not_called()
    assert not (tmp_path / "cache").exists()
