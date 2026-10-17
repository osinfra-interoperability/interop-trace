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


@app.command("run")
def run(
    configuration: Annotated[
        Path, typer.Argument(help="Experiment YAML file.", exists=True, dir_okay=False)
    ],
    output: Annotated[
        Path, typer.Option("--output", help="New directory for this run.")
    ] = Path("results/run-001"),
    cache_directory: Annotated[
        Path, typer.Option("--cache-directory", help="Shared download cache.")
    ] = DEFAULT_CACHE_DIR,
    check: Annotated[
        bool,
        typer.Option(
            "--check", help="Validate configuration without setup or execution."
        ),
    ] = False,
) -> None:
    """Load reusable component settings and execute the selected experiments."""
    from interop_trace.experiments import load_configuration, run_experiments

    try:
        configured = load_configuration(configuration)
        if check:
            typer.echo(
                f"Valid configuration: {len(configured.experiments)} experiment(s)."
            )
            return
        results = run_experiments(
            configured, output_dir=output, cache_dir=cache_directory
        )
    except Exception as error:
        typer.echo(f"Run failed: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Completed {len(results)} experiment(s): {output.resolve()}")


@app.command("components")
def list_components(
    update_docs: Annotated[
        bool, typer.Option("--update-docs", help="Update marked catalogue tables.")
    ] = False,
    check_docs: Annotated[
        bool, typer.Option("--check-docs", help="Fail if catalogue tables are stale.")
    ] = False,
    root: Annotated[
        Path, typer.Option("--root", help="Repository root for documentation tables.")
    ] = Path("."),
) -> None:
    """List available implementations without downloads or optional scoring imports."""
    from interop_trace.catalogue import component_table, update_catalogue

    if update_docs and check_docs:
        raise typer.BadParameter("Choose --update-docs or --check-docs.")
    if update_docs or check_docs:
        try:
            update_catalogue(root.resolve(), check=check_docs)
        except (OSError, ValueError) as error:
            raise typer.BadParameter(str(error)) from error
        typer.echo("Component catalogue is current.")
    else:
        typer.echo(component_table(detailed=True))


@cache_app.command("list")
def list_downloads(
    directory: Annotated[
        Path, typer.Option("--directory", help="Cache directory.")
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Show names, component types, sources, sizes, releases and download times."""
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
            f"{entry.name or 'unknown'} | type: {entry.kind or 'unknown'} | "
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
