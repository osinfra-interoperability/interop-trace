"""Check cache inspection and the user's control over clearing downloads."""

from pathlib import Path

from typer.testing import CliRunner

from interop_trace.cli import app
from interop_trace.downloads import DownloadCache


def download(url: str, destination: Path) -> dict[str, str | None]:
    destination.write_bytes(b"downloaded content")
    return {"release": "test_release"}


def test_list_shows_source_release_path_and_missing_status(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    first = cache.fetch("https://example.org/first", download)
    missing = cache.fetch("https://example.org/missing", download)
    missing.path.unlink()

    result = CliRunner().invoke(app, ["cache", "list", "--directory", str(cache.root)])

    assert result.exit_code == 0, result.output
    assert "test_release" in result.output
    assert "https://example.org/first" in result.output
    assert str(first.path) in result.output
    assert first.downloaded_at in result.output
    assert "missing/changed" in result.output


def test_clear_can_be_cancelled(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    entry = cache.fetch("https://example.org/file", download)

    result = CliRunner().invoke(
        app, ["cache", "clear", "--directory", str(cache.root)], input="n\n"
    )

    assert result.exit_code != 0
    assert entry.available


def test_clear_yes_removes_cache_but_keeps_run_metadata(tmp_path: Path) -> None:
    cache = DownloadCache(tmp_path / "cache")
    entry = cache.fetch("https://example.org/file", download)
    metadata = tmp_path / "run-uniprot.json"
    metadata.write_text('{"release": "test_release"}')

    result = CliRunner().invoke(
        app, ["cache", "clear", "--directory", str(cache.root), "--yes"]
    )

    assert result.exit_code == 0, result.output
    assert not entry.path.exists()
    assert cache.entries() == []
    assert metadata.read_text() == '{"release": "test_release"}'


def test_clear_rejects_unmanaged_folder(tmp_path: Path) -> None:
    important = tmp_path / "important.txt"
    important.write_text("keep me")

    result = CliRunner().invoke(
        app, ["cache", "clear", "--directory", str(tmp_path), "--yes"]
    )

    assert result.exit_code != 0
    assert "Not an interop-trace cache" in result.output
    assert important.read_text() == "keep me"


def test_list_does_not_create_an_unused_cache(tmp_path: Path) -> None:
    directory = tmp_path / "cache"

    result = CliRunner().invoke(app, ["cache", "list", "--directory", str(directory)])

    assert result.exit_code == 0
    assert "No registered downloads" in result.output
    assert not directory.exists()
