"""Command-line entry point for Interop Trace."""

from pathlib import Path
from typing import Annotated

import typer

from interop_trace.downloads import DEFAULT_CACHE_DIR, DownloadCache

app = typer.Typer(
    help="Tracing interoperability across bioinformatics databases and workflows.",
    invoke_without_command=True,
    no_args_is_help=True,
)
cache_app = typer.Typer(help="Inspect and clear downloaded files.")
app.add_typer(cache_app, name="cache")


@app.callback()
def callback() -> None:
    """Provide the command group."""


@cache_app.command("list")
def list_downloads(
    directory: Annotated[
        Path, typer.Option("--directory", help="Cache directory.")
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Show registered files, their sources, sizes, releases and download times."""
    cache = DownloadCache(directory)
    try:
        entries = cache.entries()
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--directory") from error
    typer.echo(f"Cache: {cache.root}")
    if not entries:
        typer.echo("No registered downloads.")
    for entry in entries:
        status = "ready" if entry.available else "missing/changed"
        version = entry.metadata.get("release") or entry.metadata.get("version")
        typer.echo(
            f"{status} | {_size(entry.size_bytes)} | version: {version or 'unknown'}"
        )
        typer.echo(
            f"  Downloaded: {entry.downloaded_at}\n  {entry.url}\n  {entry.path}"
        )


@cache_app.command("clear")
def clear_downloads(
    directory: Annotated[
        Path, typer.Option("--directory", help="Cache directory.")
    ] = DEFAULT_CACHE_DIR,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation.")
    ] = False,
) -> None:
    """Remove cached downloads and their registry. Run between workflow runs."""
    cache = DownloadCache(directory)
    try:
        cache.entries()  # Validate ownership before asking to remove anything.
        if not yes:
            typer.confirm(f"Remove all cached downloads from {cache.root}?", abort=True)
        cache.clear()
    except (OSError, ValueError) as error:
        raise typer.BadParameter(str(error), param_hint="--directory") from error
    typer.echo(f"Cleared download cache: {cache.root}")


def _size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    raise AssertionError("Unreachable size unit.")


def main() -> None:
    """Run the command-line application."""
    app()
